import unittest
import time
import tempfile
import shutil
import os
from unittest.mock import patch, MagicMock
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import threading
from app import app


class TestSidebarGrowthBehavior(unittest.TestCase):
    """Integration test to identify and prevent sidebar growth issues"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests"""
        # Configure Chrome options for headless testing
        cls.chrome_options = Options()
        cls.chrome_options.add_argument("--headless")
        cls.chrome_options.add_argument("--no-sandbox")
        cls.chrome_options.add_argument("--disable-dev-shm-usage")
        cls.chrome_options.add_argument("--window-size=1280,720")
        
        # Create temporary directory for test files
        cls.test_dir = tempfile.mkdtemp()
        
        # Configure Flask app for testing
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        
        # Patch file paths
        cls.tree_memory_patch = patch('app.TREE_MEMORY_FILE', 
                                     os.path.join(cls.test_dir, 'test_tree_memory.json'))
        cls.tree_memory_patch.start()
        
        # Start Flask app in separate thread
        cls.server_thread = threading.Thread(
            target=lambda: app.run(host='127.0.0.1', port=5555, debug=False, use_reloader=False)
        )
        cls.server_thread.daemon = True
        cls.server_thread.start()
        time.sleep(2)  # Wait for server to start
    
    @classmethod 
    def tearDownClass(cls):
        """Clean up test environment"""
        cls.tree_memory_patch.stop()
        shutil.rmtree(cls.test_dir)
    
    def setUp(self):
        """Set up for each test"""
        try:
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.driver.get("http://127.0.0.1:5555")
            self.wait = WebDriverWait(self.driver, 10)
        except Exception as e:
            self.skipTest(f"Chrome WebDriver not available: {e}")
    
    def tearDown(self):
        """Clean up after each test"""
        if hasattr(self, 'driver'):
            self.driver.quit()
    
    def get_sidebar_height(self):
        """Get current sidebar height"""
        sidebar = self.driver.find_element(By.CLASS_NAME, "sidebar")
        return sidebar.size['height']
    
    def get_messages_container_height(self):
        """Get messages container height"""
        messages = self.driver.find_element(By.ID, "messages")
        return messages.size['height']
    
    def send_test_message(self, message="Test message"):
        """Send a test message"""
        # Mock the Ollama response to avoid external dependencies
        self.driver.execute_script("""
            // Override the sendMessage function to avoid actual API calls
            window.originalSendMessage = sendMessage;
            sendMessage = function() {
                const input = document.getElementById('messageInput');
                const message = input.value.trim();
                if (!message) return;
                
                // Simulate successful response
                input.value = '';
                showMessage('Message sent successfully!', 'success');
                
                // Simulate adding a node to the tree (simplified)
                selectedNodeId = 'test_node_' + Date.now();
                
                // Update node info
                document.getElementById('selectedNodeInfo').innerHTML = `
                    <div class="node-info selected-path">
                        <h3>Selected Node</h3>
                        <div class="timestamp">${new Date().toLocaleString()}</div>
                        <div class="message"><strong>You:</strong> ${message}</div>
                        <div class="response"><strong>ALM:</strong> Test response</div>
                        <p><em>New messages will branch from this point</em></p>
                    </div>
                `;
            };
        """)
        
        input_field = self.driver.find_element(By.ID, "messageInput")
        input_field.clear()
        input_field.send_keys(message)
        input_field.send_keys(Keys.RETURN)
        time.sleep(0.5)  # Allow UI to update
    
    def test_sidebar_height_remains_constant(self):
        """Test that sidebar height doesn't grow beyond viewport"""
        initial_height = self.get_sidebar_height()
        viewport_height = self.driver.execute_script("return window.innerHeight;")
        
        # Initial height should not exceed viewport
        self.assertLessEqual(initial_height, viewport_height, 
                           "Initial sidebar height exceeds viewport height")
        
        # Send multiple messages
        for i in range(10):
            self.send_test_message(f"Test message {i+1}")
            
            current_height = self.get_sidebar_height()
            self.assertLessEqual(current_height, viewport_height + 10,
                               msg=f"Sidebar height ({current_height}px) exceeds viewport ({viewport_height}px) after {i+1} messages")
            
            # Height should remain essentially constant
            self.assertAlmostEqual(current_height, initial_height, delta=50,
                                 msg=f"Sidebar height changed significantly after {i+1} messages")
    
    def test_messages_container_height_fixed(self):
        """Test that messages container height stays fixed"""
        initial_height = self.get_messages_container_height()
        
        # Send multiple messages to trigger potential growth
        for i in range(15):
            self.send_test_message(f"Message that could cause growth {i+1}")
            
            current_height = self.get_messages_container_height()
            self.assertEqual(current_height, initial_height,
                           f"Messages container height changed after {i+1} messages")
    
    def test_no_vertical_scrollbar_on_body(self):
        """Test that body doesn't develop a vertical scrollbar"""
        # Initial state
        body_scroll_height = self.driver.execute_script("return document.body.scrollHeight;")
        viewport_height = self.driver.execute_script("return window.innerHeight;")
        
        # Should not have vertical scroll initially
        self.assertLessEqual(body_scroll_height, viewport_height + 5,  # 5px tolerance
                           "Page initially has vertical scrollbar")
        
        # After multiple messages
        for i in range(20):
            self.send_test_message(f"Potential scroll trigger {i+1}")
        
        final_scroll_height = self.driver.execute_script("return document.body.scrollHeight;")
        self.assertLessEqual(final_scroll_height, viewport_height + 5,
                           "Page developed vertical scrollbar after messages")
    
    def test_container_overflow_handling(self):
        """Test that container properly handles overflow"""
        # Check that container has proper overflow settings
        container = self.driver.find_element(By.CLASS_NAME, "container")
        container_overflow = self.driver.execute_script(
            "return window.getComputedStyle(arguments[0]).overflow;", container)
        
        # Container should not allow overflow that creates scrollbars
        self.assertNotEqual(container_overflow, "visible", 
                          "Container allows visible overflow")
    
    def test_sidebar_footer_positioning(self):
        """Test that sidebar footer stays at bottom without affecting layout"""
        sidebar_footer = self.driver.find_element(By.CLASS_NAME, "sidebar-footer")
        
        # Get positioning properties
        position = self.driver.execute_script(
            "return window.getComputedStyle(arguments[0]).position;", sidebar_footer)
        bottom = self.driver.execute_script(
            "return window.getComputedStyle(arguments[0]).bottom;", sidebar_footer)
        
        self.assertEqual(position, "absolute", "Footer should be absolutely positioned")
        self.assertEqual(bottom, "0px", "Footer should be at bottom")
        
        # Send messages and ensure footer position doesn't change
        for i in range(5):
            self.send_test_message(f"Footer position test {i+1}")
            
            new_bottom = self.driver.execute_script(
                "return window.getComputedStyle(arguments[0]).bottom;", sidebar_footer)
            self.assertEqual(new_bottom, "0px", 
                           f"Footer moved from bottom after {i+1} messages")
    
    def test_message_limiting_works(self):
        """Test that message limiting prevents accumulation"""
        # Send more than 10 messages (the limit)
        for i in range(15):
            self.send_test_message(f"Message limit test {i+1}")
        
        # Check that only 10 or fewer messages are displayed
        messages_count = self.driver.execute_script(
            "return document.getElementById('messages').children.length;")
        
        self.assertLessEqual(messages_count, 10, 
                           "More than 10 messages are displayed")
    
    def test_rapid_message_sending(self):
        """Test rapid message sending doesn't break layout"""
        initial_height = self.get_sidebar_height()
        
        # Rapidly send messages
        for i in range(20):
            self.send_test_message(f"Rapid message {i+1}")
            if i % 5 == 0:  # Check every 5 messages
                current_height = self.get_sidebar_height()
                self.assertAlmostEqual(current_height, initial_height, delta=50,
                                      msg=f"Layout broken during rapid sending at message {i+1}")
    
    def test_css_layout_constraints_applied(self):
        """Test that critical CSS constraints are actually applied"""
        # Check body overflow
        body_overflow = self.driver.execute_script(
            "return window.getComputedStyle(document.body).overflow;")
        self.assertEqual(body_overflow, "hidden", "Body should have overflow: hidden")
        
        # Check container height
        container = self.driver.find_element(By.CLASS_NAME, "container")
        container_height = self.driver.execute_script(
            "return window.getComputedStyle(arguments[0]).height;", container)
        viewport_height = self.driver.execute_script("return window.innerHeight + 'px';")
        self.assertEqual(container_height, viewport_height, "Container should be 100vh")
        
        # Check messages height
        messages = self.driver.find_element(By.ID, "messages")
        messages_height = self.driver.execute_script(
            "return window.getComputedStyle(arguments[0]).height;", messages)
        self.assertEqual(messages_height, "140px", "Messages should be fixed at 140px")


