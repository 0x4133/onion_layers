#!/usr/bin/env python3

from flask import Flask, render_template, request, jsonify
import json
import os
import datetime
import requests
import logging
from typing import Dict, List, Any, Optional
import uuid

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

def load_tree_memory() -> Dict[str, Any]:
    """Load conversation tree from disk"""
    try:
        if os.path.exists(TREE_MEMORY_FILE):
            with open(TREE_MEMORY_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        return {"nodes": {}, "root_id": None}
    except Exception as e:
        logger.error(f"Failed to load tree memory: {e}")
        return {"nodes": {}, "root_id": None}

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

def check_ollama_connection() -> bool:
    """Check if Ollama is available and responding"""
    try:
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False

@app.route('/')
def index():
    """Serve the main interface"""
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def status():
    """Get system status including Ollama connectivity"""
    try:
        ollama_connected = check_ollama_connection()
        return jsonify({
            "status": "running",
            "ollama_connected": ollama_connected,
            "model": OLLAMA_MODEL,
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
        
        if not user_input:
            return jsonify({"error": "Message cannot be empty"}), 400
        
        # Check if message is too long
        if len(user_input) > 5000:
            return jsonify({"error": "Message too long (max 5000 characters)"}), 400
        
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
        
        logger.info(f"Processing chat request from {request.remote_addr}")
        
        # Query the ALM
        response = query_ollama(full_prompt)
        
        # Create new node
        new_node_id = str(uuid.uuid4())
        new_node = {
            "id": new_node_id,
            "user_input": user_input,
            "ai_response": response,
            "parent_id": parent_id,
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