import unittest
import json
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
import requests
from flask import Flask
from app import app, load_tree_memory, save_tree_memory, build_conversation_context


class TestFlaskApp(unittest.TestCase):
    """Test Flask web application"""
    
    def setUp(self):
        """Set up test environment"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.tree_memory_patch = patch('app.TREE_MEMORY_FILE', 
                                      os.path.join(self.test_dir, 'test_tree_memory.json'))
        self.tree_memory_patch.start()
    
    def tearDown(self):
        """Clean up test environment"""
        self.tree_memory_patch.stop()
        shutil.rmtree(self.test_dir)
    
    def test_index_route(self):
        """Test main index route returns HTML"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Visual ALM', response.data)
        self.assertIn(b'<!DOCTYPE html>', response.data)
    
    def test_index_contains_layout_constraints(self):
        """Test that index.html contains proper layout constraints to prevent growing"""
        response = self.client.get('/')
        html_content = response.data.decode('utf-8')
        
        # Check for critical CSS that prevents growing
        self.assertIn('height: 100vh', html_content)
        self.assertIn('overflow: hidden', html_content)
        self.assertIn('position: fixed', html_content)
        self.assertIn('height: 140px', html_content)  # Messages fixed height
        self.assertIn('sidebar-footer', html_content)  # Footer section exists
        
        # Check for layout structure
        self.assertIn('sidebar-header', html_content)
        self.assertIn('sidebar-content', html_content)
        self.assertIn('sidebar-footer', html_content)
    
    def test_get_tree_empty(self):
        """Test getting empty conversation tree"""
        response = self.client.get('/api/tree')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        expected = {"nodes": {}, "root_id": None}
        self.assertEqual(data, expected)
    
    def test_reset_tree(self):
        """Test resetting conversation tree"""
        response = self.client.post('/api/tree/reset')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data["success"])
    
    @patch('app.query_ollama')
    def test_chat_new_conversation(self, mock_query):
        """Test starting a new conversation"""
        mock_query.return_value = "Hello! How can I help you today?"
        
        response = self.client.post('/api/chat', 
                                  json={'message': 'Hello there'})
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertIn('node_id', data)
        self.assertIn('response', data)
        self.assertIn('timestamp', data)
        self.assertEqual(data['response'], "Hello! How can I help you today?")
    
    @patch('app.query_ollama')
    def test_chat_with_parent(self, mock_query):
        """Test branching conversation from existing node"""
        mock_query.return_value = "That's interesting!"
        
        # First create a conversation
        first_response = self.client.post('/api/chat', 
                                        json={'message': 'Hello'})
        first_data = json.loads(first_response.data)
        parent_id = first_data['node_id']
        
        # Branch from that node
        response = self.client.post('/api/chat', 
                                  json={'message': 'Tell me more', 
                                        'parent_id': parent_id})
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['response'], "That's interesting!")
    
    def test_chat_empty_message(self):
        """Test chat with empty message"""
        response = self.client.post('/api/chat', 
                                  json={'message': ''})
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    @patch('app.query_ollama')
    def test_chat_ollama_connection_error(self, mock_query):
        """Test chat when Ollama is not available"""
        from main import OllamaConnectionError
        mock_query.side_effect = OllamaConnectionError("Could not connect to Ollama server")
        
        response = self.client.post('/api/chat', 
                                  json={'message': 'Hello'})
        
        self.assertEqual(response.status_code, 503)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_get_nonexistent_node(self):
        """Test getting details of non-existent node"""
        response = self.client.get('/api/node/nonexistent')
        self.assertEqual(response.status_code, 404)


