// Visual ALM - Client-side JavaScript
// Author: ALM Developer
// Version: 1.0.0

// Global variables
let network;
let selectedNodeId = null;
let conversationTree = { nodes: {}, root_id: null };
let ollamaConnected = false;

// Configuration
const CONFIG = {
    MAX_MESSAGE_LENGTH: 5000,
    MAX_DISPLAY_MESSAGES: 10,
    MESSAGE_AUTO_REMOVE_DELAY: 8000,
    STATUS_CHECK_INTERVAL: 30000, // Check Ollama status every 30 seconds
    NODE_LABEL_MAX_LENGTH: 30
};

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
        updateNetworkView();
    } catch (error) {
        console.error('Error loading tree:', error);
        showMessage('Error loading conversation tree', 'error');
    }
}

// Update the network visualization
function updateNetworkView() {
    const nodes = [];
    const edges = [];
    
    for (const [nodeId, node] of Object.entries(conversationTree.nodes)) {
        // Create node for user message
        if (node.user_input) {
            const isSelected = selectedNodeId === nodeId;
            nodes.push({
                id: nodeId + '_user',
                label: truncateText(node.user_input, CONFIG.NODE_LABEL_MAX_LENGTH),
                color: {
                    background: isSelected ? '#c3e6cb' : '#d4edda',
                    border: isSelected ? '#1e7e34' : '#28a745',
                    highlight: {
                        background: '#c3e6cb',
                        border: '#1e7e34'
                    }
                },
                title: `You: ${escapeHtml(node.user_input)}\n\nClick to branch from this point`,
                font: { 
                    multi: true,
                    bold: isSelected
                },
                borderWidth: isSelected ? 4 : 2,
                shadow: isSelected ? { enabled: true, size: 10, x: 0, y: 0 } : true,
                nodeData: { type: 'user', nodeId: nodeId, content: node.user_input }
            });
        }
        
        // Create node for AI response
        if (node.ai_response) {
            const isSelected = selectedNodeId === nodeId;
            nodes.push({
                id: nodeId + '_ai',
                label: truncateText(node.ai_response, CONFIG.NODE_LABEL_MAX_LENGTH),
                color: {
                    background: isSelected ? '#b3d7ff' : '#cce5ff',
                    border: isSelected ? '#0056b3' : '#007bff',
                    highlight: {
                        background: '#b3d7ff',
                        border: '#0056b3'
                    }
                },
                title: `ALM: ${escapeHtml(node.ai_response)}\n\nClick to branch from this point`,
                font: { 
                    multi: true,
                    bold: isSelected
                },
                borderWidth: isSelected ? 4 : 2,
                shadow: isSelected ? { enabled: true, size: 10, x: 0, y: 0 } : true,
                nodeData: { type: 'ai', nodeId: nodeId, content: node.ai_response }
            });
            
            // Connect user message to AI response
            if (node.user_input) {
                edges.push({
                    from: nodeId + '_user',
                    to: nodeId + '_ai',
                    color: { color: selectedNodeId === nodeId ? '#1e7e34' : '#28a745' },
                    width: selectedNodeId === nodeId ? 4 : 2
                });
            }
        }
        
        // Connect to parent
        if (node.parent_id && conversationTree.nodes[node.parent_id]) {
            const isOnSelectedPath = isNodeOnPath(nodeId, selectedNodeId);
            edges.push({
                from: node.parent_id + '_ai',
                to: nodeId + '_user',
                color: { color: isOnSelectedPath ? '#0056b3' : '#007bff' },
                width: isOnSelectedPath ? 4 : 2
            });
        }
    }
    
    // Add branch point indicator if a node is selected
    if (selectedNodeId && conversationTree.nodes[selectedNodeId]) {
        const branchNode = conversationTree.nodes[selectedNodeId];
        
        // Add a visual branch point indicator
        nodes.push({
            id: 'branch_point_indicator',
            label: '📍 BRANCH\nPOINT',
            color: {
                background: '#ffd700',
                border: '#ff8c00'
            },
            shape: 'diamond',
            size: 30,
            font: {
                size: 10,
                color: '#333',
                face: 'Segoe UI',
                multi: true
            },
            borderWidth: 3,
            shadow: {
                enabled: true,
                size: 15,
                x: 0,
                y: 0,
                color: 'rgba(255, 140, 0, 0.5)'
            },
            title: 'New messages will branch from here'
        });
        
        // Connect branch point to selected node
        const targetNodeId = branchNode.ai_response ? selectedNodeId + '_ai' : selectedNodeId + '_user';
        edges.push({
            from: targetNodeId,
            to: 'branch_point_indicator',
            color: { color: '#ff8c00' },
            width: 3,
            dashes: [10, 5],
            arrows: 'to',
            title: 'Branch point connection'
        });
        
        // Add potential new message preview
        nodes.push({
            id: 'new_message_preview',
            label: '💬 Your next\nmessage will\nappear here',
            color: {
                background: 'rgba(212, 237, 218, 0.7)',
                border: 'rgba(40, 167, 69, 0.7)'
            },
            shape: 'box',
            font: {
                size: 9,
                color: '#666',
                face: 'Segoe UI',
                multi: true
            },
            borderWidth: 2,
            borderWidthSelected: 2,
            opacity: 0.8,
            title: 'Type a message and send to create this branch'
        });
        
        // Connect branch point to new message preview
        edges.push({
            from: 'branch_point_indicator',
            to: 'new_message_preview',
            color: { color: 'rgba(255, 140, 0, 0.7)' },
            width: 2,
            dashes: [5, 5],
            arrows: 'to',
            title: 'New conversation branch'
        });
    }
    
    network.setData({ nodes: nodes, edges: edges });
    
    // Auto-fit if there are nodes
    if (nodes.length > 0) {
        setTimeout(() => network.fit(), 100);
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
                parent_id: selectedNodeId
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            input.value = '';
            selectedNodeId = data.node_id;
            await loadTree();
            updateSelectedNodeInfo();
            showMessage('Message sent successfully!', 'success');
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
                pathHtml += `<div class="path-message ai-msg">
                    <div class="message-header">
                        <strong>🤖 ALM:</strong>
                        <span class="message-time">${new Date(pathNode.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <div class="message-content">${escapeHtml(pathNode.ai_response)}</div>
                </div>`;
            }
        });
        
        pathHtml += '</div>';
    }
    
    const currentNode = conversationTree.nodes[selectedNodeId];
    const hasChildren = currentNode.children && currentNode.children.length > 0;
    
    infoDiv.innerHTML = `
        <div class="node-info selected-path">
            <h3>🎯 Selected Branch Point</h3>
            <div class="node-details">
                <div class="timestamp">📅 Selected: ${timestamp}</div>
                <div class="branch-info">
                    ${hasChildren ? 
                        `<div class="existing-branches">⚡ This point has ${currentNode.children.length} existing branch${currentNode.children.length === 1 ? '' : 'es'}</div>` :
                        '<div class="no-branches">💡 No branches from this point yet</div>'
                    }
                </div>
            </div>
            
            <div class="instruction-panel">
                <h4>🚀 What happens next?</h4>
                <p>• New messages will continue from this conversation point</p>
                <p>• The AI will have access to all previous context shown below</p>
                <p>• This creates a new branch in your conversation tree</p>
            </div>
            
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
            </div>
            
            <div class="welcome-section">
                <h4>⚙️ Status:</h4>
                <p>• Make sure Ollama is running locally</p>
                <p>• Click "Check Ollama" button to verify connection</p>
                <p>• Use "Reset Tree" to start completely fresh</p>
            </div>
            
            <div class="tip-section">
                <p><strong>💡 Pro Tip:</strong> Try different conversation paths to explore how the AI responds differently to various contexts!</p>
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

// Initialize everything when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('Visual ALM starting up...');
    
    initNetwork();
    loadTree();
    checkOllamaStatus();
    startPeriodicStatusCheck();
    
    // Focus on input field
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.focus();
    }
    
    // Show welcome message
    setTimeout(() => {
        showMessage('Welcome to Visual ALM! 🚀', 'success');
    }, 500);
    
    // Add keyboard shortcuts
    document.addEventListener('keydown', function(event) {
        // Ctrl/Cmd + Enter to send message
        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
            sendMessage();
        }
        
        // Escape to clear input
        if (event.key === 'Escape') {
            const input = document.getElementById('messageInput');
            if (input) {
                input.value = '';
                input.focus();
            }
        }
    });
    
    console.log('Visual ALM initialized successfully!');
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