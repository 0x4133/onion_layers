// Visual ALM - Client-side JavaScript
// Author: ALM Developer
// Version: 1.0.0

// Global variables
let network;
let selectedNodeId = null;
let conversationTree = { nodes: {}, root_id: null, ghost_branches: {} };
let ollamaConnected = false;
let availableModels = [];
let selectedModel = null;
let isEditMode = false;
let ghostBranches = {};

// Voice-related global variables
let speechSynthesis = null;
let speechRecognition = null;
let isListening = false;
let isSpeaking = false;
let voiceModeEnabled = false;
let availableVoices = [];
let selectedVoice = null;
let currentUtterance = null;

// Configuration
const CONFIG = {
    MAX_MESSAGE_LENGTH: 5000,
    MAX_DISPLAY_MESSAGES: 10,
    MESSAGE_AUTO_REMOVE_DELAY: 8000,
    STATUS_CHECK_INTERVAL: 30000, // Check Ollama status every 30 seconds
    NODE_LABEL_MAX_LENGTH: 30,
    MODEL_STORAGE_KEY: 'alm_selected_model',
    VOICE_SETTINGS_KEY: 'alm_voice_settings',
    SPEECH_TIMEOUT: 10000, // 10 seconds timeout for speech recognition
    TTS_MAX_LENGTH: 1000 // Maximum characters to speak at once
};

// Voice configuration defaults
const VOICE_DEFAULTS = {
    autoTTS: true,
    autoSTT: false,
    rate: 1.0,
    pitch: 1.0,
    voice: null
};

// Configure marked.js for secure markdown rendering
if (typeof marked !== 'undefined') {
    marked.setOptions({
        gfm: true, // GitHub Flavored Markdown
        breaks: true, // Convert \n to <br>
        sanitize: false, // We'll handle XSS protection differently
        smartLists: true,
        smartypants: true
    });
}

// Render markdown content safely
function renderMarkdown(content) {
    if (typeof marked === 'undefined') {
        console.warn('Marked.js not loaded, falling back to plain text');
        return escapeHtml(content);
    }
    
    try {
        // Basic XSS protection: remove script tags and other dangerous elements
        const sanitizedContent = content
            .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
            .replace(/<iframe\b[^<]*(?:(?!<\/iframe>)<[^<]*)*<\/iframe>/gi, '')
            .replace(/javascript:/gi, '')
            .replace(/on\w+\s*=/gi, '');
        
        // Render markdown
        const rendered = marked.parse(sanitizedContent);
        
        // Wrap in markdown-content class for styling
        return `<div class="markdown-content">${rendered}</div>`;
    } catch (error) {
        console.error('Error rendering markdown:', error);
        return `<div class="markdown-content"><p>${escapeHtml(content)}</p></div>`;
    }
}

// Initialize the network visualization
function initNetwork() {
    const container = document.getElementById('tree-network');
    const options = {
        layout: {
            hierarchical: {
                direction: 'UD',
                sortMethod: 'directed',
                nodeSpacing: 150,
                levelSeparation: 120
            }
        },
        physics: false,
        nodes: {
            shape: 'box',
            margin: 10,
            widthConstraint: { maximum: 150 },
            heightConstraint: { minimum: 40 }
        },
        edges: {
            smooth: true,
            arrows: 'to'
        },
        interaction: {
            hover: true,
            multiselect: false
        }
    };

    network = new vis.Network(container, {}, options);
    
    // Handle node selection
    network.on('click', function(params) {
        if (params.nodes.length > 0) {
            const visualNodeId = params.nodes[0];
            
            // Ignore clicks on branch indicators
            if (visualNodeId === 'branch_point_indicator' || visualNodeId === 'new_message_preview') {
                return;
            }
            
            // Extract the real node ID from the visual node ID
            const realNodeId = extractRealNodeId(visualNodeId);
            
            if (realNodeId && conversationTree.nodes[realNodeId]) {
                selectedNodeId = realNodeId;
                updateSelectedNodeInfo();
                updateNetworkView(); // Refresh to show branch indicators
                showMessage(`Selected conversation point. New messages will branch from here.`, 'success');
            }
        } else {
            // Clicked on empty space - deselect
            selectedNodeId = null;
            resetSelectedNodeInfo();
            updateNetworkView(); // Refresh to remove branch indicators
        }
    });

    // Handle hover events
    network.on('hoverNode', function(params) {
        showNodePreview(params.node);
    });
    
    network.on('blurNode', function(params) {
        hideNodePreview();
    });
}

// Extract real conversation node ID from visual node ID
function extractRealNodeId(visualNodeId) {
    if (!visualNodeId) return null;
    
    // Remove _user or _ai suffix to get the actual conversation node ID
    if (visualNodeId.endsWith('_user') || visualNodeId.endsWith('_ai')) {
        return visualNodeId.substring(0, visualNodeId.lastIndexOf('_'));
    }
    return visualNodeId;
}

// Build conversation path from root to specified node
function buildConversationPath(nodeId) {
    if (!nodeId || !conversationTree.nodes[nodeId]) {
        return [];
    }
    
    const path = [];
    let currentId = nodeId;
    
    while (currentId && conversationTree.nodes[currentId]) {
        path.unshift(conversationTree.nodes[currentId]);
        currentId = conversationTree.nodes[currentId].parent_id;
    }
    
    return path;
}

// Check Ollama connection status
async function checkOllamaStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        ollamaConnected = data.ollama_connected;
        
        if (ollamaConnected) {
            showMessage('✅ Ollama is connected and ready!', 'success');
        } else {
            showMessage('⚠️ Ollama is not responding. Please start Ollama.', 'error');
        }
    } catch (error) {
        console.error('Error checking Ollama status:', error);
        ollamaConnected = false;
        showMessage('❌ Could not connect to server.', 'error');
    }
}

// Start periodic status checking
function startPeriodicStatusCheck() {
    // Initial check
    checkOllamaStatus();
    
    // Periodic checks
    setInterval(() => {
        checkOllamaStatus();
    }, CONFIG.STATUS_CHECK_INTERVAL);
}

// Load conversation tree from server
async function loadTree() {
    try {
        const response = await fetch('/api/tree');
        conversationTree = await response.json();
        
        // Ensure ghost_branches exists
        if (!conversationTree.ghost_branches) {
            conversationTree.ghost_branches = {};
        }
        
        updateNetworkView();
    } catch (error) {
        console.error('Error loading tree:', error);
        showMessage('Error loading conversation tree', 'error');
    }
}

