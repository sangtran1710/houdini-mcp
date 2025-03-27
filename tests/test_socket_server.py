import unittest
import json
import socket
import sys
import os
import threading
import time
from unittest.mock import patch, MagicMock

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from server import HoudiniMCPServer

class TestSocketServer(unittest.TestCase):
    """Test cases for the socket server"""

    def setUp(self):
        """Set up mock command executor and server instance"""
        self.mock_command_executor = MagicMock()
        self.mock_command_executor.return_value = {
            "status": "success",
            "message": "Command executed successfully"
        }
        
        # Use a different port for testing to avoid conflicts
        self.test_port = 9999
        self.server = HoudiniMCPServer('localhost', self.test_port, self.mock_command_executor)
        
        # Start server in a separate thread
        self.server_thread = threading.Thread(target=self._start_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Give the server time to start
        time.sleep(0.1)
        
    def _start_server(self):
        """Start the server for testing"""
        self.server.start()
        
    def tearDown(self):
        """Clean up server instance"""
        if self.server:
            self.server.stop()
        
    def test_server_starts_and_stops(self):
        """Test that the server starts and stops properly"""
        # Server should be running after setUp
        self.assertTrue(self.server.is_running())
        
        # Stop the server
        self.server.stop()
        time.sleep(0.1)  # Give it time to stop
        
        # Server should no longer be running
        self.assertFalse(self.server.is_running())
        
    def test_command_execution(self):
        """Test that the server executes commands and returns responses"""
        # Configure mock to return a specific response for a specific command
        self.mock_command_executor.return_value = {
            "status": "success",
            "message": "Node created",
            "node_path": "/obj/test_geo"
        }
        
        # Connect to server
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('localhost', self.test_port))
        
        # Send command
        command = {
            "type": "create_node",
            "params": {
                "parent_path": "/obj",
                "node_type": "geo",
                "node_name": "test_geo"
            }
        }
        client.sendall(json.dumps(command).encode('utf-8'))
        
        # Receive response
        response_data = b''
        client.settimeout(2)  # Timeout after 2 seconds
        
        try:
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                
                # Try to parse as JSON to check if we've received a complete response
                try:
                    json.loads(response_data.decode('utf-8'))
                    break  # If we can parse it, we have a complete response
                except json.JSONDecodeError:
                    continue  # Keep receiving
        except socket.timeout:
            self.fail("Timed out waiting for response")
            
        # Close connection
        client.close()
        
        # Check response
        response = json.loads(response_data.decode('utf-8'))
        self.assertEqual(response["status"], "success")
        self.assertEqual(response["message"], "Node created")
        self.assertEqual(response["node_path"], "/obj/test_geo")
        
        # Verify command executor was called with the correct command
        self.mock_command_executor.assert_called_once()
        args, _ = self.mock_command_executor.call_args
        self.assertEqual(args[0]["type"], "create_node")
        self.assertEqual(args[0]["params"]["node_name"], "test_geo")
        
    def test_invalid_json(self):
        """Test server's handling of invalid JSON"""
        # Connect to server
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('localhost', self.test_port))
        
        # Send invalid JSON
        client.sendall(b'{"type": "create_node", "params": {')
        
        # Send a valid closing marker to indicate the end of the invalid JSON
        client.sendall(b'}}')
        
        # Receive response
        response_data = b''
        client.settimeout(2)
        
        try:
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                
                try:
                    json.loads(response_data.decode('utf-8'))
                    break
                except json.JSONDecodeError:
                    continue
        except socket.timeout:
            self.fail("Timed out waiting for response")
            
        # Close connection
        client.close()
        
        # Check response indicates error
        response = json.loads(response_data.decode('utf-8'))
        self.assertEqual(response["status"], "error")
        
    def test_missing_type(self):
        """Test server's handling of commands with missing type"""
        # Connect to server
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('localhost', self.test_port))
        
        # Send command without type
        command = {
            "params": {
                "parent_path": "/obj",
                "node_type": "geo"
            }
        }
        client.sendall(json.dumps(command).encode('utf-8'))
        
        # Receive response
        response_data = b''
        client.settimeout(2)
        
        try:
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                
                try:
                    json.loads(response_data.decode('utf-8'))
                    break
                except json.JSONDecodeError:
                    continue
        except socket.timeout:
            self.fail("Timed out waiting for response")
            
        # Close connection
        client.close()
        
        # Check response indicates error about missing type
        response = json.loads(response_data.decode('utf-8'))
        self.assertEqual(response["status"], "error")
        self.assertIn("missing", response["message"].lower())
        self.assertIn("type", response["message"].lower())

if __name__ == '__main__':
    unittest.main() 