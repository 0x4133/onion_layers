import unittest
import json
import os
import tempfile
import shutil
from unittest.mock import patch, mock_open, MagicMock
import requests
from main import (
    load_memory, save_memory, query_ollama, build_prompt, main,
    ALMError, OllamaConnectionError, MemoryError,
    MEMORY_FILE, OLLAMA_MODEL, OLLAMA_URL, REQUEST_TIMEOUT
)


class TestMemoryOperations(unittest.TestCase):
    """Test memory loading and saving operations"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.original_memory_file = MEMORY_FILE
        # Patch the MEMORY_FILE to use test directory
        self.memory_file_patch = patch('main.MEMORY_FILE', 
                                     os.path.join(self.test_dir, 'test_memory.json'))
        self.memory_file_patch.start()
    
    def tearDown(self):
        """Clean up test environment"""
        self.memory_file_patch.stop()
        shutil.rmtree(self.test_dir)
    
    def test_load_memory_new_file(self):
        """Test loading memory when file doesn't exist"""
        memory = load_memory()
        expected = {"goals": [], "log": []}
        self.assertEqual(memory, expected)
    
    def test_load_memory_existing_file(self):
        """Test loading memory from existing file"""
        test_memory = {
            "goals": ["Learn Python", "Build a project"],
            "log": [{"timestamp": "2023-01-01", "user": "Hello", "model": "Hi there"}]
        }
        
        memory_file = os.path.join(self.test_dir, 'test_memory.json')
        with open(memory_file, 'w') as f:
            json.dump(test_memory, f)
        
        memory = load_memory()
        self.assertEqual(memory, test_memory)
    
    def test_load_memory_corrupted_file(self):
        """Test loading memory with corrupted JSON file"""
        memory_file = os.path.join(self.test_dir, 'test_memory.json')
        with open(memory_file, 'w') as f:
            f.write("invalid json content")
        
        memory = load_memory()
        expected = {"goals": [], "log": []}
        self.assertEqual(memory, expected)
    
    def test_load_memory_invalid_structure(self):
        """Test loading memory with invalid structure"""
        memory_file = os.path.join(self.test_dir, 'test_memory.json')
        with open(memory_file, 'w') as f:
            json.dump("not a dict", f)
        
        memory = load_memory()
        expected = {"goals": [], "log": []}
        self.assertEqual(memory, expected)
    
    def test_load_memory_missing_keys(self):
        """Test loading memory with missing required keys"""
        memory_file = os.path.join(self.test_dir, 'test_memory.json')
        with open(memory_file, 'w') as f:
            json.dump({"only_goals": []}, f)
        
        memory = load_memory()
        self.assertIn("goals", memory)
        self.assertIn("log", memory)
    
    def test_save_memory_success(self):
        """Test successful memory saving"""
        test_memory = {
            "goals": ["Test goal"],
            "log": [{"timestamp": "2023-01-01", "user": "test", "model": "response"}]
        }
        
        save_memory(test_memory)
        
        # Verify file was created and contains correct data
        memory_file = os.path.join(self.test_dir, 'test_memory.json')
        self.assertTrue(os.path.exists(memory_file))
        
        with open(memory_file, 'r') as f:
            saved_data = json.load(f)
        
        self.assertEqual(saved_data, test_memory)
    
    def test_save_memory_log_trimming(self):
        """Test that memory log gets trimmed when too large"""
        # Create memory with more than MAX_LOG_ENTRIES
        large_log = [{"timestamp": f"2023-01-{i:02d}", "user": f"msg{i}", "model": f"resp{i}"} 
                     for i in range(150)]
        test_memory = {"goals": [], "log": large_log}
        
        with patch('main.MAX_LOG_ENTRIES', 100):
            save_memory(test_memory)
        
        memory_file = os.path.join(self.test_dir, 'test_memory.json')
        with open(memory_file, 'r') as f:
            saved_data = json.load(f)
        
        self.assertEqual(len(saved_data["log"]), 100)
        # Should keep the last 100 entries
        self.assertEqual(saved_data["log"][0]["user"], "msg50")
    
    @patch('builtins.open', side_effect=IOError("Permission denied"))
    def test_save_memory_io_error(self, mock_file):
        """Test save memory with IO error"""
        test_memory = {"goals": [], "log": []}
        
        with self.assertRaises(MemoryError):
            save_memory(test_memory)


