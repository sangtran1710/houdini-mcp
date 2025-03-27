import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rest_to_socket_proxy import app, send_to_socket, load_command_schema

class TestRestApi(unittest.TestCase):
    """Test cases for the REST API proxy"""

    def setUp(self):
        """Set up test client"""
        app.config['TESTING'] = True
        self.client = app.test_client()
        
    @patch('rest_to_socket_proxy.send_to_socket')
    def test_command_execution_success(self, mock_send_to_socket):
        """Test successful command execution"""
        # Mock the socket response
        mock_send_to_socket.return_value = {
            "status": "success",
            "message": "Command executed successfully"
        }
        
        # Send a test command
        response = self.client.post('/mcp/command', 
            json={
                "type": "create_node",
                "params": {
                    "parent_path": "/obj",
                    "node_type": "geo",
                    "node_name": "test_geo"
                }
            })
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["message"], "Command executed successfully")
        
        # Verify the socket function was called with correct parameters
        mock_send_to_socket.assert_called_once()
        args = mock_send_to_socket.call_args[0][0]
        self.assertEqual(args["type"], "create_node")
        self.assertEqual(args["params"]["node_name"], "test_geo")
        
    @patch('rest_to_socket_proxy.send_to_socket')
    def test_command_execution_error(self, mock_send_to_socket):
        """Test command execution with error"""
        # Mock the socket response for an error
        mock_send_to_socket.return_value = {
            "status": "error",
            "code": 400,
            "message": "Invalid parameters"
        }
        
        # Send a test command with invalid params
        response = self.client.post('/mcp/command', 
            json={
                "type": "create_node",
                "params": {
                    # Missing required "node_type"
                    "parent_path": "/obj"
                }
            })
        
        # Check response has error status code
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["message"], "Invalid parameters")
        
    def test_missing_command_type(self):
        """Test request with missing command type"""
        response = self.client.post('/mcp/command', 
            json={
                "params": {
                    "parent_path": "/obj"
                }
            })
        
        # Check response has error status code
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["message"], "Missing required field: type")
    
    @patch('rest_to_socket_proxy.send_to_socket')
    def test_status_endpoint(self, mock_send_to_socket):
        """Test the status endpoint"""
        # Mock the socket response
        mock_send_to_socket.return_value = {
            "status": "success",
            "commands": ["create_node", "set_param"]
        }
        
        # Send a status request
        response = self.client.get('/mcp/status')
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["message"], "Houdini MCP server is running")
        self.assertEqual(data["available_commands"], ["create_node", "set_param"])
    
    @patch('rest_to_socket_proxy.load_command_schema')
    def test_schema_endpoint(self, mock_load_schema):
        """Test the schema endpoint"""
        # Mock the schema response
        mock_schema = {
            "schema_version": "1.0",
            "commands": {
                "create_node": {
                    "description": "Create a new node in Houdini",
                    "params": {},
                    "required_params": ["node_type"]
                }
            }
        }
        mock_load_schema.return_value = mock_schema
        
        # Send a schema request
        response = self.client.get('/mcp/schema')
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["schema_version"], "1.0")
        self.assertTrue("create_node" in data["commands"])
        
    @patch('rest_to_socket_proxy.load_command_schema')
    def test_command_schema_endpoint(self, mock_load_schema):
        """Test the command-specific schema endpoint"""
        # Mock the schema response
        mock_schema = {
            "schema_version": "1.0",
            "commands": {
                "create_node": {
                    "description": "Create a new node in Houdini",
                    "params": {},
                    "required_params": ["node_type"]
                }
            }
        }
        mock_load_schema.return_value = mock_schema
        
        # Send a command schema request
        response = self.client.get('/mcp/schema/create_node')
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["description"], "Create a new node in Houdini")
        
    @patch('rest_to_socket_proxy.load_command_schema')
    def test_command_schema_endpoint_not_found(self, mock_load_schema):
        """Test the command-specific schema endpoint with non-existent command"""
        # Mock the schema response
        mock_schema = {
            "schema_version": "1.0",
            "commands": {
                "create_node": {
                    "description": "Create a new node in Houdini",
                    "params": {},
                    "required_params": ["node_type"]
                }
            }
        }
        mock_load_schema.return_value = mock_schema
        
        # Send a command schema request for non-existent command
        response = self.client.get('/mcp/schema/non_existent_command')
        
        # Check response
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["message"], "Command 'non_existent_command' not found in schema")

if __name__ == '__main__':
    unittest.main() 