// Update the network visualization
function updateNetworkView() {
    if (!network || !conversationTree.nodes) {
        return;
    }
    
    const nodes = [];
    const edges = [];
    
    // Convert tree structure to vis.js format
    Object.values(conversationTree.nodes).forEach(node => {
        let label = `🤖 ${node.id.substring(0, 8)}`;
        let title = `Node: ${node.id}\n`;
        let color = '#74b9ff'; // Default blue
        let borderWidth = 2;
        let shapeProperties = {};
        
        // Check if node has been edited
        const isEdited = node.edit_history && node.edit_history.length > 0;
        
        if (node.user_input) {
            label = `👤 ${truncateText(node.user_input, CONFIG.NODE_LABEL_MAX_LENGTH)}`;
            title += `You: ${node.user_input}\n`;
        }
        
        if (node.ai_response) {
            title += `AI: ${truncateText(node.ai_response, 100)}\n`;
        }
        
        title += `Time: ${new Date(node.timestamp).toLocaleString()}\n`;
        title += `Model: ${node.model_used || 'Unknown'}\n`;
        
        // Style edited nodes differently
        if (isEdited) {
            color = '#ffeaa7'; // Yellow for edited nodes
            borderWidth = 3;
            title += `✏️ EDITED NODE (${node.edit_history.length} edit${node.edit_history.length === 1 ? '' : 's'})\n`;
            
            // Add edit history to tooltip
            node.edit_history.forEach((edit, index) => {
                const editTime = new Date(edit.timestamp).toLocaleString();
                title += `Edit ${index + 1}: ${editTime}\n`;
                if (edit.ghost_created) {
                    title += `Ghost created: ${edit.ghost_created}\n`;
                }
            });
        }
        
        // Add special styling for root node
        if (node.id === conversationTree.root_id) {
            color = isEdited ? '#fdcb6e' : '#00b894'; // Green or orange if edited
            title += '🌟 ROOT NODE\n';
        }
        
        // Check if node has children
        const hasChildren = node.children && node.children.length > 0;
        if (hasChildren) {
            title += `📊 ${node.children.length} child branch${node.children.length === 1 ? '' : 'es'}\n`;
        }
        
        title += '\n💡 Click to continue conversation from this point!';
        
        // Add markdown support note for AI responses
        if (node.ai_response) {
            title += '\n📝 AI responses support markdown formatting - click to see formatted version!';
        }
        
        nodes.push({
            id: node.id,
            label: label,
            title: title,
            color: {
                background: color,
                border: isEdited ? '#e17055' : '#2d3436',
                highlight: {
                    background: isEdited ? '#fdcb6e' : '#55a3ff',
                    border: '#2d3436'
                }
            },
            borderWidth: borderWidth,
            chosen: {
                node: function(values, id, selected, hovering) {
                    if (selected) {
                        values.borderWidth = 4;
                        values.color = isEdited ? '#e17055' : '#6c5ce7';
                    }
                }
            },
            font: {
                color: '#2d3436',
                size: 12,
                face: 'Arial',
                background: 'rgba(255,255,255,0.7)'
            },
            shapeProperties: shapeProperties
        });
        
        // Add edges for children
        if (node.children) {
            node.children.forEach(childId => {
                edges.push({
                    from: node.id,
                    to: childId,
                    arrows: 'to',
                    color: {
                        color: isEdited ? '#e17055' : '#636e72',
                        highlight: '#6c5ce7'
                    },
                    width: 2,
                    smooth: {
                        type: 'curvedCW',
                        roundness: 0.2
                    }
                });
            });
        }
    });
    
    // Update network
    const data = { nodes: nodes, edges: edges };
    network.setData(data);
    
    // Update node count display
    const nodeCount = nodes.length;
    const editedCount = nodes.filter(n => n.borderWidth > 2).length;
    console.log(`Network updated: ${nodeCount} nodes (${editedCount} edited)`);
    
    // Fit network if it's not empty
    if (nodes.length > 0) {
        setTimeout(() => {
            network.fit({
                animation: {
                    duration: 1000,
                    easingFunction: 'easeInOutQuad'
                }
            });
        }, 100);
    }
}

// Check if a node is on the path to the selected node
function isNodeOnPath(nodeId, selectedNodeId) {
    if (!selectedNodeId || !nodeId) return false;
    
    const path = buildConversationPath(selectedNodeId);
    return path.some(node => node.id === nodeId);
}

// Send a message
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message) {
        showMessage('Please enter a message.', 'error');
        input.focus();
        return;
    }
    
    if (message.length > CONFIG.MAX_MESSAGE_LENGTH) {
        showMessage(`Message too long (max ${CONFIG.MAX_MESSAGE_LENGTH} characters).`, 'error');
        return;
    }
    
    const sendButton = document.getElementById('sendButton');
    sendButton.disabled = true;
    showLoading(true);
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                parent_id: selectedNodeId,
                model: selectedModel
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            input.value = '';
            selectedNodeId = data.node_id;
            await loadTree();
            updateSelectedNodeInfo();
            showMessage(`Message sent successfully using ${data.model_used || selectedModel}!`, 'success');
        } else {
            showMessage(data.error || 'Error sending message', 'error');
            
            // If it's an Ollama connection error, suggest checking
            if (data.error && data.error.includes('Ollama')) {
                showMessage('💡 Try: Check Ollama button or restart Ollama', 'error');
            }
        }
    } catch (error) {
        console.error('Error sending message:', error);
        showMessage('Error connecting to server. Is the Flask app running?', 'error');
    } finally {
        sendButton.disabled = false;
        showLoading(false);
        input.focus();
    }
}

// Handle enter key press
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Update selected node information display
function updateSelectedNodeInfo() {
    const infoDiv = document.getElementById('selectedNodeInfo');
    
    if (!selectedNodeId || !conversationTree.nodes[selectedNodeId]) {
        resetSelectedNodeInfo();
        return;
    }
    
    const node = conversationTree.nodes[selectedNodeId];
    const timestamp = new Date(node.timestamp).toLocaleString();
    const conversationPath = buildConversationPath(selectedNodeId);
    
    let pathHtml = '';
    if (conversationPath.length > 0) {
        pathHtml = '<div class="conversation-path">';
        pathHtml += '<h4>📜 Full Conversation History</h4>';
        pathHtml += '<div class="conversation-count">Showing ' + conversationPath.length + ' conversation' + (conversationPath.length === 1 ? '' : 's') + ' in this path</div>';
        
        conversationPath.forEach((pathNode, index) => {
            if (pathNode.user_input) {
                pathHtml += `<div class="path-message user-msg">
                    <div class="message-header">
                        <strong>👤 You:</strong>
                        <span class="message-time">${new Date(pathNode.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <div class="message-content">${escapeHtml(pathNode.user_input)}</div>
                </div>`;
            }
            if (pathNode.ai_response) {
                const modelUsed = pathNode.model_used || 'Unknown';
                pathHtml += `<div class="path-message ai-msg">
                    <div class="message-header">
                        <strong>🤖 ALM (${modelUsed}):</strong>
                        <span class="message-time">${new Date(pathNode.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <div class="message-content">${renderMarkdown(pathNode.ai_response)}</div>
                </div>`;
            }
        });
        
        pathHtml += '</div>';
    }
    
    const currentNode = conversationTree.nodes[selectedNodeId];
    const hasChildren = currentNode.children && currentNode.children.length > 0;
    const editHistoryHtml = buildEditHistoryHtml(currentNode);
    const isEdited = currentNode.edit_history && currentNode.edit_history.length > 0;
    
    infoDiv.innerHTML = `
        <div class="node-info selected-path">
            <h3>🎯 Selected Branch Point ${isEdited ? '✏️' : ''}</h3>
            <div class="node-details">
                <div class="timestamp">📅 Selected: ${timestamp}</div>
                ${isEdited ? `<div class="edit-indicator">✏️ This node has been edited</div>` : ''}
                <div class="branch-info">
                    ${hasChildren ? 
                        `<div class="existing-branches">⚡ This point has ${currentNode.children.length} existing branch${currentNode.children.length === 1 ? '' : 'es'}</div>` :
                        '<div class="no-branches">💡 No branches from this point yet</div>'
                    }
                </div>
            </div>
            
            <div class="edit-controls">
                <button onclick="startEditMode('${selectedNodeId}')" class="edit-btn" title="Edit this conversation point">
                    ✏️ Edit Node
                </button>
                ${hasChildren ? `
                    <button onclick="showGhostBranchDialog('${selectedNodeId}')" class="ghost-btn" title="Manage ghost branches">
                        👻 Manage Branches
                    </button>
                ` : ''}
            </div>
            
            <div class="instruction-panel">
                <h4>🚀 What happens next?</h4>
                <p>• New messages will continue from this conversation point</p>
                <p>• The AI will have access to all previous context shown below</p>
                <p>• This creates a new branch in your conversation tree</p>
                <p>• <strong>💡 AI responses now support markdown formatting!</strong></p>
                <p>• <strong>✏️ You can edit any node to explore different conversation paths!</strong></p>
            </div>
            
            ${editHistoryHtml}
            ${pathHtml}
            
            <div class="branch-actions">
                <button onclick="startFreshChat()" class="fresh-chat-btn" title="Start completely new conversation">
                    🆕 Start Fresh Chat
                </button>
                <button onclick="clearSelection()" class="clear-selection-btn" title="Deselect current branch point">
                    ❌ Clear Selection
                </button>
            </div>
        </div>
    `;
}