class TestTreeMemoryOperations(unittest.TestCase):
    """Test tree memory operations"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.tree_memory_patch = patch('app.TREE_MEMORY_FILE', 
                                      os.path.join(self.test_dir, 'test_tree_memory.json'))
        self.tree_memory_patch.start()
    
    def tearDown(self):
        """Clean up test environment"""
        self.tree_memory_patch.stop()
        shutil.rmtree(self.test_dir)
    
    def test_load_tree_memory_new_file(self):
        """Test loading tree memory when file doesn't exist"""
        tree_data = load_tree_memory()
        expected = {"nodes": {}, "root_id": None}
        self.assertEqual(tree_data, expected)
    
    def test_load_tree_memory_existing_file(self):
        """Test loading tree memory from existing file"""
        test_tree = {
            "nodes": {
                "node1": {
                    "id": "node1",
                    "user_input": "Hello",
                    "ai_response": "Hi there",
                    "parent_id": None,
                    "children": []
                }
            },
            "root_id": "node1"
        }
        
        tree_file = os.path.join(self.test_dir, 'test_tree_memory.json')
        with open(tree_file, 'w') as f:
            json.dump(test_tree, f)
        
        tree_data = load_tree_memory()
        self.assertEqual(tree_data, test_tree)
    
    def test_save_tree_memory(self):
        """Test saving tree memory"""
        test_tree = {
            "nodes": {"node1": {"id": "node1", "user_input": "test"}},
            "root_id": "node1"
        }
        
        save_tree_memory(test_tree)
        
        tree_file = os.path.join(self.test_dir, 'test_tree_memory.json')
        self.assertTrue(os.path.exists(tree_file))
        
        with open(tree_file, 'r') as f:
            saved_data = json.load(f)
        
        self.assertEqual(saved_data, test_tree)
    
    def test_build_conversation_context_empty(self):
        """Test building context with empty tree"""
        tree_data = {"nodes": {}, "root_id": None}
        context = build_conversation_context(tree_data, "nonexistent")
        self.assertEqual(context, "")
    
    def test_build_conversation_context_single_node(self):
        """Test building context with single node"""
        tree_data = {
            "nodes": {
                "node1": {
                    "user_input": "Hello",
                    "ai_response": "Hi there",
                    "parent_id": None
                }
            },
            "root_id": "node1"
        }
        
        context = build_conversation_context(tree_data, "node1")
        self.assertIn("Human: Hello", context)
        self.assertIn("Assistant: Hi there", context)
    
    def test_build_conversation_context_chain(self):
        """Test building context with conversation chain"""
        tree_data = {
            "nodes": {
                "node1": {
                    "user_input": "Hello",
                    "ai_response": "Hi there",
                    "parent_id": None
                },
                "node2": {
                    "user_input": "How are you?",
                    "ai_response": "I'm doing well",
                    "parent_id": "node1"
                }
            },
            "root_id": "node1"
        }
        
        context = build_conversation_context(tree_data, "node2")
        lines = context.split('\n')
        
        # Should have both conversations in order
        self.assertIn("Human: Hello", context)
        self.assertIn("Assistant: Hi there", context)
        self.assertIn("Human: How are you?", context)
        self.assertIn("Assistant: I'm doing well", context)


class TestUILayoutBehavior(unittest.TestCase):
    """Test UI layout behavior and constraints"""
    
    def setUp(self):
        """Set up test environment"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
    
    def test_html_has_viewport_constraints(self):
        """Test that HTML has proper viewport constraints"""
        response = self.client.get('/')
        html_content = response.data.decode('utf-8')
        
        # Critical layout constraints that prevent growing
        required_css = [
            'height: 100vh',
            'overflow: hidden',
            'position: fixed',
            'height: 140px',  # Fixed messages height
            'height: calc(100vh - 200px)',  # Content area calculation
            'position: absolute',  # Footer positioning
        ]
        
        for css_rule in required_css:
            self.assertIn(css_rule, html_content, 
                         f"Missing critical CSS rule: {css_rule}")
    
    def test_html_has_proper_structure(self):
        """Test that HTML has proper structure to prevent layout growth"""
        response = self.client.get('/')
        html_content = response.data.decode('utf-8')
        
        # Required structural elements
        required_elements = [
            'class="sidebar-header"',
            'class="sidebar-content"', 
            'class="sidebar-footer"',
            'id="messages"',
            'id="selectedNodeInfo"',
            'id="loading"'
        ]
        
        for element in required_elements:
            self.assertIn(element, html_content,
                         f"Missing required element: {element}")
    
    def test_javascript_message_limiting(self):
        """Test that JavaScript includes message limiting logic"""
        response = self.client.get('/')
        html_content = response.data.decode('utf-8')
        
        # Check for message limiting logic in JavaScript
        js_patterns = [
            'messagesDiv.children.length >= 10',
            'messagesDiv.removeChild',
            'messagesDiv.scrollTop',
            'messagesDiv.scrollHeight'
        ]
        
        for pattern in js_patterns:
            self.assertIn(pattern, html_content,
                         f"Missing JS pattern for message control: {pattern}")
    
    def test_css_prevents_flex_growth(self):
        """Test that CSS prevents problematic flex growth"""
        response = self.client.get('/')
        html_content = response.data.decode('utf-8')
        
        # Should NOT contain problematic flex rules on messages
        problematic_patterns = [
            '#messages {\n            flex: 1',
            'flex-grow: 1'
        ]
        
        for pattern in problematic_patterns:
            self.assertNotIn(pattern, html_content,
                           f"Found problematic CSS that could cause growth: {pattern}")


class TestMessageHandling(unittest.TestCase):
    """Test message handling and UI feedback"""
    
    def setUp(self):
        """Set up test environment"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
    
    def test_showMessage_function_exists(self):
        """Test that showMessage function exists in JavaScript"""
        response = self.client.get('/')
        html_content = response.data.decode('utf-8')
        
        self.assertIn('function showMessage(message, type)', html_content)
    
    def test_message_cleanup_logic(self):
        """Test that message cleanup logic is present"""
        response = self.client.get('/')
        html_content = response.data.decode('utf-8')
        
        # Check for auto-removal logic
        self.assertIn('setTimeout', html_content)
        self.assertIn('removeChild', html_content)
        self.assertIn('5000', html_content)  # 5 second timeout


if __name__ == '__main__':
    unittest.main() 