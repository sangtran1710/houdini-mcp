from mcp.server.fastmcp import FastMCP, Context, Image
import socket
import json
import asyncio
import logging
from dataclasses import dataclass
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, List, Optional
import os
from pathlib import Path
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("HoudiniMCPServer")

@dataclass
class HoudiniConnection:
    host: str
    port: int
    sock: socket.socket = None
    
    def connect(self) -> bool:
        """Connect to the Houdini plugin socket server"""
        if self.sock:
            return True
            
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            logger.info(f"Connected to Houdini at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Houdini: {str(e)}")
            self.sock = None
            return False
    
    def disconnect(self):
        """Disconnect from the Houdini plugin"""
        if self.sock:
            try:
                self.sock.close()
            except Exception as e:
                logger.error(f"Error disconnecting from Houdini: {str(e)}")
            finally:
                self.sock = None

    def receive_full_response(self, sock, buffer_size=8192):
        """Receive the complete response, potentially in multiple chunks"""
        chunks = []
        # Set timeout for receiving data
        sock.settimeout(15.0)  # 15 seconds timeout
        
        try:
            while True:
                try:
                    chunk = sock.recv(buffer_size)
                    if not chunk:
                        # If we get an empty chunk, the connection might be closed
                        if not chunks:  # If we haven't received anything yet, this is an error
                            raise Exception("Connection closed before receiving any data")
                        break
                    
                    chunks.append(chunk)
                    
                    # Check if we've received a complete JSON object
                    try:
                        data = b''.join(chunks)
                        json.loads(data.decode('utf-8'))
                        # If we get here, it parsed successfully
                        logger.info(f"Received complete response ({len(data)} bytes)")
                        return data
                    except json.JSONDecodeError:
                        # Incomplete JSON, continue receiving
                        continue
                except socket.timeout:
                    # If we hit a timeout during receiving, break the loop and try to use what we have
                    logger.warning("Socket timeout during chunked receive")
                    break
                except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
                    logger.error(f"Socket connection error during receive: {str(e)}")
                    raise  # Re-raise to be handled by the caller
        except socket.timeout:
            logger.warning("Socket timeout during chunked receive")
        except Exception as e:
            logger.error(f"Error during receive: {str(e)}")
            raise
            
        # If we get here, we either timed out or broke out of the loop
        # Try to use what we have
        if chunks:
            data = b''.join(chunks)
            logger.info(f"Returning data after receive completion ({len(data)} bytes)")
            try:
                # Try to parse what we have
                json.loads(data.decode('utf-8'))
                return data
            except json.JSONDecodeError:
                # If we can't parse it, it's incomplete
                raise Exception("Incomplete JSON response received")
        else:
            raise Exception("No data received")

    def send_command(self, command_type: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send a command to Houdini and return the response"""
        if not self.sock and not self.connect():
            raise ConnectionError("Not connected to Houdini")
        
        command = {
            "type": command_type,
            "params": params or {}
        }
        
        try:
            # Log the command being sent
            logger.info(f"Sending command: {command_type} with params: {params}")
            
            # Send the command
            self.sock.sendall(json.dumps(command).encode('utf-8'))
            logger.info(f"Command sent, waiting for response...")
            
            # Set a timeout for receiving
            self.sock.settimeout(15.0)  # 15 seconds timeout
            
            # Receive the response using the improved receive_full_response method
            response_data = self.receive_full_response(self.sock)
            logger.info(f"Received {len(response_data)} bytes of data")
            
            response = json.loads(response_data.decode('utf-8'))
            logger.info(f"Response parsed, status: {response.get('status', 'unknown')}")
            
            if response.get("status") == "error":
                logger.error(f"Houdini error: {response.get('message')}")
                raise Exception(response.get("message", "Unknown error from Houdini"))
            
            return response.get("result", {})
        except socket.timeout:
            logger.error("Socket timeout while waiting for response from Houdini")
            # Invalidate the current socket so it will be recreated next time
            self.sock = None
            raise Exception("Timeout waiting for Houdini response - try simplifying your request")
        except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
            logger.error(f"Socket connection error: {str(e)}")
            self.sock = None
            raise Exception(f"Connection to Houdini lost: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from Houdini: {str(e)}")
            # Try to log what was received
            if 'response_data' in locals() and response_data:
                logger.error(f"Raw response (first 200 bytes): {response_data[:200]}")
            raise Exception(f"Invalid response from Houdini: {str(e)}")
        except Exception as e:
            logger.error(f"Error communicating with Houdini: {str(e)}")
            # Invalidate the current socket
            self.sock = None
            raise Exception(f"Communication error with Houdini: {str(e)}")

# Global connection instance
_houdini_connection = None

def get_houdini_connection() -> HoudiniConnection:
    """Get or create the global Houdini connection"""
    global _houdini_connection
    
    if not _houdini_connection:
        # Default connection parameters
        host = os.environ.get("HOUDINI_MCP_HOST", "localhost")
        port = int(os.environ.get("HOUDINI_MCP_PORT", "9876"))
        
        logger.info(f"Creating new Houdini connection to {host}:{port}")
        _houdini_connection = HoudiniConnection(host=host, port=port)
    
    # Ensure connection is active
    if not _houdini_connection.sock:
        logger.info("Connecting to Houdini...")
        if not _houdini_connection.connect():
            raise ConnectionError("Could not connect to Houdini - make sure the plugin is running")
    
    return _houdini_connection

@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """Manage server startup and shutdown lifecycle"""
    try:
        # Just log that we're starting up
        logger.info("HoudiniMCP server starting up")
        
        # Try to connect to Houdini on startup to verify it's available
        try:
            # This will initialize the global connection if needed
            houdini = get_houdini_connection()
            logger.info("Successfully connected to Houdini on startup")
        except Exception as e:
            logger.warning(f"Could not connect to Houdini on startup: {str(e)}")
            logger.warning("Make sure the Houdini plugin is running before using Houdini resources or tools")
        
        # Return an empty context - we're using the global connection
        yield {}
    finally:
        # Clean up the global connection on shutdown
        global _houdini_connection
        if _houdini_connection:
            logger.info("Disconnecting from Houdini on shutdown")
            _houdini_connection.disconnect()
            _houdini_connection = None
        logger.info("HoudiniMCP server shut down")

# Create the MCP server with lifespan support
mcp = FastMCP(
    "HoudiniMCP",
    description="Houdini integration through the Model Context Protocol",
    lifespan=server_lifespan
)

# Resource endpoints

@mcp.resource()
def get_scene_info() -> Dict[str, Any]:
    """
    Get detailed information about the current Houdini scene
    
    Returns information about the current Houdini scene, including:
    - File path and name
    - Frame rate
    - Current frame
    - Playback range
    - List of top-level objects
    """
    houdini = get_houdini_connection()
    return houdini.send_command("get_scene_info")

@mcp.resource()
def get_object_info(object_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific object in the Houdini scene
    
    Parameters:
    - object_name: The name or path of the object to get information about
    
    Returns detailed information about the specified object, including:
    - Node type
    - Node path
    - Parent and children
    - Parameters and their values
    """
    houdini = get_houdini_connection()
    return houdini.send_command("get_object_info", {"object_name": object_name})

# Tool endpoints

@mcp.tool()
def create_object(
    type: str = "geo",
    name: Optional[str] = None,
    parent_path: str = "/obj",
    sop_type: Optional[str] = None,
    sop_name: Optional[str] = None,
    sop_params: Optional[Dict[str, Any]] = None,
    parameters: Optional[Dict[str, Any]] = None,
    position: Optional[List[float]] = None
) -> Dict[str, Any]:
    """
    Create a new object in the Houdini scene
    
    Parameters:
    - type: Type of object to create (default: "geo")
    - name: Name for the object (optional)
    - parent_path: Path to the parent node (default: "/obj")
    - sop_type: Type of SOP to create inside the object (optional, for geo nodes)
    - sop_name: Name for the SOP (optional)
    - sop_params: Parameters for the SOP (optional)
    - parameters: Parameters for the object (optional)
    - position: Position [x, y] for the node in the network (optional)
    """
    houdini = get_houdini_connection()
    
    return houdini.send_command("create_object", {
        "type": type,
        "name": name,
        "parent_path": parent_path,
        "sop_type": sop_type,
        "sop_name": sop_name,
        "sop_params": sop_params or {},
        "parameters": parameters or {},
        "position": position
    })

@mcp.tool()
def modify_object(
    name: str,
    parameters: Optional[Dict[str, Any]] = None,
    position: Optional[List[float]] = None
) -> Dict[str, Any]:
    """
    Modify an existing object in the Houdini scene
    
    Parameters:
    - name: Name or path of the object to modify
    - parameters: Parameters to update (optional)
    - position: New position [x, y] for the node in the network (optional)
    """
    houdini = get_houdini_connection()
    
    return houdini.send_command("modify_object", {
        "name": name,
        "parameters": parameters or {},
        "position": position
    })

@mcp.tool()
def delete_object(name: str) -> Dict[str, Any]:
    """
    Delete an object from the Houdini scene
    
    Parameters:
    - name: Name or path of the object to delete
    """
    houdini = get_houdini_connection()
    
    return houdini.send_command("delete_object", {
        "name": name
    })

@mcp.tool()
def set_material(
    object_name: str,
    material_name: Optional[str] = None,
    color: Optional[List[float]] = None,
    roughness: Optional[float] = None,
    metallic: Optional[float] = None
) -> Dict[str, Any]:
    """
    Set or create a material for an object
    
    Parameters:
    - object_name: Name or path of the object to apply the material to
    - material_name: Name for the material (optional)
    - color: RGB color values [r, g, b] between 0-1 (optional)
    - roughness: Roughness value between 0-1 (optional)
    - metallic: Metallic value between 0-1 (optional)
    """
    houdini = get_houdini_connection()
    
    return houdini.send_command("set_material", {
        "object_name": object_name,
        "material_name": material_name,
        "color": color,
        "roughness": roughness,
        "metallic": metallic
    })

@mcp.tool()
def create_fluid_simulation(
    name: Optional[str] = None,
    source_type: str = "box",
    source_size: Optional[List[float]] = None,
    source_position: Optional[List[float]] = None,
    source_radius: Optional[float] = None,
    resolution: int = 100,
    viscosity: float = 0.0,
    create_collision: bool = False,
    collision_type: str = "box",
    collision_size: Optional[List[float]] = None,
    collision_position: Optional[List[float]] = None,
    start_frame: int = 1,
    end_frame: int = 100
) -> Dict[str, Any]:
    """
    Create a FLIP fluid simulation in Houdini
    
    Parameters:
    - name: Name for the simulation container (optional)
    - source_type: Type of source geometry ("box" or "sphere")
    - source_size: Size of the source box [x, y, z] (for box source)
    - source_position: Position of the source [x, y, z]
    - source_radius: Radius of the source (for sphere source)
    - resolution: Simulation resolution (higher is more detailed but slower)
    - viscosity: Fluid viscosity (0 = water, higher values = more viscous)
    - create_collision: Whether to create collision geometry
    - collision_type: Type of collision geometry ("box" or "sphere")
    - collision_size: Size of the collision box [x, y, z] (for box collision)
    - collision_position: Position of the collision [x, y, z]
    - start_frame: Start frame for the simulation
    - end_frame: End frame for the simulation
    """
    houdini = get_houdini_connection()
    
    return houdini.send_command("create_fluid_simulation", {
        "name": name,
        "source_type": source_type,
        "source_size": source_size or [1, 1, 1],
        "source_position": source_position or [0, 0, 0],
        "source_radius": source_radius,
        "resolution": resolution,
        "viscosity": viscosity,
        "create_collision": create_collision,
        "collision_type": collision_type,
        "collision_size": collision_size or [2, 2, 2],
        "collision_position": collision_position or [0, 0, 0],
        "start_frame": start_frame,
        "end_frame": end_frame
    })

@mcp.tool()
def create_pyro_simulation(
    name: Optional[str] = None,
    sim_type: str = "fire",  # "fire", "smoke", or "both"
    source_type: str = "box",
    source_size: Optional[List[float]] = None,
    source_position: Optional[List[float]] = None,
    source_radius: Optional[float] = None,
    resolution: int = 100,
    temperature: float = 1.0,
    fuel_amount: float = 1.0,
    smoke_density: float = 1.0,
    add_forces: bool = False,
    force_type: str = "wind",
    wind_direction: Optional[List[float]] = None,
    wind_strength: float = 1.0
) -> Dict[str, Any]:
    """
    Create a Pyro simulation (fire, smoke) in Houdini
    
    Parameters:
    - name: Name for the simulation container (optional)
    - sim_type: Type of simulation ("fire", "smoke", or "both")
    - source_type: Type of source geometry ("box" or "sphere")
    - source_size: Size of the source box [x, y, z] (for box source)
    - source_position: Position of the source [x, y, z]
    - source_radius: Radius of the source (for sphere source)
    - resolution: Simulation resolution (higher is more detailed but slower)
    - temperature: Base temperature for fire (higher = more intense fire)
    - fuel_amount: Amount of fuel for fire
    - smoke_density: Density of smoke
    - add_forces: Whether to add force fields to the simulation
    - force_type: Type of force ("wind" or "turbulence")
    - wind_direction: Direction of wind [x, y, z]
    - wind_strength: Strength of the wind force
    """
    houdini = get_houdini_connection()
    
    return houdini.send_command("create_pyro_simulation", {
        "name": name,
        "sim_type": sim_type,
        "source_type": source_type,
        "source_size": source_size or [1, 1, 1],
        "source_position": source_position or [0, 0, 0],
        "source_radius": source_radius,
        "resolution": resolution,
        "temperature": temperature,
        "fuel_amount": fuel_amount,
        "smoke_density": smoke_density,
        "add_forces": add_forces,
        "force_type": force_type,
        "wind_direction": wind_direction or [0, 0, 1],
        "wind_strength": wind_strength
    })

@mcp.tool()
def simulate(
    node_path: str,
    start_frame: Optional[int] = None,
    end_frame: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run a simulation for a specified node or DOP network
    
    Parameters:
    - node_path: Path to the node to simulate (DOP network or container)
    - start_frame: Start frame for the simulation (optional)
    - end_frame: End frame for the simulation (optional)
    """
    houdini = get_houdini_connection()
    
    return houdini.send_command("simulate", {
        "node_path": node_path,
        "start_frame": start_frame,
        "end_frame": end_frame
    })

@mcp.tool()
def execute_houdini_code(code: str) -> Dict[str, Any]:
    """
    Execute arbitrary Python code in Houdini
    
    Parameters:
    - code: The Python code to execute in Houdini
    
    Warning: This allows running arbitrary code in Houdini. Use with caution!
    """
    houdini = get_houdini_connection()
    
    return houdini.send_command("execute_houdini_code", {
        "code": code
    })

# Main entry point
def main():
    """Run the HoudiniMCP server"""
    logger.info("Starting HoudiniMCP server...")
    mcp.run()

if __name__ == "__main__":
    main() 