class TestOllamaOperations(unittest.TestCase):
    """Test Ollama API operations"""
    
    @patch('main.requests.post')
    def test_query_ollama_success(self, mock_post):
        """Test successful Ollama query"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Hello, how can I help?"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = query_ollama("Hello")
        
        self.assertEqual(result, "Hello, how can I help?")
        mock_post.assert_called_once_with(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": "Hello",
                "stream": False
            },
            timeout=REQUEST_TIMEOUT
        )
    
    def test_query_ollama_empty_prompt(self):
        """Test Ollama query with empty prompt"""
        with self.assertRaises(ValueError):
            query_ollama("")
        
        with self.assertRaises(ValueError):
            query_ollama("   ")
    
    @patch('main.requests.post')
    def test_query_ollama_connection_error(self, mock_post):
        """Test Ollama query with connection error"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        with self.assertRaises(OllamaConnectionError) as context:
            query_ollama("Hello")
        
        self.assertIn("Could not connect to Ollama server", str(context.exception))
    
    @patch('main.requests.post')
    def test_query_ollama_timeout(self, mock_post):
        """Test Ollama query with timeout"""
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
        
        with self.assertRaises(OllamaConnectionError) as context:
            query_ollama("Hello")
        
        self.assertIn("timed out", str(context.exception))
    
    @patch('main.requests.post')
    def test_query_ollama_invalid_response(self, mock_post):
        """Test Ollama query with invalid response format"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "No response field"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        with self.assertRaises(OllamaConnectionError):
            query_ollama("Hello")
    
    @patch('main.requests.post')
    def test_query_ollama_json_decode_error(self, mock_post):
        """Test Ollama query with JSON decode error"""
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        with self.assertRaises(OllamaConnectionError):
            query_ollama("Hello")


class TestPromptBuilding(unittest.TestCase):
    """Test prompt building functionality"""
    
    def test_build_prompt_basic(self):
        """Test basic prompt building"""
        memory = {"goals": ["Learn Python"], "log": []}
        user_input = "Hello"
        
        prompt = build_prompt(memory, user_input)
        
        self.assertIn("Learn Python", prompt)
        self.assertIn("Hello", prompt)
        self.assertIn("You are an autonomous language model", prompt)
    
    def test_build_prompt_empty_memory(self):
        """Test prompt building with empty memory"""
        memory = {"goals": [], "log": []}
        user_input = "Hello"
        
        prompt = build_prompt(memory, user_input)
        
        self.assertIn("No goals yet", prompt)
        self.assertIn("None", prompt)  # For empty log
        self.assertIn("Hello", prompt)
    
    def test_build_prompt_with_log(self):
        """Test prompt building with interaction log"""
        memory = {
            "goals": ["Test goal"],
            "log": [
                {"timestamp": "2023-01-01", "user": "Hi", "model": "Hello"},
                {"timestamp": "2023-01-02", "user": "How are you?", "model": "I'm fine"}
            ]
        }
        user_input = "What's next?"
        
        prompt = build_prompt(memory, user_input)
        
        self.assertIn("2023-01-01: Hi", prompt)
        self.assertIn("2023-01-02: How are you?", prompt)
        self.assertIn("What's next?", prompt)
    
    def test_build_prompt_empty_user_input(self):
        """Test prompt building with empty user input"""
        memory = {"goals": [], "log": []}
        
        with self.assertRaises(ValueError):
            build_prompt(memory, "")
        
        with self.assertRaises(ValueError):
            build_prompt(memory, "   ")
    
    def test_build_prompt_malformed_memory(self):
        """Test prompt building with malformed memory structure"""
        memory = {}  # Missing keys
        user_input = "Hello"
        
        prompt = build_prompt(memory, user_input)
        
        # Should handle missing keys gracefully
        self.assertIn("No goals yet", prompt)
        self.assertIn("None", prompt)
    
    def test_build_prompt_log_limit(self):
        """Test that only recent log entries are included"""
        # Create more than 5 log entries
        log_entries = [
            {"timestamp": f"2023-01-{i:02d}", "user": f"message{i}", "model": f"response{i}"}
            for i in range(1, 11)
        ]
        memory = {"goals": [], "log": log_entries}
        user_input = "Hello"
        
        prompt = build_prompt(memory, user_input)
        
        # Should only include last 5 entries
        self.assertIn("2023-01-06: message6", prompt)
        self.assertIn("2023-01-10: message10", prompt)
        self.assertNotIn("2023-01-01: message1", prompt)


class TestErrorClasses(unittest.TestCase):
    """Test custom error classes"""
    
    def test_alm_error(self):
        """Test ALMError base class"""
        error = ALMError("Test error")
        self.assertEqual(str(error), "Test error")
        self.assertIsInstance(error, Exception)
    
    def test_ollama_connection_error(self):
        """Test OllamaConnectionError"""
        error = OllamaConnectionError("Connection failed")
        self.assertEqual(str(error), "Connection failed")
        self.assertIsInstance(error, ALMError)
    
    def test_memory_error(self):
        """Test MemoryError"""
        error = MemoryError("Memory operation failed")
        self.assertEqual(str(error), "Memory operation failed")
        self.assertIsInstance(error, ALMError)


class TestMainFunction(unittest.TestCase):
    """Test main function and integration"""
    
    @patch('main.input', side_effect=['exit'])
    @patch('main.load_memory')
    @patch('builtins.print')
    def test_main_exit_immediately(self, mock_print, mock_load_memory, mock_input):
        """Test main function with immediate exit"""
        mock_load_memory.return_value = {"goals": [], "log": []}
        
        main()
        
        mock_load_memory.assert_called_once()
        # Should print ready message and exit message
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        self.assertTrue(any("ready" in call for call in print_calls))
        self.assertTrue(any("ended" in call for call in print_calls))
    
    @patch('main.input', side_effect=['hello', 'exit'])
    @patch('main.load_memory')
    @patch('main.query_ollama')
    @patch('main.save_memory')
    @patch('builtins.print')
    def test_main_single_interaction(self, mock_print, mock_save, mock_query, mock_load, mock_input):
        """Test main function with single interaction"""
        mock_load.return_value = {"goals": [], "log": []}
        mock_query.return_value = "Hello there!"
        
        main()
        
        mock_query.assert_called_once()
        mock_save.assert_called()
    
    @patch('main.input', side_effect=['', 'exit'])
    @patch('main.load_memory')
    @patch('builtins.print')
    def test_main_empty_input(self, mock_print, mock_load, mock_input):
        """Test main function with empty input"""
        mock_load.return_value = {"goals": [], "log": []}
        
        main()
        
        # Should prompt for non-empty message
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        self.assertTrue(any("Please enter a message" in call for call in print_calls))
    
    @patch('main.input', side_effect=['hello', 'exit'])
    @patch('main.load_memory')
    @patch('main.query_ollama')
    @patch('builtins.print')
    def test_main_ollama_connection_error(self, mock_print, mock_query, mock_load, mock_input):
        """Test main function with Ollama connection error"""
        mock_load.return_value = {"goals": [], "log": []}
        mock_query.side_effect = OllamaConnectionError("Server not running")
        
        main()
        
        # Should print error message
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        self.assertTrue(any("Error:" in call for call in print_calls))


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete workflow"""
    
    def setUp(self):
        """Set up test environment for integration tests"""
        self.test_dir = tempfile.mkdtemp()
        self.memory_file_patch = patch('main.MEMORY_FILE', 
                                     os.path.join(self.test_dir, 'integration_memory.json'))
        self.memory_file_patch.start()
    
    def tearDown(self):
        """Clean up test environment"""
        self.memory_file_patch.stop()
        shutil.rmtree(self.test_dir)
    
    @patch('main.query_ollama')
    def test_full_interaction_cycle(self, mock_query):
        """Test complete interaction cycle"""
        mock_query.return_value = "I understand your goal!"
        
        # Start with empty memory
        memory = load_memory()
        self.assertEqual(memory, {"goals": [], "log": []})
        
        # Simulate user interaction
        user_input = "I want to learn machine learning"
        prompt = build_prompt(memory, user_input)
        response = mock_query(prompt)
        
        # Update memory
        import datetime
        timestamp = datetime.datetime.utcnow().isoformat()
        memory["log"].append({
            "timestamp": timestamp,
            "user": user_input,
            "model": response
        })
        
        # Save and reload
        save_memory(memory)
        reloaded_memory = load_memory()
        
        # Verify persistence
        self.assertEqual(len(reloaded_memory["log"]), 1)
        self.assertEqual(reloaded_memory["log"][0]["user"], user_input)
        self.assertEqual(reloaded_memory["log"][0]["model"], response)


if __name__ == '__main__':
    # Create test suite
    test_loader = unittest.TestLoader()
    test_suite = unittest.TestSuite()
    
    # Add all test cases
    test_classes = [
        TestMemoryOperations,
        TestOllamaOperations,
        TestPromptBuilding,
        TestErrorClasses,
        TestMainFunction,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = test_loader.loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}")
    
    if result.errors:
        print(f"\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}") 