class TestLayoutStress(unittest.TestCase):
    """Stress test to identify layout breaking points"""
    
    def setUp(self):
        """Set up test client"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
    
    def test_large_node_content_handling(self):
        """Test how layout handles very large content"""
        response = self.client.get('/')
        html_content = response.data.decode('utf-8')
        
        # Check that CSS includes word-wrap and overflow handling
        self.assertIn('word-wrap: break-word', html_content)
        self.assertIn('overflow-y: auto', html_content)
    
    def test_css_rule_completeness(self):
        """Test that all critical CSS rules are present"""
        response = self.client.get('/')
        html_content = response.data.decode('utf-8')
        
        critical_rules = [
            'height: 100vh',
            'overflow: hidden',
            'position: fixed',
            'height: 140px',
            'position: absolute',
            'bottom: 0',
            'height: calc(100vh - 200px)',
            'box-sizing: border-box'
        ]
        
        missing_rules = []
        for rule in critical_rules:
            if rule not in html_content:
                missing_rules.append(rule)
        
        self.assertEqual(len(missing_rules), 0, 
                        f"Missing critical CSS rules: {missing_rules}")


if __name__ == '__main__':
    # Only run if selenium is available
    try:
        import selenium
        unittest.main()
    except ImportError:
        print("Selenium not available, skipping integration tests")
        print("Run: pip install selenium")
        print("And install Chrome/ChromeDriver for full testing") 