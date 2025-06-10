#!/usr/bin/env python3

from flask import Flask, render_template, request, jsonify
import json
import os
import datetime
import requests
import logging
from typing import Dict, List, Any, Optional
import uuid
import copy

# Import our existing ALM functionality
from main import (
    query_ollama, ALMError, OllamaConnectionError, MemoryError,
    OLLAMA_MODEL, OLLAMA_URL, REQUEST_TIMEOUT
)

app = Flask(__name__)

# Configure logging for the web app
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('alm_web.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Enhanced memory structure for conversation trees
TREE_MEMORY_FILE = "alm_tree_memory.json"
GHOST_BRANCH_FILE = "alm_ghost_branches.json"

class TreeMemoryManager:
    def __init__(self):
        self.tree = self.load_tree()
        self.ghost_branches = self.load_ghost_branches()
    
    def load_tree(self) -> Dict[str, Any]:
        """Load conversation tree from file"""
        if os.path.exists(TREE_MEMORY_FILE):
            try:
                with open(TREE_MEMORY_FILE, 'r', encoding='utf-8') as f:
                    tree_data = json.load(f)
                    # Ensure required structure
                    if 'nodes' not in tree_data:
                        tree_data['nodes'] = {}
                    if 'root_id' not in tree_data:
                        tree_data['root_id'] = None
                    return tree_data
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading tree memory: {e}")
        
        # Return empty tree structure
        return {
            'nodes': {},
            'root_id': None
        }
    
    def load_ghost_branches(self) -> Dict[str, Any]:
        """Load ghost branches from file"""
        if os.path.exists(GHOST_BRANCH_FILE):
            try:
                with open(GHOST_BRANCH_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading ghost branches: {e}")
        return {}
    
    def save_tree(self):
        """Save conversation tree to file"""
        try:
            with open(TREE_MEMORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.tree, f, indent=2, ensure_ascii=False)
            logger.info("Tree memory saved successfully")
        except IOError as e:
            logger.error(f"Error saving tree memory: {e}")
    
    def save_ghost_branches(self):
        """Save ghost branches to file"""
        try:
            with open(GHOST_BRANCH_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.ghost_branches, f, indent=2, ensure_ascii=False)
            logger.info("Ghost branches saved successfully")
        except IOError as e:
            logger.error(f"Error saving ghost branches: {e}")
    
    def create_ghost_branch(self, node_id: str, reason: str = "Node edited") -> str:
        """Create a ghost branch from a node and its descendants"""
        if node_id not in self.tree['nodes']:
            raise ValueError(f"Node {node_id} not found")
        
        # Generate unique ghost ID
        ghost_id = f"ghost_{uuid.uuid4().hex[:8]}"
        
        # Deep copy the subtree starting from this node
        ghost_nodes = self._copy_subtree(node_id)
        
        # Count nodes and get root content for display
        node_count = len(ghost_nodes)
        root_node = self.tree['nodes'][node_id]
        root_content = (root_node.get('user_input', '') or root_node.get('ai_response', ''))[:50]
        if len(root_content) > 50:
            root_content += "..."
        
        # Create ghost branch metadata
        ghost_branch = {
            'id': ghost_id,
            'original_node_id': node_id,
            'created_at': datetime.datetime.now().isoformat(),
            'reason': reason,
            'nodes': ghost_nodes,
            'node_count': node_count,
            'root_content': root_content
        }
        
        # Save ghost branch
        self.ghost_branches[ghost_id] = ghost_branch
        self.save_ghost_branches()
        
        logger.info(f"Created ghost branch {ghost_id} from node {node_id} with {node_count} nodes")
        return ghost_id
    
    def _copy_subtree(self, node_id: str) -> Dict[str, Any]:
        """Recursively copy a subtree starting from node_id"""
        subtree = {}
        
        def copy_node_recursive(current_id: str):
            if current_id not in self.tree['nodes']:
                return
            
            # Deep copy the node
            node = copy.deepcopy(self.tree['nodes'][current_id])
            subtree[current_id] = node
            
            # Recursively copy children
            if 'children' in node and node['children']:
                for child_id in node['children']:
                    copy_node_recursive(child_id)
        
        copy_node_recursive(node_id)
        return subtree
    
    def remove_subtree(self, node_id: str):
        """Remove a subtree starting from node_id"""
        def remove_recursive(current_id: str):
            if current_id not in self.tree['nodes']:
                return
            
            node = self.tree['nodes'][current_id]
            
            # Recursively remove children first
            if 'children' in node and node['children']:
                for child_id in list(node['children']):  # Use list() to avoid iteration issues
                    remove_recursive(child_id)
            
            # Remove this node
            del self.tree['nodes'][current_id]
        
        # Remove all children but keep the node itself
        node = self.tree['nodes'].get(node_id)
        if node and 'children' in node and node['children']:
            for child_id in list(node['children']):
                remove_recursive(child_id)
            node['children'] = []
    
    def edit_node(self, node_id: str, user_input: str = None, ai_response: str = None, 
                  create_ghost: bool = False) -> Dict[str, Any]:
        """Edit a node's content and optionally create ghost branches"""
        if node_id not in self.tree['nodes']:
            raise ValueError(f"Node {node_id} not found")
        
        node = self.tree['nodes'][node_id]
        result = {}
        
        # Check if node has children
        has_children = 'children' in node and node['children']
        
        # Create ghost branch if requested and node has children
        ghost_branch_id = None
        if create_ghost and has_children:
            ghost_branch_id = self.create_ghost_branch(node_id, "Node edited - preserving children")
            result['ghost_branch_id'] = ghost_branch_id
        
        # Remove children if not creating ghost branch
        children_removed = False
        if has_children and not create_ghost:
            self.remove_subtree(node_id)
            children_removed = True
            result['children_removed'] = True
        elif has_children and create_ghost:
            # Still remove children from main tree after creating ghost
            self.remove_subtree(node_id)
        
        # Update node content
        if user_input is not None:
            node['user_input'] = user_input
        
        if ai_response is not None:
            node['ai_response'] = ai_response
        
        # Add edit history
        if 'edit_history' not in node:
            node['edit_history'] = []
        
        edit_entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'ghost_created': ghost_branch_id if ghost_branch_id else None
        }
        node['edit_history'].append(edit_entry)
        
        # Update timestamp
        node['timestamp'] = datetime.datetime.now().isoformat()
        
        # Save changes
        self.save_tree()
        
        logger.info(f"Edited node {node_id}, ghost: {ghost_branch_id}, children removed: {children_removed}")
        return result
    
    def restore_ghost_branch(self, ghost_id: str) -> bool:
        """Restore a ghost branch back to the main tree"""
        if ghost_id not in self.ghost_branches:
            raise ValueError(f"Ghost branch {ghost_id} not found")
        
        ghost_branch = self.ghost_branches[ghost_id]
        original_node_id = ghost_branch['original_node_id']
        
        # Check if original node still exists
        if original_node_id not in self.tree['nodes']:
            raise ValueError(f"Original node {original_node_id} no longer exists")
        
        # Add ghost nodes back to main tree
        ghost_nodes = ghost_branch['nodes']
        
        # First, add all nodes
        for ghost_node_id, ghost_node in ghost_nodes.items():
            if ghost_node_id not in self.tree['nodes']:
                self.tree['nodes'][ghost_node_id] = ghost_node
        
        # Then, restore the parent-child relationship for the root node
        original_node = self.tree['nodes'][original_node_id]
        if 'children' not in original_node:
            original_node['children'] = []
        
        # Find the children that should be restored to the original node
        for ghost_node_id, ghost_node in ghost_nodes.items():
            # If this ghost node was a direct child of the original node
            if ghost_node_id in ghost_nodes and ghost_node_id != original_node_id:
                # Check if it should be a direct child by seeing if it was in original children
                if ghost_node_id not in original_node['children']:
                    original_node['children'].append(ghost_node_id)
        
        # Save changes
        self.save_tree()
        
        logger.info(f"Restored ghost branch {ghost_id} to main tree")
        return True
    
    def delete_ghost_branch(self, ghost_id: str) -> bool:
        """Permanently delete a ghost branch"""
        if ghost_id not in self.ghost_branches:
            raise ValueError(f"Ghost branch {ghost_id} not found")
        
        del self.ghost_branches[ghost_id]
        self.save_ghost_branches()
        
        logger.info(f"Deleted ghost branch {ghost_id}")
        return True
    
    def add_conversation(self, parent_id: Optional[str], user_input: str, 
                        ai_response: str, model_used: str) -> str:
        """Add a new conversation to the tree"""
        node_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().isoformat()
        
        node = {
            'id': node_id,
            'user_input': user_input,
            'ai_response': ai_response,
            'model_used': model_used,
            'timestamp': timestamp,
            'children': []
        }
        
        # Add to tree
        self.tree['nodes'][node_id] = node
        
        if parent_id:
            # Add as child to parent
            if parent_id in self.tree['nodes']:
                if 'children' not in self.tree['nodes'][parent_id]:
                    self.tree['nodes'][parent_id]['children'] = []
                self.tree['nodes'][parent_id]['children'].append(node_id)
        else:
            # This is the root node
            self.tree['root_id'] = node_id
        
        self.save_tree()
        return node_id
    
    def reset_tree(self):
        """Reset the entire conversation tree"""
        self.tree = {
            'nodes': {},
            'root_id': None
        }
        self.save_tree()
        
        # Also clear ghost branches
        self.ghost_branches = {}
        self.save_ghost_branches()
        
        logger.info("Tree and ghost branches reset")

# Global memory manager instance
memory_manager = TreeMemoryManager()

def load_tree_memory() -> Dict[str, Any]:
    """Load conversation tree from disk"""
    try:
        if os.path.exists(TREE_MEMORY_FILE):
            with open(TREE_MEMORY_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        return {"nodes": {}, "root_id": None, "ghost_branches": {}}
    except Exception as e:
        logger.error(f"Failed to load tree memory: {e}")
        return {"nodes": {}, "root_id": None, "ghost_branches": {}}

def save_tree_memory(tree_data: Dict[str, Any]) -> None:
    """Save conversation tree to disk"""
    try:
        with open(TREE_MEMORY_FILE, "w", encoding='utf-8') as f:
            json.dump(tree_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save tree memory: {e}")
        raise MemoryError(f"Could not save tree memory: {e}")

def build_conversation_context(tree_data: Dict[str, Any], node_id: str) -> str:
    """Build conversation context from root to specified node"""
    if not node_id or node_id not in tree_data["nodes"]:
        return ""
    
    # Build path from root to current node
    path = []
    current_id = node_id
    
    while current_id:
        if current_id in tree_data["nodes"]:
            node = tree_data["nodes"][current_id]
            path.append(node)
            current_id = node.get("parent_id")
        else:
            break
    
    path.reverse()  # Start from root
    
    # Build context string
    context_parts = []
    for node in path:
        if node["user_input"]:
            context_parts.append(f"Human: {node['user_input']}")
        if node["ai_response"]:
            context_parts.append(f"Assistant: {node['ai_response']}")
    
    return "\n".join(context_parts[-10:])  # Last 10 exchanges

def create_ghost_branch(tree_data: Dict[str, Any], node_id: str, reason: str = "Node edited") -> str:
    """Create a ghost branch preserving the subtree from node_id"""
    if node_id not in tree_data["nodes"]:
        return None
    
    # Initialize ghost_branches if not exists
    if "ghost_branches" not in tree_data:
        tree_data["ghost_branches"] = {}
    
    # Create ghost branch ID
    ghost_id = f"ghost_{node_id}_{str(uuid.uuid4())[:8]}"
    
    # Deep copy the entire subtree
    ghost_branch = {
        "id": ghost_id,
        "original_node_id": node_id,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "reason": reason,
        "nodes": {},
        "root_id": node_id
    }
    
    # Recursively copy all descendant nodes
    def copy_subtree(current_id: str, visited: set = None):
        if visited is None:
            visited = set()
        
        if current_id in visited or current_id not in tree_data["nodes"]:
            return
            
        visited.add(current_id)
        
        # Copy the node
        original_node = tree_data["nodes"][current_id]
        ghost_branch["nodes"][current_id] = copy.deepcopy(original_node)
        
        # Copy all children
        for child_id in original_node.get("children", []):
            copy_subtree(child_id, visited)
    
    copy_subtree(node_id)
    
    # Store the ghost branch
    tree_data["ghost_branches"][ghost_id] = ghost_branch
    
    logger.info(f"Created ghost branch {ghost_id} preserving subtree from {node_id}")
    return ghost_id

def remove_subtree(tree_data: Dict[str, Any], node_id: str, preserve_root: bool = True):
    """Remove all descendants of a node (but optionally preserve the root node itself)"""
    if node_id not in tree_data["nodes"]:
        return
    
    # Get all descendants
    descendants = []
    
    def collect_descendants(current_id: str):
        if current_id in tree_data["nodes"]:
            for child_id in tree_data["nodes"][current_id].get("children", []):
                descendants.append(child_id)
                collect_descendants(child_id)
    
    collect_descendants(node_id)
    
    # Remove descendants
    for desc_id in descendants:
        if desc_id in tree_data["nodes"]:
            del tree_data["nodes"][desc_id]
    
    # Clear children of the root node
    if preserve_root and node_id in tree_data["nodes"]:
        tree_data["nodes"][node_id]["children"] = []
    elif not preserve_root and node_id in tree_data["nodes"]:
        # Also remove the root node itself
        parent_id = tree_data["nodes"][node_id].get("parent_id")
        if parent_id and parent_id in tree_data["nodes"]:
            parent_children = tree_data["nodes"][parent_id].get("children", [])
            if node_id in parent_children:
                parent_children.remove(node_id)
        del tree_data["nodes"][node_id]

def check_ollama_connection() -> bool:
    """Check if Ollama is available and responding"""
    try:
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False

def get_available_models() -> List[Dict[str, Any]]:
    """Get list of available Ollama models"""
    try:
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Extract model information
        models = []
        for model in data.get('models', []):
            models.append({
                'name': model.get('name', ''),
                'size': model.get('size', 0),
                'modified_at': model.get('modified_at', ''),
                'digest': model.get('digest', '')
            })
        
        # Sort by name for consistent ordering
        models.sort(key=lambda x: x['name'])
        return models
    except requests.RequestException as e:
        logger.error(f"Error fetching models from Ollama: {e}")
        return []
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error parsing models response: {e}")
        return []

@app.route('/')
def index():
    """Serve the main interface"""
    return render_template('index.html')

@app.route('/api/models', methods=['GET'])
def get_models():
    """Get available Ollama models"""
    try:
        models = get_available_models()
        return jsonify({
            "models": models,
            "default_model": OLLAMA_MODEL,
            "count": len(models)
        })
    except Exception as e:
        logger.error(f"Error in models endpoint: {e}")
        return jsonify({
            "error": "Failed to fetch models",
            "models": [],
            "default_model": OLLAMA_MODEL,
            "count": 0
        }), 500

@app.route('/api/status', methods=['GET'])
def status():
    """Get system status including Ollama connectivity and available models"""
    try:
        ollama_connected = check_ollama_connection()
        models = get_available_models() if ollama_connected else []
        
        return jsonify({
            "status": "running",
            "ollama_connected": ollama_connected,
            "model": OLLAMA_MODEL,
            "available_models": len(models),
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
    except Exception as e:
        logger.error(f"Error in status endpoint: {e}")
        return jsonify({
            "status": "error",
            "ollama_connected": False,
            "error": str(e)
        }), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages and update conversation tree"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
            
        user_input = data.get('message', '').strip()
        parent_id = data.get('parent_id')  # Node to branch from
        selected_model = data.get('model', OLLAMA_MODEL)  # Allow model selection
        
        if not user_input:
            return jsonify({"error": "Message cannot be empty"}), 400
        
        # Check if message is too long
        if len(user_input) > 5000:
            return jsonify({"error": "Message too long (max 5000 characters)"}), 400
        
        # Validate selected model
        if selected_model:
            available_models = get_available_models()
            model_names = [model['name'] for model in available_models]
            if selected_model not in model_names and available_models:  # Only validate if we can get models
                logger.warning(f"Requested model '{selected_model}' not available, using default")
                selected_model = OLLAMA_MODEL
        
        # Load conversation tree
        tree_data = load_tree_memory()
        
        # Build context from conversation path
        context = build_conversation_context(tree_data, parent_id) if parent_id else ""
        
        # Create enhanced prompt with context
        if context:
            full_prompt = f"""You are an autonomous language model. Here's our conversation so far:

{context}

Now respond to: {user_input}"""
        else:
            full_prompt = f"You are an autonomous language model. Respond to: {user_input}"
        
        logger.info(f"Processing chat request from {request.remote_addr} using model: {selected_model}")
        
        # Query the ALM with selected model
        response = query_ollama(full_prompt, model=selected_model)
        
        # Create new node
        new_node_id = str(uuid.uuid4())
        new_node = {
            "id": new_node_id,
            "user_input": user_input,
            "ai_response": response,
            "parent_id": parent_id,
            "model_used": selected_model,  # Store which model was used
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "children": []
        }
        
        # Update conversation tree
        tree_data["nodes"][new_node_id] = new_node
        
        # Update parent's children list
        if parent_id and parent_id in tree_data["nodes"]:
            if "children" not in tree_data["nodes"][parent_id]:
                tree_data["nodes"][parent_id]["children"] = []
            tree_data["nodes"][parent_id]["children"].append(new_node_id)
        else:
            # This is a root node
            tree_data["root_id"] = new_node_id
        
        # Save tree
        save_tree_memory(tree_data)
        
        logger.info(f"Chat completed successfully for node {new_node_id}")
        
        return jsonify({
            "node_id": new_node_id,
            "response": response,
            "model_used": selected_model,
            "timestamp": new_node["timestamp"]
        })
        
    except OllamaConnectionError as e:
        logger.error(f"Ollama connection error: {e}")
        return jsonify({
            "error": f"Ollama connection error: {str(e)}",
            "suggestion": "Please check that Ollama is running and accessible"
        }), 503
    except MemoryError as e:
        logger.error(f"Memory error: {e}")
        return jsonify({"error": f"Memory error: {str(e)}"}), 500
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error in chat: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/api/tree', methods=['GET'])
def get_tree():
    """Get the current conversation tree"""
    try:
        tree_data = load_tree_memory()
        return jsonify(tree_data)
    except Exception as e:
        logger.error(f"Error getting tree: {e}")
        return jsonify({"error": "Failed to load conversation tree"}), 500

@app.route('/api/tree/reset', methods=['POST'])
def reset_tree():
    """Reset the conversation tree"""
    try:
        tree_data = {"nodes": {}, "root_id": None}
        save_tree_memory(tree_data)
        logger.info("Conversation tree reset")
        return jsonify({"success": True, "message": "Tree reset successfully"})
    except Exception as e:
        logger.error(f"Error resetting tree: {e}")
        return jsonify({"error": "Failed to reset conversation tree"}), 500

@app.route('/api/node/<node_id>', methods=['GET'])
def get_node(node_id):
    """Get details of a specific node"""
    try:
        if not node_id:
            return jsonify({"error": "Node ID is required"}), 400
            
        tree_data = load_tree_memory()
        if node_id in tree_data["nodes"]:
            return jsonify(tree_data["nodes"][node_id])
        else:
            return jsonify({"error": "Node not found"}), 404
    except Exception as e:
        logger.error(f"Error getting node {node_id}: {e}")
        return jsonify({"error": "Failed to get node details"}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "version": "1.0.0"
    })

@app.route('/api/node/<node_id>/edit', methods=['POST'])
def edit_node(node_id):
    """Edit a specific node's content"""
    try:
        if not node_id:
            return jsonify({"error": "Node ID is required"}), 400
            
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        new_user_input = data.get('user_input', '').strip()
        new_ai_response = data.get('ai_response', '').strip()
        create_ghost = data.get('create_ghost', False)
        
        if not new_user_input and not new_ai_response:
            return jsonify({"error": "At least one of user_input or ai_response must be provided"}), 400
        
        # Load tree
        tree_data = load_tree_memory()
        
        if node_id not in tree_data["nodes"]:
            return jsonify({"error": "Node not found"}), 404
        
        node = tree_data["nodes"][node_id]
        has_children = len(node.get("children", [])) > 0
        
        ghost_id = None
        
        # Create ghost branch if requested and node has children
        if create_ghost and has_children:
            ghost_id = create_ghost_branch(tree_data, node_id, "Node edited - preserving original branch")
        
        # Remove children if not creating ghost (to maintain consistency)
        if has_children and not create_ghost:
            remove_subtree(tree_data, node_id, preserve_root=True)
        elif has_children and create_ghost:
            # Still remove children from the original tree since we ghosted them
            remove_subtree(tree_data, node_id, preserve_root=True)
        
        # Update the node content
        if new_user_input:
            node["user_input"] = new_user_input
        if new_ai_response:
            node["ai_response"] = new_ai_response
        
        # Update timestamp
        node["last_edited"] = datetime.datetime.utcnow().isoformat()
        node["edit_history"] = node.get("edit_history", [])
        node["edit_history"].append({
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "changes": {
                "user_input": new_user_input if new_user_input else None,
                "ai_response": new_ai_response if new_ai_response else None
            },
            "ghost_created": ghost_id
        })
        
        # Save tree
        save_tree_memory(tree_data)
        
        logger.info(f"Node {node_id} edited successfully. Ghost branch: {ghost_id}")
        
        return jsonify({
            "success": True,
            "message": "Node edited successfully",
            "ghost_branch_id": ghost_id,
            "children_removed": has_children and not create_ghost,
            "children_ghosted": has_children and create_ghost
        })
        
    except Exception as e:
        logger.error(f"Error editing node {node_id}: {e}")
        return jsonify({"error": "Failed to edit node"}), 500

@app.route('/api/ghost-branches', methods=['GET'])
def get_ghost_branches():
    """Get all ghost branches"""
    try:
        tree_data = load_tree_memory()
        ghost_branches = tree_data.get("ghost_branches", {})
        
        # Format ghost branches for frontend
        formatted_branches = {}
        for ghost_id, branch in ghost_branches.items():
            formatted_branches[ghost_id] = {
                "id": ghost_id,
                "original_node_id": branch["original_node_id"],
                "created_at": branch["created_at"],
                "reason": branch["reason"],
                "node_count": len(branch["nodes"]),
                "root_content": branch["nodes"].get(branch["root_id"], {}).get("user_input", "")[:50] + "..."
            }
        
        return jsonify(formatted_branches)
    except Exception as e:
        logger.error(f"Error getting ghost branches: {e}")
        return jsonify({"error": "Failed to load ghost branches"}), 500

@app.route('/api/ghost-branches/<ghost_id>', methods=['GET'])
def get_ghost_branch_details(ghost_id):
    """Get detailed information about a specific ghost branch"""
    try:
        tree_data = load_tree_memory()
        
        if ghost_id not in tree_data.get("ghost_branches", {}):
            return jsonify({"error": "Ghost branch not found"}), 404
        
        return jsonify(tree_data["ghost_branches"][ghost_id])
    except Exception as e:
        logger.error(f"Error getting ghost branch {ghost_id}: {e}")
        return jsonify({"error": "Failed to load ghost branch"}), 500

@app.route('/api/ghost-branches/<ghost_id>/restore', methods=['POST'])
def restore_ghost_branch(ghost_id):
    """Restore a ghost branch back to the main tree"""
    try:
        tree_data = load_tree_memory()
        
        if ghost_id not in tree_data.get("ghost_branches", {}):
            return jsonify({"error": "Ghost branch not found"}), 404
        
        ghost_branch = tree_data["ghost_branches"][ghost_id]
        
        # Check if the original node still exists
        original_node_id = ghost_branch["original_node_id"]
        if original_node_id not in tree_data["nodes"]:
            return jsonify({"error": "Original node no longer exists, cannot restore"}), 400
        
        # Restore all nodes from ghost branch
        for node_id, node_data in ghost_branch["nodes"].items():
            if node_id != original_node_id:  # Don't overwrite the edited original
                tree_data["nodes"][node_id] = node_data
        
        # Restore children relationship to original node
        original_node = tree_data["nodes"][original_node_id]
        ghost_root = ghost_branch["nodes"][original_node_id]
        original_node["children"] = ghost_root.get("children", [])
        
        # Remove the ghost branch
        del tree_data["ghost_branches"][ghost_id]
        
        # Save tree
        save_tree_memory(tree_data)
        
        logger.info(f"Ghost branch {ghost_id} restored successfully")
        
        return jsonify({
            "success": True,
            "message": "Ghost branch restored successfully"
        })
        
    except Exception as e:
        logger.error(f"Error restoring ghost branch {ghost_id}: {e}")
        return jsonify({"error": "Failed to restore ghost branch"}), 500

@app.route('/api/ghost-branches/<ghost_id>', methods=['DELETE'])
def delete_ghost_branch(ghost_id):
    """Permanently delete a ghost branch"""
    try:
        tree_data = load_tree_memory()
        
        if ghost_id not in tree_data.get("ghost_branches", {}):
            return jsonify({"error": "Ghost branch not found"}), 404
        
        # Remove the ghost branch
        del tree_data["ghost_branches"][ghost_id]
        
        # Save tree
        save_tree_memory(tree_data)
        
        logger.info(f"Ghost branch {ghost_id} deleted permanently")
        
        return jsonify({
            "success": True,
            "message": "Ghost branch deleted permanently"
        })
        
    except Exception as e:
        logger.error(f"Error deleting ghost branch {ghost_id}: {e}")
        return jsonify({"error": "Failed to delete ghost branch"}), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    # Get configuration from environment variables
    host = os.getenv('ALM_HOST', '0.0.0.0')
    port = int(os.getenv('ALM_PORT', '5001'))
    debug = os.getenv('ALM_DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting ALM web application on {host}:{port}")
    logger.info(f"Using Ollama model: {OLLAMA_MODEL}")
    logger.info(f"Ollama URL: {OLLAMA_URL}")
    
    # Check initial Ollama connection
    if check_ollama_connection():
        logger.info("✅ Ollama is connected and ready!")
    else:
        logger.warning("⚠️  Ollama is not responding. Please start Ollama for full functionality.")
    
    app.run(debug=debug, host=host, port=port) 