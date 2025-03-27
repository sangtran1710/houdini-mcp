import socket
import json
import logging
import sys
import os
from typing import Dict, Any, Optional, Union, List
from flask import Flask, request, jsonify, send_file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("HoudiniMCP.RESTProxy")

app = Flask(__name__)

# Default configuration
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8095
DEFAULT_API_PORT = 5000

# Path to schema file
SCHEMA_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "command_schema.json")

def send_to_socket(command_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send a command to the Houdini MCP socket server
    
    Args:
        command_data: Command data to send
    
    Returns:
        Dict containing the response from the server
    """
    try:
        # Create socket
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(10.0)  # 10 second timeout
        
        # Connect to server
        client.connect((DEFAULT_HOST, DEFAULT_PORT))
        logger.info(f"Connected to Houdini MCP server at {DEFAULT_HOST}:{DEFAULT_PORT}")
        
        # Send command
        command_json = json.dumps(command_data)
        client.sendall(command_json.encode('utf-8'))
        logger.info(f"Sent command: {command_json}")
        
        # Receive response
        response_data = b''
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            response_data += chunk
            
            # Try to parse the response to see if it's complete
            try:
                json.loads(response_data.decode('utf-8'))
                # If we can parse it, we have a complete response
                break
            except json.JSONDecodeError:
                # Not complete yet, continue receiving
                continue
                
        # Parse response
        response = json.loads(response_data.decode('utf-8'))
        logger.info(f"Received response: {json.dumps(response, indent=2)}")
        
        # Close connection
        client.close()
        
        return response
    except socket.timeout:
        logger.error("Connection to Houdini MCP server timed out")
        return {
            "status": "error",
            "code": 504,  # Gateway Timeout
            "message": "Connection to Houdini MCP server timed out"
        }
    except ConnectionRefusedError:
        logger.error(f"Connection to Houdini MCP server at {DEFAULT_HOST}:{DEFAULT_PORT} refused")
        return {
            "status": "error",
            "code": 503,  # Service Unavailable
            "message": f"Connection to Houdini MCP server at {DEFAULT_HOST}:{DEFAULT_PORT} refused. Is the server running?"
        }
    except Exception as e:
        logger.error(f"Error sending command to socket: {str(e)}")
        return {
            "status": "error",
            "code": 500,  # Internal Server Error
            "message": f"Error sending command to socket: {str(e)}"
        }

def load_command_schema() -> Dict[str, Any]:
    """
    Load the command schema from the JSON file
    
    Returns:
        Dict containing the command schema
    """
    try:
        if os.path.exists(SCHEMA_FILE_PATH):
            with open(SCHEMA_FILE_PATH, 'r') as f:
                return json.load(f)
        else:
            logger.warning(f"Schema file not found at {SCHEMA_FILE_PATH}")
            return {"error": "Schema file not found"}
    except Exception as e:
        logger.error(f"Error loading schema: {str(e)}")
        return {"error": f"Error loading schema: {str(e)}"}

@app.route('/mcp/command', methods=['POST'])
def handle_command():
    """
    Handle POST requests to /mcp/command
    
    Request body should be a JSON object with:
        - type: Command type
        - params: Command parameters (optional)
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                "status": "error",
                "code": 400,
                "message": "No JSON data received"
            }), 400
            
        # Validate data
        if not isinstance(data, dict):
            return jsonify({
                "status": "error",
                "code": 400,
                "message": "Invalid data format: expected JSON object"
            }), 400
            
        if "type" not in data:
            return jsonify({
                "status": "error",
                "code": 400,
                "message": "Missing required field: type"
            }), 400
            
        # Send command to socket server
        response = send_to_socket(data)
        
        # Return response with appropriate HTTP status code
        if response.get("status") == "error":
            code = response.get("code", 500)
            # Remove code from response to avoid duplication
            if "code" in response:
                del response["code"]
            return jsonify(response), code
        else:
            return jsonify(response), 200
    except Exception as e:
        logger.error(f"Error handling command: {str(e)}")
        return jsonify({
            "status": "error",
            "code": 500,
            "message": f"Error handling command: {str(e)}"
        }), 500

@app.route('/mcp/status', methods=['GET'])
def handle_status():
    """
    Handle GET requests to /mcp/status
    """
    try:
        # Send status command to socket server
        response = send_to_socket({
            "type": "list_available_commands"
        })
        
        # Check if we got a valid response
        if response.get("status") == "success":
            return jsonify({
                "status": "success",
                "message": "Houdini MCP server is running",
                "available_commands": response.get("commands", [])
            }), 200
        else:
            error_code = response.get("code", 500)
            return jsonify({
                "status": "error",
                "code": error_code,
                "message": "Houdini MCP server is not responding properly",
                "server_response": response
            }), error_code
    except Exception as e:
        logger.error(f"Error checking status: {str(e)}")
        return jsonify({
            "status": "error",
            "code": 500,
            "message": f"Error checking status: {str(e)}"
        }), 500

@app.route('/mcp/schema', methods=['GET'])
def handle_schema():
    """
    Handle GET requests to /mcp/schema
    Returns the schema for the available commands
    """
    try:
        # Load schema from file
        schema = load_command_schema()
        
        # Check if there was an error loading the schema
        if "error" in schema:
            return jsonify({
                "status": "error",
                "code": 500,
                "message": schema["error"]
            }), 500
            
        return jsonify(schema), 200
    except Exception as e:
        logger.error(f"Error retrieving schema: {str(e)}")
        return jsonify({
            "status": "error",
            "code": 500,
            "message": f"Error retrieving schema: {str(e)}"
        }), 500

@app.route('/mcp/schema/<command_name>', methods=['GET'])
def handle_command_schema(command_name):
    """
    Handle GET requests to /mcp/schema/<command_name>
    Returns the schema for a specific command
    """
    try:
        # Load schema from file
        schema = load_command_schema()
        
        # Check if there was an error loading the schema
        if "error" in schema:
            return jsonify({
                "status": "error",
                "code": 500,
                "message": schema["error"]
            }), 500
            
        # Get command-specific schema
        commands = schema.get("commands", {})
        if command_name in commands:
            return jsonify(commands[command_name]), 200
        else:
            return jsonify({
                "status": "error",
                "code": 404,
                "message": f"Command '{command_name}' not found in schema"
            }), 404
    except Exception as e:
        logger.error(f"Error retrieving command schema: {str(e)}")
        return jsonify({
            "status": "error",
            "code": 500,
            "message": f"Error retrieving command schema: {str(e)}"
        }), 500

def main() -> None:
    """
    Main entry point for the REST proxy
    """
    global DEFAULT_HOST, DEFAULT_PORT, DEFAULT_API_PORT
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        try:
            DEFAULT_PORT = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port number: {sys.argv[1]}")
            print(f"Using default: {DEFAULT_PORT}")
    
    if len(sys.argv) > 2:
        try:
            DEFAULT_API_PORT = int(sys.argv[2])
        except ValueError:
            print(f"Invalid API port number: {sys.argv[2]}")
            print(f"Using default: {DEFAULT_API_PORT}")
    
    # Start REST API server
    logger.info(f"Starting REST API server on localhost:{DEFAULT_API_PORT}")
    logger.info(f"Will forward requests to socket server at {DEFAULT_HOST}:{DEFAULT_PORT}")
    logger.info("For security reasons, the API will only accept connections from localhost")
    
    # Run Flask app - only accept connections from localhost (127.0.0.1)
    app.run(host="127.0.0.1", port=DEFAULT_API_PORT)

if __name__ == "__main__":
    main() 