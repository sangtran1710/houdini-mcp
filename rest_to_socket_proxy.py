import socket
import json
import logging
from flask import Flask, request, jsonify

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("HoudiniMCPProxy")

# Configuration
HOUDINI_HOST = "localhost"
HOUDINI_PORT = 9876  # Default port used by HoudiniMCP plugin
SOCKET_TIMEOUT = 15  # Seconds
BUFFER_SIZE = 8192   # Bytes

app = Flask(__name__)

def send_to_houdini(command_json):
    """Send a command to Houdini via socket and return the response"""
    try:
        # Create a socket connection to Houdini
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(SOCKET_TIMEOUT)
        sock.connect((HOUDINI_HOST, HOUDINI_PORT))
        logger.info(f"Connected to Houdini at {HOUDINI_HOST}:{HOUDINI_PORT}")
        
        # Send command to Houdini
        command_data = json.dumps(command_json).encode('utf-8')
        sock.sendall(command_data)
        logger.info(f"Sent command: {command_json}")
        
        # Receive response from Houdini
        response_data = receive_full_response(sock)
        logger.info(f"Received response: {response_data[:200]}...")  # Log first 200 chars
        
        # Parse response as JSON
        return json.loads(response_data)
        
    except socket.timeout:
        logger.error("Socket timeout while communicating with Houdini")
        return {
            "status": "error", 
            "message": "Timeout while communicating with Houdini"
        }
    except ConnectionRefusedError:
        logger.error(f"Connection refused - Houdini MCP plugin not running at {HOUDINI_HOST}:{HOUDINI_PORT}")
        return {
            "status": "error", 
            "message": f"Connection refused - Houdini MCP plugin not running at {HOUDINI_HOST}:{HOUDINI_PORT}"
        }
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response from Houdini: {e}")
        return {
            "status": "error", 
            "message": f"Invalid response format from Houdini: {e}"
        }
    except Exception as e:
        logger.error(f"Error communicating with Houdini: {str(e)}")
        return {
            "status": "error", 
            "message": f"Error communicating with Houdini: {str(e)}"
        }
    finally:
        # Close the socket
        try:
            sock.close()
        except:
            pass

def receive_full_response(sock, buffer_size=BUFFER_SIZE):
    """Receive the complete response, potentially in multiple chunks"""
    chunks = []
    
    try:
        while True:
            chunk = sock.recv(buffer_size)
            if not chunk:
                break
                
            chunks.append(chunk)
            
            # Try to parse as JSON to check if we've received a complete response
            try:
                data = b''.join(chunks)
                # Convert to string (handle potential byte issues)
                if isinstance(data, bytes):
                    data_str = data.decode('utf-8')
                else:
                    data_str = data
                    
                # Try to parse JSON to see if we have a complete response
                json.loads(data_str)
                # If we get here, it parsed successfully
                return data_str
            except json.JSONDecodeError:
                # Incomplete JSON, continue receiving
                continue
        
        # If we get here, the connection closed normally
        data = b''.join(chunks)
        if isinstance(data, bytes):
            return data.decode('utf-8')
        return data
    
    except socket.timeout:
        # If we timeout, return what we have so far
        if chunks:
            data = b''.join(chunks)
            if isinstance(data, bytes):
                return data.decode('utf-8')
            return data
        raise  # Reraise the timeout if we have no data
        
@app.route('/houdini/run', methods=['POST'])
def houdini_run():
    """Handle requests to execute Houdini commands"""
    try:
        # Get the request data
        data = request.json
        
        if not data:
            return jsonify({
                "status": "error", 
                "message": "No data provided"
            }), 400
            
        logger.info(f"Received request: {data}")
        
        # Extract command and arguments
        command_type = data.get("command")
        args = data.get("args", {})
        
        if not command_type:
            return jsonify({
                "status": "error", 
                "message": "No command specified"
            }), 400
            
        # Format command for HoudiniMCP plugin
        houdini_command = {
            "type": command_type,
            "params": args
        }
        
        # Send command to Houdini and get response
        response = send_to_houdini(houdini_command)
        
        # Return response
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error processing request: {str(e)}"
        }), 500

if __name__ == '__main__':
    logger.info("Starting Houdini MCP REST API proxy on port 7860")
    logger.info(f"Configured to connect to Houdini at {HOUDINI_HOST}:{HOUDINI_PORT}")
    app.run(host='0.0.0.0', port=7860, debug=False) 