// Build edit history HTML
function buildEditHistoryHtml(node) {
    if (!node.edit_history || node.edit_history.length === 0) {
        return '';
    }
    
    let html = '<div class="edit-history">';
    html += '<h4>📝 Edit History</h4>';
    
    node.edit_history.forEach((edit, index) => {
        const editTime = new Date(edit.timestamp).toLocaleString();
        html += `<div class="edit-entry">
            <div class="edit-timestamp">Edit ${index + 1}: ${editTime}</div>
            ${edit.ghost_created ? `<div class="ghost-info">👻 Created ghost branch: ${edit.ghost_created}</div>` : ''}
        </div>`;
    });
    
    html += '</div>';
    return html;
}

// Start edit mode for a node
function startEditMode(nodeId) {
    if (!nodeId || !conversationTree.nodes[nodeId]) {
        showMessage('Node not found', 'error');
        return;
    }
    
    const node = conversationTree.nodes[nodeId];
    const hasChildren = node.children && node.children.length > 0;
    
    // Show edit modal
    showEditModal(nodeId, node, hasChildren);
}

// Show edit modal
function showEditModal(nodeId, node, hasChildren) {
    const modal = document.createElement('div');
    modal.className = 'edit-modal';
    modal.innerHTML = `
        <div class="modal-overlay" onclick="closeEditModal()"></div>
        <div class="modal-content">
            <div class="modal-header">
                <h3>✏️ Edit Conversation Node</h3>
                <button onclick="closeEditModal()" class="close-btn">✖️</button>
            </div>
            
            <div class="modal-body">
                ${hasChildren ? `
                    <div class="warning-section">
                        <h4>⚠️ Warning: This node has children</h4>
                        <p>Editing this node will affect ${node.children.length} child branch${node.children.length === 1 ? '' : 'es'}.</p>
                        <label class="ghost-option">
                            <input type="checkbox" id="createGhost" checked>
                            Create ghost branch to preserve existing conversations
                        </label>
                    </div>
                ` : ''}
                
                <div class="edit-fields">
                    <div class="field-group">
                        <label for="editUserInput">👤 Your Message:</label>
                        <textarea id="editUserInput" rows="3" placeholder="Edit your message...">${escapeHtml(node.user_input || '')}</textarea>
                    </div>
                    
                    <div class="field-group">
                        <label for="editAiResponse">🤖 AI Response:</label>
                        <textarea id="editAiResponse" rows="5" placeholder="Edit AI response...">${escapeHtml(node.ai_response || '')}</textarea>
                        <small>Supports markdown formatting</small>
                    </div>
                </div>
            </div>
            
            <div class="modal-footer">
                <button onclick="closeEditModal()" class="cancel-btn">Cancel</button>
                <button onclick="saveNodeEdit('${nodeId}')" class="save-btn">💾 Save Changes</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Focus on first textarea
    setTimeout(() => {
        const firstTextarea = modal.querySelector('textarea');
        if (firstTextarea) firstTextarea.focus();
    }, 100);
}

// Close edit modal
function closeEditModal() {
    const modal = document.querySelector('.edit-modal');
    if (modal) {
        modal.remove();
    }
}

// Save node edit
async function saveNodeEdit(nodeId) {
    const userInput = document.getElementById('editUserInput')?.value.trim();
    const aiResponse = document.getElementById('editAiResponse')?.value.trim();
    const createGhost = document.getElementById('createGhost')?.checked || false;
    
    if (!userInput && !aiResponse) {
        showMessage('Please provide at least one field to edit', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/api/node/${nodeId}/edit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_input: userInput,
                ai_response: aiResponse,
                create_ghost: createGhost
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            closeEditModal();
            await loadTree();
            updateSelectedNodeInfo();
            
            let message = 'Node edited successfully! ';
            if (data.ghost_branch_id) {
                message += `Ghost branch created: ${data.ghost_branch_id}`;
            } else if (data.children_removed) {
                message += 'Child branches were removed.';
            }
            
            showMessage(message, 'success');
            
            // Load ghost branches
            loadGhostBranches();
        } else {
            showMessage(data.error || 'Error editing node', 'error');
        }
    } catch (error) {
        console.error('Error editing node:', error);
        showMessage('Error connecting to server', 'error');
    }
}

// Show ghost branch management dialog
function showGhostBranchDialog(nodeId) {
    loadGhostBranches().then(() => {
        const modal = document.createElement('div');
        modal.className = 'ghost-modal';
        
        // Filter ghost branches for this node
        const nodeGhosts = Object.values(ghostBranches).filter(
            ghost => ghost.original_node_id === nodeId
        );
        
        let ghostListHtml = '';
        if (nodeGhosts.length === 0) {
            ghostListHtml = '<p>No ghost branches found for this node.</p>';
        } else {
            ghostListHtml = '<div class="ghost-list">';
            nodeGhosts.forEach(ghost => {
                const createdDate = new Date(ghost.created_at).toLocaleString();
                ghostListHtml += `
                    <div class="ghost-item">
                        <div class="ghost-info">
                            <h5>👻 ${ghost.id}</h5>
                            <p><strong>Created:</strong> ${createdDate}</p>
                            <p><strong>Reason:</strong> ${ghost.reason}</p>
                            <p><strong>Nodes:</strong> ${ghost.node_count}</p>
                            <p><strong>Content:</strong> ${ghost.root_content}</p>
                        </div>
                        <div class="ghost-actions">
                            <button onclick="restoreGhostBranch('${ghost.id}')" class="restore-btn">
                                🔄 Restore
                            </button>
                            <button onclick="deleteGhostBranch('${ghost.id}')" class="delete-ghost-btn">
                                🗑️ Delete
                            </button>
                        </div>
                    </div>
                `;
            });
            ghostListHtml += '</div>';
        }
        
        modal.innerHTML = `
            <div class="modal-overlay" onclick="closeGhostModal()"></div>
            <div class="modal-content ghost-content">
                <div class="modal-header">
                    <h3>👻 Ghost Branch Management</h3>
                    <button onclick="closeGhostModal()" class="close-btn">✖️</button>
                </div>
                
                <div class="modal-body">
                    <p>Ghost branches preserve conversation paths when nodes are edited.</p>
                    ${ghostListHtml}
                </div>
                
                <div class="modal-footer">
                    <button onclick="closeGhostModal()" class="cancel-btn">Close</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
    });
}

