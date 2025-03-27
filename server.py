import socket
import threading
import time
import traceback
import json
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("HoudiniMCP.Server")

class HoudiniMCPServer:
    def __init__(self, host='localhost', port=9876, command_executor=None):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.server_thread = None
        self.logger = logger
        # This will be set from outside to handle command execution
        self.command_executor = command_executor
    
    def log(self, level, message):
        """Log a message with the specified level"""
        if level == "info":
            self.logger.info(message)
            print(message)  # Also print for backwards compatibility
        elif level == "error":
            self.logger.error(message)
            print(message)  # Also print for backwards compatibility
        elif level == "debug":
            self.logger.debug(message)
        elif level == "warning":
            self.logger.warning(message)
            print(message)  # Also print for backwards compatibility
        else:
            print(message)  # Fallback to print
    
    def start(self):
        if self.running:
            self.log("info", "Server is already running")
            return True
            
        self.running = True
        
        try:
            # Create socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            
            # Start server thread
            self.server_thread = threading.Thread(target=self._server_loop)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            self.log("info", f"HoudiniMCP server started on {self.host}:{self.port}")
            return True
        except Exception as e:
            self.log("error", f"Failed to start server: {str(e)}")
            self.stop()
            return False
            
    def stop(self):
        self.running = False
        
        # Close socket
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        # Wait for thread to finish
        if self.server_thread:
            try:
                if self.server_thread.is_alive():
                    self.server_thread.join(timeout=1.0)
            except:
                pass
            self.server_thread = None
        
        self.log("info", "HoudiniMCP server stopped")
    
    def _server_loop(self):
        """Main server loop in a separate thread"""
        self.log("info", "Server thread started")
        self.socket.settimeout(1.0)  # Timeout to allow for stopping
        
        while self.running:
            try:
                # Accept new connection
                try:
                    client, address = self.socket.accept()
                    self.log("info", f"Connected to client: {address}")
                    
                    # Handle client in a separate thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client,)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    # Just check running condition
                    continue
                except Exception as e:
                    self.log("error", f"Error accepting connection: {str(e)}")
                    time.sleep(0.5)
            except Exception as e:
                self.log("error", f"Error in server loop: {str(e)}")
                if not self.running:
                    break
                time.sleep(0.5)
        
        self.log("info", "Server thread stopped")
    
    def _handle_client(self, client):
        """Handle connected client"""
        self.log("info", "Client handler started")
        client.settimeout(None)  # No timeout
        buffer = b''
        
        try:
            while self.running:
                # Receive data
                try:
                    data = client.recv(8192)
                    if not data:
                        self.log("info", "Client disconnected")
                        break
                    
                    # Check if data is empty after whitespace stripping
                    if len(data.strip()) == 0:
                        self.log("warning", "Empty data received")
                        error_response = {
                            "status": "error",
                            "message": "Empty request received from client"
                        }
                        client.sendall(json.dumps(error_response).encode('utf-8'))
                        continue
                    
                    buffer += data
                    try:
                        # Try to parse command
                        try:
                            command_str = buffer.decode('utf-8')
                            if not command_str.strip():
                                self.log("warning", "Empty JSON after buffer decode")
                                error_response = {
                                    "status": "error",
                                    "message": "Empty request received from client"
                                }
                                client.sendall(json.dumps(error_response).encode('utf-8'))
                                buffer = b''
                                continue
                            
                            command = json.loads(command_str)
                            buffer = b''
                            
                            self.log("info", f"Received command: {json.dumps(command, indent=2)}")
                        except json.JSONDecodeError as e:
                            # Only handle complete but invalid JSON - if it's incomplete, wait for more data
                            if buffer.endswith(b'}') or buffer.endswith(b']'):
                                self.log("warning", f"Invalid JSON received: {str(e)}")
                                error_response = {
                                    "status": "error",
                                    "message": f"Invalid JSON received: {str(e)}"
                                }
                                client.sendall(json.dumps(error_response).encode('utf-8'))
                                buffer = b''
                                continue
                            else:
                                # Incomplete JSON, wait for more data
                                continue
                        
                        # Validate command format
                        if not isinstance(command, dict):
                            self.log("warning", f"Command is not a dictionary: {command}")
                            error_response = {
                                "status": "error",
                                "message": "Invalid command format: expected JSON object"
                            }
                            client.sendall(json.dumps(error_response).encode('utf-8'))
                            continue
                        
                        if "type" not in command:
                            self.log("warning", f"Command missing 'type' field: {command}")
                            error_response = {
                                "status": "error",
                                "message": "Invalid command format: missing 'type' field"
                            }
                            client.sendall(json.dumps(error_response).encode('utf-8'))
                            continue
                        
                        # If command_executor is available, use it to execute the command
                        if self.command_executor:
                            try:
                                # Execute the command
                                response = self.command_executor(command)
                                
                                # Ensure the response is a properly formatted dictionary
                                if not isinstance(response, dict):
                                    self.log("warning", f"Response is not a dictionary: {response}")
                                    response = {
                                        "status": "error",
                                        "message": f"Invalid response format: {str(response)}"
                                    }
                                
                                # Ensure the response has a status field
                                if "status" not in response:
                                    self.log("warning", f"Response missing status field: {response}")
                                    if "error" in response:
                                        # Convert old error format to new status format
                                        response = {
                                            "status": "error",
                                            "message": response["error"]
                                        }
                                    else:
                                        # Add a default success status
                                        response["status"] = "success"
                                
                                # Ensure there's a message field
                                if "message" not in response and response["status"] == "success":
                                    self.log("warning", f"Success response missing message field: {response}")
                                    response["message"] = "Command executed successfully"
                                
                                # Convert response to JSON and send
                                try:
                                    # Debug print before JSON serialization
                                    self.log("info", f"Preparing to send response: {response}")
                                    
                                    response_json = json.dumps(response)
                                    # Debug print after JSON serialization
                                    self.log("info", f"Serialized JSON response: {response_json}")
                                    
                                    client.sendall(response_json.encode('utf-8'))
                                    self.log("info", f"Response sent successfully")
                                except Exception as e:
                                    self.log("error", f"Failed to send response: {str(e)}")
                                    traceback.print_exc()
                            except Exception as e:
                                self.log("error", f"Error executing command: {str(e)}")
                                traceback.print_exc()
                                try:
                                    error_response = {
                                        "status": "error",
                                        "message": str(e)
                                    }
                                    error_json = json.dumps(error_response)
                                    self.log("info", f"Sending error response: {error_json}")
                                    client.sendall(error_json.encode('utf-8'))
                                except Exception as send_err:
                                    self.log("error", f"Failed to send error response: {str(send_err)}")
                                    traceback.print_exc()
                        else:
                            # If no command executor is available, return an error
                            self.log("error", "No command executor available")
                            error_response = {
                                "status": "error",
                                "message": "Server is not configured to execute commands"
                            }
                            client.sendall(json.dumps(error_response).encode('utf-8'))
                    except Exception as e:
                        # Handle any other exception in the command processing logic
                        self.log("error", f"Error processing command: {str(e)}")
                        traceback.print_exc()
                        try:
                            error_response = {
                                "status": "error",
                                "message": f"Error processing command: {str(e)}"
                            }
                            client.sendall(json.dumps(error_response).encode('utf-8'))
                        except Exception as send_err:
                            self.log("error", f"Failed to send error response: {str(send_err)}")
                except Exception as e:
                    self.log("error", f"Error receiving data: {str(e)}")
                    traceback.print_exc()
                    break
        except Exception as e:
            self.log("error", f"Error in client handler: {str(e)}")
            traceback.print_exc()
        finally:
            try:
                client.close()
            except:
                pass
            self.log("info", "Client handler stopped") 