// Close ghost modal
function closeGhostModal() {
    const modal = document.querySelector('.ghost-modal');
    if (modal) {
        modal.remove();
    }
}

// Load ghost branches
async function loadGhostBranches() {
    try {
        const response = await fetch('/api/ghost-branches');
        if (response.ok) {
            ghostBranches = await response.json();
        } else {
            console.error('Error loading ghost branches');
        }
    } catch (error) {
        console.error('Error loading ghost branches:', error);
    }
}

// Restore ghost branch
async function restoreGhostBranch(ghostId) {
    if (!confirm('Are you sure you want to restore this ghost branch? This will add its nodes back to the main tree.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/ghost-branches/${ghostId}/restore`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showMessage('Ghost branch restored successfully!', 'success');
            closeGhostModal();
            await loadTree();
            updateSelectedNodeInfo();
            loadGhostBranches();
        } else {
            showMessage(data.error || 'Error restoring ghost branch', 'error');
        }
    } catch (error) {
        console.error('Error restoring ghost branch:', error);
        showMessage('Error connecting to server', 'error');
    }
}

// Delete ghost branch
async function deleteGhostBranch(ghostId) {
    if (!confirm('Are you sure you want to permanently delete this ghost branch? This cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/ghost-branches/${ghostId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showMessage('Ghost branch deleted permanently', 'success');
            closeGhostModal();
            loadGhostBranches();
        } else {
            showMessage(data.error || 'Error deleting ghost branch', 'error');
        }
    } catch (error) {
        console.error('Error deleting ghost branch:', error);
        showMessage('Error connecting to server', 'error');
    }
}

// Reset selected node info to initial state with improved instructions
function resetSelectedNodeInfo() {
    const infoDiv = document.getElementById('selectedNodeInfo');
    infoDiv.innerHTML = `
        <div class="node-info">
            <h3>🌟 Welcome to Visual ALM</h3>
            
            <div class="welcome-section">
                <h4>🚀 Getting Started:</h4>
                <p>• Type a message below to start your first conversation</p>
                <p>• Watch as your conversation grows into a visual tree</p>
                <p>• Click on any node to branch from that point</p>
            </div>
            
            <div class="welcome-section">
                <h4>🎨 Visual Guide:</h4>
                <p>• <span style="color: #28a745;">🟢 Green nodes</span> are your messages</p>
                <p>• <span style="color: #007bff;">🔵 Blue nodes</span> are AI responses</p>
                <p>• Selected nodes have highlighted borders</p>
                <p>• ✨ AI responses support <strong>markdown formatting</strong></p>
            </div>
            
            <div class="welcome-section">
                <h4>⚙️ Status:</h4>
                <p>• Make sure Ollama is running locally</p>
                <p>• Click "Check Ollama" button to verify connection</p>
                <p>• Use "Reset Tree" to start completely fresh</p>
            </div>
            
            <div class="tip-section">
                <p><strong>💡 Pro Tip:</strong> Try different conversation paths to explore how the AI responds differently to various contexts!</p>
                <p><strong>📝 Markdown Support:</strong> AI responses can include headers, lists, code blocks, tables, and more!</p>
            </div>
        </div>
    `;
}

// Start a fresh chat (no parent)
function startFreshChat() {
    selectedNodeId = null;
    resetSelectedNodeInfo();
    updateNetworkView(); // Refresh to remove selection highlighting
    showMessage('Started fresh chat. New messages will start a new conversation.', 'success');
    
    // Focus input
    const input = document.getElementById('messageInput');
    if (input) input.focus();
}

// Clear current selection
function clearSelection() {
    selectedNodeId = null;
    resetSelectedNodeInfo();
    updateNetworkView(); // Refresh to remove selection highlighting
    showMessage('Selection cleared.', 'success');
}

// Show node preview on hover
function showNodePreview(nodeId) {
    // Could implement a tooltip or preview panel here
    console.log('Hovering over node:', nodeId);
}

// Hide node preview
function hideNodePreview() {
    // Hide any preview tooltip or panel
}

// Reset the conversation tree
async function resetTree() {
    if (!confirm('Are you sure you want to reset the entire conversation tree? This cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch('/api/tree/reset', {
            method: 'POST'
        });
        
        if (response.ok) {
            selectedNodeId = null;
            await loadTree();
            resetSelectedNodeInfo();
            showMessage('Conversation tree reset successfully!', 'success');
        } else {
            const data = await response.json();
            showMessage(data.error || 'Error resetting tree', 'error');
        }
    } catch (error) {
        console.error('Error resetting tree:', error);
        showMessage('Error connecting to server', 'error');
    }
}

// Center the view
function centerView() {
    if (network) {
        network.fit();
        showMessage('View centered', 'success');
    }
}

// Show loading indicator
function showLoading(show) {
    document.getElementById('loading').style.display = show ? 'block' : 'none';
}

// Show message to user
function showMessage(message, type) {
    const messagesDiv = document.getElementById('messages');
    
    // Limit number of messages displayed
    while (messagesDiv.children.length >= CONFIG.MAX_DISPLAY_MESSAGES) {
        messagesDiv.removeChild(messagesDiv.firstChild);
    }
    
    const messageEl = document.createElement('div');
    messageEl.className = type;
    messageEl.textContent = message;
    messageEl.style.marginBottom = '8px';
    messageEl.style.padding = '8px 12px';
    messageEl.style.borderRadius = '6px';
    messageEl.style.fontSize = '14px';
    messageEl.style.wordWrap = 'break-word';
    messageEl.style.cursor = 'pointer';
    messageEl.title = 'Click to dismiss';
    
    // Click to dismiss
    messageEl.addEventListener('click', function() {
        if (messageEl.parentNode) {
            messageEl.parentNode.removeChild(messageEl);
        }
    });
    
    messagesDiv.appendChild(messageEl);
    
    // Scroll to bottom to show latest message
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    
    // Auto-remove after delay
    setTimeout(() => {
        if (messageEl.parentNode) {
            messageEl.parentNode.removeChild(messageEl);
        }
    }, CONFIG.MESSAGE_AUTO_REMOVE_DELAY);
}

// Utility function to truncate text
function truncateText(text, maxLength) {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

// Utility function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

// Export conversation tree as JSON
function exportTree() {
    const dataStr = JSON.stringify(conversationTree, null, 2);
    const dataBlob = new Blob([dataStr], {type: 'application/json'});
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `alm_conversation_${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
    showMessage('Conversation tree exported!', 'success');
}

// Initialize resize functionality
function initResize() {
    const resizeHandle = document.getElementById('resizeHandle');
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    
    if (!resizeHandle || !sidebar || !mainContent) {
        console.error('Required elements for resize functionality not found');
        return;
    }
    
    let isResizing = false;
    let startX = 0;
    let startY = 0;
    let startWidth = 0;
    let startHeight = 0;
    let isMobile = window.innerWidth <= 768;
    
    // Check if we're in mobile mode
    function updateMobileMode() {
        isMobile = window.innerWidth <= 768;
    }
    
    // Mouse/Touch down on resize handle
    function startResize(clientX, clientY) {
        isResizing = true;
        startX = clientX;
        startY = clientY;
        
        if (isMobile) {
            startHeight = parseInt(window.getComputedStyle(sidebar).height, 10);
            document.body.style.cursor = 'row-resize';
        } else {
            startWidth = parseInt(window.getComputedStyle(sidebar).width, 10);
            document.body.style.cursor = 'col-resize';
        }
        
        // Prevent text selection during resize
        document.body.style.userSelect = 'none';
        
        // Add visual feedback
        resizeHandle.style.background = '#556bd8';
    }
    
    // Mouse down
    resizeHandle.addEventListener('mousedown', (e) => {
        updateMobileMode();
        startResize(e.clientX, e.clientY);
        e.preventDefault();
    });
    
    // Touch start for mobile
    resizeHandle.addEventListener('touchstart', (e) => {
        updateMobileMode();
        if (e.touches.length === 1) {
            startResize(e.touches[0].clientX, e.touches[0].clientY);
            e.preventDefault();
        }
    });
    
    // Handle resize movement
    function handleResize(clientX, clientY) {
        if (!isResizing) return;
        
        if (isMobile) {
            // Mobile: vertical resize
            const deltaY = clientY - startY;
            const newHeight = startHeight + deltaY;
            const minHeight = 250;
            const maxHeight = window.innerHeight * 0.7; // 70% of viewport
            
            // Constrain height within bounds
            const constrainedHeight = Math.max(minHeight, Math.min(maxHeight, newHeight));
            
            // Update sidebar height
            sidebar.style.height = `${constrainedHeight}px`;
            
            // Update main content height
            const handleHeight = 6;
            const mainContentHeight = window.innerHeight - constrainedHeight - handleHeight;
            mainContent.style.height = `${mainContentHeight}px`;
            
            // Store the current height for persistence
            localStorage.setItem('alm_sidebar_height_mobile', constrainedHeight);
            
        } else {
            // Desktop: horizontal resize
            const deltaX = clientX - startX;
            const newWidth = startWidth + deltaX;
            const minWidth = 250;
            const maxWidth = window.innerWidth * 0.6; // 60% of viewport
            
            // Constrain width within bounds
            const constrainedWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
            
            // Update sidebar width
            sidebar.style.width = `${constrainedWidth}px`;
            
            // Update main content width
            const handleWidth = 6;
            const mainContentWidth = window.innerWidth - constrainedWidth - handleWidth;
            mainContent.style.width = `${mainContentWidth}px`;
            
            // Store the current width for persistence
            localStorage.setItem('alm_sidebar_width', constrainedWidth);
        }
        
        // Resize the network visualization if it exists
        if (network) {
            setTimeout(() => {
                network.redraw();
                network.fit();
            }, 50);
        }
    }
    
    // Mouse move during resize
    document.addEventListener('mousemove', (e) => {
        handleResize(e.clientX, e.clientY);
        if (isResizing) e.preventDefault();
    });
    
    // Touch move for mobile
    document.addEventListener('touchmove', (e) => {
        if (e.touches.length === 1) {
            handleResize(e.touches[0].clientX, e.touches[0].clientY);
            if (isResizing) e.preventDefault();
        }
    });
    
    // End resize
    function endResize() {
        if (!isResizing) return;
        
        isResizing = false;
        
        // Restore normal cursor and selection
        document.body.style.userSelect = '';
        document.body.style.cursor = '';
        resizeHandle.style.background = '';
        
        // Final network resize
        if (network) {
            setTimeout(() => {
                network.redraw();
                network.fit();
            }, 100);
        }
    }
    
    // Mouse up - end resize
    document.addEventListener('mouseup', endResize);
    
    // Touch end for mobile
    document.addEventListener('touchend', endResize);
    
    // Load saved dimensions from localStorage
    function loadSavedDimensions() {
        updateMobileMode();
        
        if (isMobile) {
            const savedHeight = localStorage.getItem('alm_sidebar_height_mobile');
            if (savedHeight) {
                const height = parseInt(savedHeight, 10);
                const minHeight = 250;
                const maxHeight = window.innerHeight * 0.7;
                
                if (height >= minHeight && height <= maxHeight) {
                    sidebar.style.height = `${height}px`;
                    const handleHeight = 6;
                    const mainContentHeight = window.innerHeight - height - handleHeight;
                    mainContent.style.height = `${mainContentHeight}px`;
                }
            }
        } else {
            const savedWidth = localStorage.getItem('alm_sidebar_width');
            if (savedWidth) {
                const width = parseInt(savedWidth, 10);
                const minWidth = 250;
                const maxWidth = window.innerWidth * 0.6;
                
                if (width >= minWidth && width <= maxWidth) {
                    sidebar.style.width = `${width}px`;
                    const handleWidth = 6;
                    const mainContentWidth = window.innerWidth - width - handleWidth;
                    mainContent.style.width = `${mainContentWidth}px`;
                }
            }
        }
    }
    
    // Load initial dimensions
    loadSavedDimensions();
    
    // Handle window resize
    window.addEventListener('resize', () => {
        const wasMobile = isMobile;
        updateMobileMode();
        
        // If switching between mobile and desktop, reset to defaults
        if (wasMobile !== isMobile) {
            sidebar.style.width = '';
            sidebar.style.height = '';
            mainContent.style.width = '';
            mainContent.style.height = '';
            
            // Load appropriate saved dimensions after mode change
            setTimeout(loadSavedDimensions, 100);
        } else {
            // Same mode, just adjust constraints
            if (isMobile) {
                const currentHeight = parseInt(window.getComputedStyle(sidebar).height, 10);
                const maxHeight = window.innerHeight * 0.7;
                
                if (currentHeight > maxHeight) {
                    sidebar.style.height = `${maxHeight}px`;
                    const handleHeight = 6;
                    const mainContentHeight = window.innerHeight - maxHeight - handleHeight;
                    mainContent.style.height = `${mainContentHeight}px`;
                } else {
                    // Recalculate main content height
                    const handleHeight = 6;
                    const mainContentHeight = window.innerHeight - currentHeight - handleHeight;
                    mainContent.style.height = `${mainContentHeight}px`;
                }
            } else {
                const currentWidth = parseInt(window.getComputedStyle(sidebar).width, 10);
                const maxWidth = window.innerWidth * 0.6;
                
                if (currentWidth > maxWidth) {
                    sidebar.style.width = `${maxWidth}px`;
                    const handleWidth = 6;
                    const mainContentWidth = window.innerWidth - maxWidth - handleWidth;
                    mainContent.style.width = `${mainContentWidth}px`;
                } else {
                    // Recalculate main content width
                    const handleWidth = 6;
                    const mainContentWidth = window.innerWidth - currentWidth - handleWidth;
                    mainContent.style.width = `${mainContentWidth}px`;
                }
            }
        }
        
        // Redraw network on window resize
        if (network) {
            setTimeout(() => {
                network.redraw();
                network.fit();
            }, 100);
        }
    });
}

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    console.log('Visual ALM initialized');
    
    // Initialize all components
    initNetwork();
    initResize(); // Add resize functionality
    loadTree();
    loadAvailableModels();
    loadGhostBranches();
    startPeriodicStatusCheck();
    
    // Focus on message input
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.focus();
    }
});

// Global error handler
window.addEventListener('error', function(event) {
    console.error('Global error:', event.error);
    showMessage('An unexpected error occurred. Please refresh the page.', 'error');
});

// Handle page visibility change (pause/resume features)
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        console.log('Page hidden - pausing background tasks');
    } else {
        console.log('Page visible - resuming background tasks');
        checkOllamaStatus(); // Check status when page becomes visible
    }
});

// Make functions available globally for HTML onclick handlers
window.sendMessage = sendMessage;
window.handleKeyPress = handleKeyPress;
window.resetTree = resetTree;
window.centerView = centerView;
window.checkOllamaStatus = checkOllamaStatus;
window.exportTree = exportTree;
window.startFreshChat = startFreshChat;
window.clearSelection = clearSelection;
window.handleModelChange = handleModelChange;
window.startEditMode = startEditMode;
window.closeEditModal = closeEditModal;
window.saveNodeEdit = saveNodeEdit;
window.showGhostBranchDialog = showGhostBranchDialog;
window.closeGhostModal = closeGhostModal;
window.restoreGhostBranch = restoreGhostBranch;
window.deleteGhostBranch = deleteGhostBranch;

// Load available models from server
async function loadAvailableModels() {
    try {
        updateModelStatus('loading', 'Loading models...');
        
        const response = await fetch('/api/models');
        const data = await response.json();
        
        if (response.ok && data.models) {
            availableModels = data.models;
            populateModelDropdown(data.models, data.default_model);
            updateModelStatus('success', `${data.models.length} models available`);
            
            // Load saved model selection or use default
            const savedModel = localStorage.getItem(CONFIG.MODEL_STORAGE_KEY);
            if (savedModel && data.models.some(m => m.name === savedModel)) {
                selectedModel = savedModel;
                document.getElementById('modelSelect').value = savedModel;
            } else {
                selectedModel = data.default_model;
                document.getElementById('modelSelect').value = data.default_model;
            }
            
            showMessage(`✅ Loaded ${data.models.length} available models`, 'success');
        } else {
            updateModelStatus('error', 'Failed to load models');
            showMessage('❌ Could not load available models', 'error');
        }
    } catch (error) {
        console.error('Error loading models:', error);
        updateModelStatus('error', 'Error loading models');
        showMessage('❌ Error connecting to server for models', 'error');
    }
}

// Populate the model dropdown
function populateModelDropdown(models, defaultModel) {
    const select = document.getElementById('modelSelect');
    select.innerHTML = '';
    
    if (models.length === 0) {
        select.innerHTML = '<option value="">No models available</option>';
        select.disabled = true;
        return;
    }
    
    // Add models to dropdown
    models.forEach(model => {
        const option = document.createElement('option');
        option.value = model.name;
        
        // Format display text with size info
        const sizeStr = formatModelSize(model.size);
        option.textContent = `${model.name}${sizeStr ? ` (${sizeStr})` : ''}`;
        
        // Mark default model
        if (model.name === defaultModel) {
            option.textContent += ' [Default]';
        }
        
        select.appendChild(option);
    });
    
    select.disabled = false;
}

// Format model size for display
function formatModelSize(bytes) {
    if (!bytes || bytes === 0) return '';
    
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    const size = (bytes / Math.pow(1024, i)).toFixed(1);
    
    return `${size}${sizes[i]}`;
}

// Handle model selection change
function handleModelChange() {
    const select = document.getElementById('modelSelect');
    const newModel = select.value;
    
    if (newModel && newModel !== selectedModel) {
        selectedModel = newModel;
        
        // Save to localStorage
        localStorage.setItem(CONFIG.MODEL_STORAGE_KEY, newModel);
        
        // Show confirmation
        const modelInfo = availableModels.find(m => m.name === newModel);
        const sizeStr = modelInfo ? ` (${formatModelSize(modelInfo.size)})` : '';
        showMessage(`🤖 Switched to model: ${newModel}${sizeStr}`, 'success');
        
        updateModelStatus('success', 'Model selected');
        
        logger.info && logger.info(`Model changed to: ${newModel}`);
    }
}

// Update model status indicator
function updateModelStatus(status, title) {
    const statusEl = document.getElementById('modelStatus');
    
    // Remove all status classes
    statusEl.classList.remove('loading', 'success', 'error');
    
    switch (status) {
        case 'loading':
            statusEl.classList.add('loading');
            statusEl.textContent = '🔄';
            statusEl.title = title || 'Loading...';
            break;
        case 'success':
            statusEl.classList.add('success');
            statusEl.textContent = '✅';
            statusEl.title = title || 'Models loaded successfully';
            break;
        case 'error':
            statusEl.classList.add('error');
            statusEl.textContent = '❌';
            statusEl.title = title || 'Error loading models';
            break;
        default:
            statusEl.textContent = '🔄';
            statusEl.title = 'Unknown status';
    }
}

// Initialize voice functionality
function initVoice() {
    // Initialize Speech Synthesis
    if ('speechSynthesis' in window) {
        speechSynthesis = window.speechSynthesis;
        loadVoices();
        
        // Load voices when they become available
        speechSynthesis.onvoiceschanged = loadVoices;
    } else {
        console.warn('Speech Synthesis not supported');
        showMessage('⚠️ Text-to-speech not supported in this browser', 'error');
    }
    
    // Initialize Speech Recognition
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        speechRecognition = new SpeechRecognition();
        
        speechRecognition.continuous = false;
        speechRecognition.interimResults = false;
        speechRecognition.lang = 'en-US';
        
        speechRecognition.onstart = function() {
            console.log('Speech recognition started');
            isListening = true;
            updateMicButtonState();
            showVoiceIndicator(true);
        };
        
        speechRecognition.onresult = function(event) {
            const transcript = event.results[0][0].transcript;
            console.log('Speech recognition result:', transcript);
            
            // Put the recognized text in the input field
            const input = document.getElementById('messageInput');
            input.value = transcript;
            
            showMessage(`🎙️ Heard: "${transcript}"`, 'success');
            
            // Auto-send if voice mode is enabled
            if (voiceModeEnabled) {
                setTimeout(() => {
                    sendMessage();
                }, 500); // Small delay to show the recognized text
            }
        };
        
        speechRecognition.onerror = function(event) {
            console.error('Speech recognition error:', event.error);
            let errorMsg = 'Speech recognition error';
            
            switch (event.error) {
                case 'no-speech':
                    errorMsg = 'No speech detected. Try speaking louder.';
                    break;
                case 'audio-capture':
                    errorMsg = 'Microphone not accessible. Check permissions.';
                    break;
                case 'not-allowed':
                    errorMsg = 'Microphone permission denied.';
                    break;
                case 'network':
                    errorMsg = 'Network error during speech recognition.';
                    break;
                default:
                    errorMsg = `Speech recognition error: ${event.error}`;
            }
            
            showMessage(`🎙️ ${errorMsg}`, 'error');
        };
        
        speechRecognition.onend = function() {
            console.log('Speech recognition ended');
            isListening = false;
            updateMicButtonState();
            showVoiceIndicator(false);
        };
    } else {
        console.warn('Speech Recognition not supported');
        showMessage('⚠️ Speech recognition not supported in this browser', 'error');
    }
    
    // Load saved voice settings
    loadVoiceSettings();
    
    // Initialize voice controls event listeners
    initVoiceControls();
}

// Load available voices
function loadVoices() {
    if (!speechSynthesis) return;
    
    availableVoices = speechSynthesis.getVoices();
    const voiceSelect = document.getElementById('voiceSelect');
    
    if (voiceSelect && availableVoices.length > 0) {
        voiceSelect.innerHTML = '';
        
        // Group voices by language for better UX
        const englishVoices = availableVoices.filter(voice => voice.lang.startsWith('en'));
        const otherVoices = availableVoices.filter(voice => !voice.lang.startsWith('en'));
        
        if (englishVoices.length > 0) {
            const englishGroup = document.createElement('optgroup');
            englishGroup.label = 'English Voices';
            
            englishVoices.forEach(voice => {
                const option = document.createElement('option');
                option.value = voice.name;
                option.textContent = `${voice.name} (${voice.lang})${voice.default ? ' [Default]' : ''}`;
                englishGroup.appendChild(option);
            });
            
            voiceSelect.appendChild(englishGroup);
        }
        
        if (otherVoices.length > 0) {
            const otherGroup = document.createElement('optgroup');
            otherGroup.label = 'Other Languages';
            
            otherVoices.forEach(voice => {
                const option = document.createElement('option');
                option.value = voice.name;
                option.textContent = `${voice.name} (${voice.lang})`;
                otherGroup.appendChild(option);
            });
            
            voiceSelect.appendChild(otherGroup);
        }
        
        // Set default voice if none selected
        if (!selectedVoice && englishVoices.length > 0) {
            const defaultVoice = englishVoices.find(voice => voice.default) || englishVoices[0];
            selectedVoice = defaultVoice.name;
            voiceSelect.value = selectedVoice;
        }
        
        console.log(`Loaded ${availableVoices.length} voices`);
    }
}

// Initialize voice control event listeners
function initVoiceControls() {
    // Rate control
    const rateSlider = document.getElementById('speechRate');
    const rateValue = document.getElementById('rateValue');
    if (rateSlider && rateValue) {
        rateSlider.addEventListener('input', function() {
            rateValue.textContent = parseFloat(this.value).toFixed(1);
            saveVoiceSettings();
        });
    }
    
    // Pitch control
    const pitchSlider = document.getElementById('speechPitch');
    const pitchValue = document.getElementById('pitchValue');
    if (pitchSlider && pitchValue) {
        pitchSlider.addEventListener('input', function() {
            pitchValue.textContent = parseFloat(this.value).toFixed(1);
            saveVoiceSettings();
        });
    }
    
    // Auto TTS checkbox
    const autoTTSCheckbox = document.getElementById('autoTTS');
    if (autoTTSCheckbox) {
        autoTTSCheckbox.addEventListener('change', saveVoiceSettings);
    }
    
    // Auto STT checkbox
    const autoSTTCheckbox = document.getElementById('autoSTT');
    if (autoSTTCheckbox) {
        autoSTTCheckbox.addEventListener('change', function() {
            voiceModeEnabled = this.checked;
            updateVoiceModeButton();
            saveVoiceSettings();
        });
    }
}

// Save voice settings to localStorage
function saveVoiceSettings() {
    const settings = {
        autoTTS: document.getElementById('autoTTS')?.checked || VOICE_DEFAULTS.autoTTS,
        autoSTT: document.getElementById('autoSTT')?.checked || VOICE_DEFAULTS.autoSTT,
        rate: parseFloat(document.getElementById('speechRate')?.value || VOICE_DEFAULTS.rate),
        pitch: parseFloat(document.getElementById('speechPitch')?.value || VOICE_DEFAULTS.pitch),
        voice: document.getElementById('voiceSelect')?.value || VOICE_DEFAULTS.voice
    };
    
    localStorage.setItem(CONFIG.VOICE_SETTINGS_KEY, JSON.stringify(settings));
}

// Load voice settings from localStorage
function loadVoiceSettings() {
    try {
        const saved = localStorage.getItem(CONFIG.VOICE_SETTINGS_KEY);
        const settings = saved ? JSON.parse(saved) : VOICE_DEFAULTS;
        
        // Apply settings to UI elements
        const autoTTSCheckbox = document.getElementById('autoTTS');
        if (autoTTSCheckbox) autoTTSCheckbox.checked = settings.autoTTS;
        
        const autoSTTCheckbox = document.getElementById('autoSTT');
        if (autoSTTCheckbox) {
            autoSTTCheckbox.checked = settings.autoSTT;
            voiceModeEnabled = settings.autoSTT;
        }
        
        const rateSlider = document.getElementById('speechRate');
        const rateValue = document.getElementById('rateValue');
        if (rateSlider && rateValue) {
            rateSlider.value = settings.rate;
            rateValue.textContent = settings.rate.toFixed(1);
        }
        
        const pitchSlider = document.getElementById('speechPitch');
        const pitchValue = document.getElementById('pitchValue');
        if (pitchSlider && pitchValue) {
            pitchSlider.value = settings.pitch;
            pitchValue.textContent = settings.pitch.toFixed(1);
        }
        
        const voiceSelect = document.getElementById('voiceSelect');
        if (voiceSelect && settings.voice) {
            selectedVoice = settings.voice;
            voiceSelect.value = settings.voice;
        }
        
        updateVoiceModeButton();
    } catch (error) {
        console.error('Error loading voice settings:', error);
    }
}

// Handle voice selection change
function handleVoiceChange() {
    const voiceSelect = document.getElementById('voiceSelect');
    if (voiceSelect) {
        selectedVoice = voiceSelect.value;
        saveVoiceSettings();
        showMessage(`🔊 Voice changed to: ${selectedVoice}`, 'success');
    }
}

// Test TTS functionality
function testTTS() {
    const testText = "Hello! This is a test of the text to speech functionality. The AI can now speak to you!";
    speakText(testText, true); // Force speak even if auto TTS is off
}

// Speak text using TTS
function speakText(text, forceSpeak = false) {
    if (!speechSynthesis) {
        console.warn('Speech synthesis not available');
        return false;
    }
    
    // Check if auto TTS is enabled or forced
    const autoTTSEnabled = document.getElementById('autoTTS')?.checked || false;
    if (!autoTTSEnabled && !forceSpeak) {
        return false;
    }
    
    // Stop any current speech
    stopTTS();
    
    // Truncate very long text
    let textToSpeak = text;
    if (text.length > CONFIG.TTS_MAX_LENGTH) {
        textToSpeak = text.substring(0, CONFIG.TTS_MAX_LENGTH) + "... [message truncated]";
        showMessage('📢 Long message truncated for speech', 'info');
    }
    
    // Remove markdown syntax for better speech
    textToSpeak = cleanTextForSpeech(textToSpeak);
    
    if (!textToSpeak.trim()) {
        return false;
    }
    
    try {
        currentUtterance = new SpeechSynthesisUtterance(textToSpeak);
        
        // Set voice if available
        if (selectedVoice && availableVoices.length > 0) {
            const voice = availableVoices.find(v => v.name === selectedVoice);
            if (voice) {
                currentUtterance.voice = voice;
            }
        }
        
        // Set speech parameters
        currentUtterance.rate = parseFloat(document.getElementById('speechRate')?.value || 1.0);
        currentUtterance.pitch = parseFloat(document.getElementById('speechPitch')?.value || 1.0);
        currentUtterance.volume = 1.0;
        
        // Set up event handlers
        currentUtterance.onstart = function() {
            isSpeaking = true;
            updateTTSButtonState();
            console.log('Started speaking:', textToSpeak.substring(0, 50) + '...');
            
            // Add visual indicator to the AI message
            addSpeakingIndicator();
        };
        
        currentUtterance.onend = function() {
            isSpeaking = false;
            currentUtterance = null;
            updateTTSButtonState();
            console.log('Finished speaking');
            
            // Remove visual indicator
            removeSpeakingIndicator();
        };
        
        currentUtterance.onerror = function(event) {
            console.error('Speech synthesis error:', event.error);
            isSpeaking = false;
            currentUtterance = null;
            updateTTSButtonState();
            removeSpeakingIndicator();
            showMessage('🔊 Speech synthesis error', 'error');
        };
        
        // Start speaking
        speechSynthesis.speak(currentUtterance);
        return true;
        
    } catch (error) {
        console.error('Error in speech synthesis:', error);
        showMessage('🔊 Error starting speech synthesis', 'error');
        return false;
    }
}

// Clean text for better speech synthesis
function cleanTextForSpeech(text) {
    return text
        // Remove markdown code blocks
        .replace(/```[\s\S]*?```/g, '[code block]')
        // Remove inline code
        .replace(/`([^`]+)`/g, '$1')
        // Remove markdown links
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
        // Remove markdown headers
        .replace(/^#{1,6}\s+/gm, '')
        // Remove markdown emphasis
        .replace(/\*\*([^*]+)\*\*/g, '$1')
        .replace(/\*([^*]+)\*/g, '$1')
        .replace(/__([^_]+)__/g, '$1')
        .replace(/_([^_]+)_/g, '$1')
        // Remove markdown lists
        .replace(/^\s*[-*+]\s+/gm, '')
        .replace(/^\s*\d+\.\s+/gm, '')
        // Clean up extra whitespace
        .replace(/\n\s*\n/g, '. ')
        .replace(/\s+/g, ' ')
        .trim();
}

// Stop TTS
function stopTTS() {
    if (speechSynthesis && isSpeaking) {
        speechSynthesis.cancel();
        isSpeaking = false;
        currentUtterance = null;
        updateTTSButtonState();
        removeSpeakingIndicator();
        console.log('Speech synthesis stopped');
    }
}

// Toggle voice input mode
function toggleVoiceMode() {
    voiceModeEnabled = !voiceModeEnabled;
    const autoSTTCheckbox = document.getElementById('autoSTT');
    if (autoSTTCheckbox) {
        autoSTTCheckbox.checked = voiceModeEnabled;
    }
    updateVoiceModeButton();
    saveVoiceSettings();
    
    const status = voiceModeEnabled ? 'ON' : 'OFF';
    showMessage(`🎙️ Voice Mode: ${status}`, 'success');
}

// Update voice mode button appearance
function updateVoiceModeButton() {
    const button = document.getElementById('voiceModeBtn');
    if (button) {
        if (voiceModeEnabled) {
            button.textContent = '🎙️ Voice Mode: ON';
            button.classList.remove('voice-mode-inactive');
            button.classList.add('voice-mode-active');
        } else {
            button.textContent = '🎙️ Voice Mode: OFF';
            button.classList.remove('voice-mode-active');
            button.classList.add('voice-mode-inactive');
        }
    }
}

// Toggle listening state
function toggleListening() {
    if (!speechRecognition) {
        showMessage('🎙️ Speech recognition not supported', 'error');
        return;
    }
    
    if (isListening) {
        speechRecognition.stop();
    } else {
        try {
            speechRecognition.start();
        } catch (error) {
            console.error('Error starting speech recognition:', error);
            showMessage('🎙️ Error starting speech recognition', 'error');
        }
    }
}

// Update microphone button state
function updateMicButtonState() {
    const micButton = document.getElementById('micButton');
    if (micButton) {
        if (isListening) {
            micButton.classList.add('recording');
            micButton.title = 'Stop listening';
            micButton.textContent = '🔴';
        } else {
            micButton.classList.remove('recording');
            micButton.title = 'Start voice input';
            micButton.textContent = '🎙️';
        }
    }
}

// Update TTS button state
function updateTTSButtonState() {
    const stopButton = document.getElementById('stopTTSButton');
    if (stopButton) {
        if (isSpeaking) {
            stopButton.style.display = 'inline-block';
        } else {
            stopButton.style.display = 'none';
        }
    }
}

// Show/hide voice indicator
function showVoiceIndicator(show) {
    const indicator = document.getElementById('voiceIndicator');
    if (indicator) {
        indicator.style.display = show ? 'flex' : 'none';
    }
}

// Add speaking indicator to AI messages
function addSpeakingIndicator() {
    // Find the most recent AI message and add speaking indicator
    const aiMessages = document.querySelectorAll('.ai-msg');
    if (aiMessages.length > 0) {
        const lastAiMessage = aiMessages[aiMessages.length - 1];
        lastAiMessage.classList.add('tts-speaking');
    }
}

// Remove speaking indicator from AI messages
function removeSpeakingIndicator() {
    const speakingMessages = document.querySelectorAll('.tts-speaking');
    speakingMessages.forEach(msg => msg.classList.remove('tts-speaking'));
}