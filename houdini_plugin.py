import hou
import json
import threading
import socket
import time
import traceback
import os
import tempfile
from typing import Dict, Any, List, Optional
import math

# Metadata for plugin
PLUGIN_NAME = "HoudiniMCP"
PLUGIN_VERSION = "1.0.0"
PLUGIN_DESCRIPTION = "Connect Houdini to Claude via MCP"

class HoudiniMCPServer:
    def __init__(self, host='localhost', port=9876):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.server_thread = None
    
    def start(self):
        if self.running:
            print("Server is already running")
            return
            
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
            
            print(f"HoudiniMCP server started on {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"Failed to start server: {str(e)}")
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
        
        print("HoudiniMCP server stopped")
    
    def _server_loop(self):
        """Main server loop in a separate thread"""
        print("Server thread started")
        self.socket.settimeout(1.0)  # Timeout to allow for stopping
        
        while self.running:
            try:
                # Accept new connection
                try:
                    client, address = self.socket.accept()
                    print(f"Connected to client: {address}")
                    
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
                    print(f"Error accepting connection: {str(e)}")
                    time.sleep(0.5)
            except Exception as e:
                print(f"Error in server loop: {str(e)}")
                if not self.running:
                    break
                time.sleep(0.5)
        
        print("Server thread stopped")
    
    def _handle_client(self, client):
        """Handle connected client"""
        print("Client handler started")
        client.settimeout(None)  # No timeout
        buffer = b''
        
        try:
            while self.running:
                # Receive data
                try:
                    data = client.recv(8192)
                    if not data:
                        print("Client disconnected")
                        break
                    
                    buffer += data
                    try:
                        # Try to parse command
                        command = json.loads(buffer.decode('utf-8'))
                        buffer = b''
                        
                        # Execute command in Houdini's main thread
                        def execute_wrapper():
                            try:
                                response = self.execute_command(command)
                                response_json = json.dumps(response)
                                try:
                                    client.sendall(response_json.encode('utf-8'))
                                except:
                                    print("Failed to send response - client disconnected")
                            except Exception as e:
                                print(f"Error executing command: {str(e)}")
                                traceback.print_exc()
                                try:
                                    error_response = {
                                        "status": "error",
                                        "message": str(e)
                                    }
                                    client.sendall(json.dumps(error_response).encode('utf-8'))
                                except:
                                    pass
                            return None
                        
                        # Schedule execution in main thread using Houdini's event loop
                        hou.ui.postEvent(execute_wrapper)
                    except json.JSONDecodeError:
                        # Incomplete data, wait for more
                        pass
                except Exception as e:
                    print(f"Error receiving data: {str(e)}")
                    break
        except Exception as e:
            print(f"Error in client handler: {str(e)}")
        finally:
            try:
                client.close()
            except:
                pass
            print("Client handler stopped")

    def execute_command(self, command):
        """Execute a command in the main Houdini thread"""
        try:
            # This function is already being called in the main thread via postEvent
            return self._execute_command_internal(command)
        except Exception as e:
            print(f"Error executing command: {str(e)}")
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def _execute_command_internal(self, command):
        """Internal command execution with proper context"""
        cmd_type = command.get("type")
        params = command.get("params", {})

        # Node creation and manipulation commands
        if cmd_type == "create_node":
            return self.create_node(params)
        elif cmd_type == "connect_nodes":
            return self.connect_nodes(params)
        elif cmd_type == "set_param":
            return self.set_param(params)
            
        # Scene information commands
        elif cmd_type == "get_scene_info":
            return {"status": "success", "result": self.get_scene_info()}
        elif cmd_type == "get_object_info":
            return {"status": "success", "result": self.get_object_info(params.get("object_name"))}
            
        # Simulation commands
        elif cmd_type == "create_fluid_sim":
            return self.create_fluid_sim(params)
        elif cmd_type == "create_pyro_sim":
            return self.create_pyro_sim(params)
        elif cmd_type == "run_simulation":
            return self.run_simulation(params)
            
        # Code execution command
        elif cmd_type == "execute_houdini_code":
            return self.execute_houdini_code(params.get("code", ""))
        else:
            return {"status": "error", "message": f"Unknown command type: {cmd_type}"}

    # Core functionality commands
    def create_node(self, params):
        """Create a node of specified type under a parent"""
        parent_path = params.get("parent_path", "/obj")
        node_type = params.get("node_type")
        node_name = params.get("node_name", None)
        
        if not node_type:
            return {
                "status": "error", 
                "message": "Missing required parameter: node_type"
            }
            
        try:
            # Get parent node
            try:
                parent = hou.node(parent_path)
                if not parent:
                    return {
                        "status": "error",
                        "message": f"Parent node not found: {parent_path}"
                    }
            except hou.OperationFailed as e:
                return {
                    "status": "error",
                    "message": f"Invalid parent path: {parent_path}. Error: {str(e)}"
                }
                
            # Create the node
            try:
                node = parent.createNode(node_type, node_name)
                node_path = node.path()
                
                return {
                    "status": "success",
                    "message": f"Node created: {node_path}",
                    "node_path": node_path
                }
            except hou.OperationFailed as e:
                return {
                    "status": "error",
                    "message": f"Failed to create node of type {node_type}. Error: {str(e)}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error creating node: {str(e)}"
            }
    
    def connect_nodes(self, params):
        """Connect two nodes together"""
        from_path = params.get("from_path")
        to_path = params.get("to_path")
        input_index = params.get("input_index", 0)
        
        if not from_path or not to_path:
            return {
                "status": "error",
                "message": "Missing required parameters: from_path and to_path"
            }
            
        try:
            # Get nodes
            from_node = hou.node(from_path)
            if not from_node:
                return {
                    "status": "error",
                    "message": f"Source node not found: {from_path}"
                }
                
            to_node = hou.node(to_path)
            if not to_node:
                return {
                    "status": "error",
                    "message": f"Target node not found: {to_path}"
                }
                
            # Connect nodes
            to_node.setInput(input_index, from_node)
            
            return {
                "status": "success",
                "message": f"Connected {from_path} to {to_path} at input {input_index}"
            }
        except hou.OperationFailed as e:
            return {
                "status": "error",
                "message": f"Failed to connect nodes. Error: {str(e)}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error connecting nodes: {str(e)}"
            }
    
    def set_param(self, params):
        """Set a parameter value on a node"""
        node_path = params.get("node_path")
        param_name = params.get("param_name")
        param_value = params.get("param_value")
        
        if not node_path or not param_name or param_value is None:
            return {
                "status": "error",
                "message": "Missing required parameters: node_path, param_name, and param_value"
            }
            
        try:
            # Get node
            node = hou.node(node_path)
            if not node:
                return {
                    "status": "error",
                    "message": f"Node not found: {node_path}"
                }
                
            # Get parameter
            try:
                parm = node.parm(param_name)
                if not parm:
                    # Try to get parmTuple
                    parm_tuple = node.parmTuple(param_name)
                    if not parm_tuple:
                        return {
                            "status": "error",
                            "message": f"Parameter not found: {param_name} on {node_path}"
                        }
                    
                    # Handle vector/tuple parameters
                    if isinstance(param_value, list):
                        if len(param_value) != len(parm_tuple):
                            return {
                                "status": "error",
                                "message": f"Parameter {param_name} expects {len(parm_tuple)} values, got {len(param_value)}"
                            }
                        
                        for i, val in enumerate(param_value):
                            parm_tuple[i].set(val)
                    else:
                        return {
                            "status": "error",
                            "message": f"Parameter {param_name} is a tuple and requires a list of values"
                        }
                else:
                    # Handle simple parameters
                    parm.set(param_value)
                
                return {
                    "status": "success",
                    "message": f"Parameter {param_name} set to {param_value} on {node_path}"
                }
            except hou.OperationFailed as e:
                return {
                    "status": "error",
                    "message": f"Failed to set parameter. Error: {str(e)}"
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error setting parameter: {str(e)}"
            }
    
    # Scene information methods
    def get_scene_info(self):
        """Get information about the current Houdini scene"""
        try:
            hip_file = hou.hipFile.name()
            fps = hou.fps()
            current_frame = hou.frame()
            start_frame = hou.playbar.playbackRange()[0]
            end_frame = hou.playbar.playbackRange()[1]
            
            # Get top-level nodes
            top_nodes = []
            for context in ["obj", "shop", "mat", "vex", "ch"]:
                context_node = hou.node(f"/{context}")
                if context_node:
                    children = [n.name() for n in context_node.children()]
                    top_nodes.append({
                        "context": context,
                        "nodes": children
                    })
            
            return {
                "hip_file": hip_file,
                "fps": fps,
                "current_frame": current_frame,
                "start_frame": start_frame,
                "end_frame": end_frame,
                "top_nodes": top_nodes
            }
        except Exception as e:
            print(f"Error getting scene info: {str(e)}")
            return {"error": str(e)}
    
    def get_object_info(self, object_name):
        """Get detailed information about a specified node"""
        if not object_name:
            return {"error": "No object name specified"}
            
        try:
            node = hou.node(object_name)
            if not node:
                return {"error": f"Node not found: {object_name}"}
                
            # Get basic info
            node_type = node.type().name()
            node_path = node.path()
            
            # Get parent
            parent = node.parent()
            parent_path = parent.path() if parent else None
            
            # Get children
            children = [c.path() for c in node.children()]
            
            # Get parameters
            parameters = {}
            for parm in node.parms():
                try:
                    parameters[parm.name()] = parm.eval()
                except:
                    parameters[parm.name()] = str(parm)
                    
            # Get inputs and outputs
            inputs = []
            for i in range(node.inputs()):
                input_node = node.input(i)
                if input_node:
                    inputs.append({
                        "index": i,
                        "path": input_node.path()
                    })
                    
            outputs = []
            for i, output in enumerate(node.outputs()):
                if output:
                    outputs.append({
                        "index": i,
                        "path": output.path()
                    })
                    
            return {
                "node_type": node_type,
                "node_path": node_path,
                "parent": parent_path,
                "children": children,
                "parameters": parameters,
                "inputs": inputs,
                "outputs": outputs
            }
        except Exception as e:
            print(f"Error getting object info: {str(e)}")
            return {"error": str(e)}
            
    # Simulation methods
    def create_fluid_sim(self, params):
        """Create a FLIP fluid simulation with specified parameters"""
        try:
            # Get parameters
            container_size = params.get("container_size", [10, 10, 10])
            position = params.get("position", [0, 0, 0])
            resolution = params.get("resolution", 128)
            source_type = params.get("source_type", "box")
            source_size = params.get("source_size", [2, 2, 2])
            source_pos = params.get("source_pos", [0, 5, 0])
            viscosity = params.get("viscosity", 1.0)
            collision_objects = params.get("collision_objects", [])
            
            # Create container
            obj = hou.node("/obj")
            geo = obj.createNode("geo", "flip_fluid")
            geo.setPosition(hou.Vector3(position))
            
            # Create a DOP Network for the simulation
            dop = geo.createNode("dopnet", "flip_sim")
            dop.setPosition(hou.Vector2(0, 0))
            
            # Create a FLIP Solver
            flip_solver = dop.createNode("flip", "flip_solver")
            
            # Create FLIP container/solver
            flip_object = dop.createNode("flipobject", "flip_container")
            flip_object.setInput(0, flip_solver)
            
            # Set container size
            size_parm = flip_object.parmTuple("size")
            size_parm.set(container_size)
            
            # Set division size (resolution)
            div_size = container_size[0] / resolution
            flip_object.parm("divsize").set(div_size)
            
            # Create source geometry
            source = None
            if source_type == "box":
                source = geo.createNode("box", "fluid_source")
                source_size_parm = source.parmTuple("size")
                source_size_parm.set(source_size)
            elif source_type == "sphere":
                source = geo.createNode("sphere", "fluid_source")
                source.parm("rad").set(source_size[0] / 2.0)
            else:
                return {
                    "status": "error",
                    "message": f"Unsupported source type: {source_type}"
                }
                
            # Position the source
            source_xform = source.createOutputNode("xform")
            source_xform.parmTuple("t").set(source_pos)
            
            # Create a particle fluid source
            particle_fluid_source = dop.createNode("flipparticlefluid", "source")
            particle_fluid_source.setInput(0, flip_solver)
            
            # Add viscosity if specified
            if viscosity > 0:
                flip_object.parm("viscosity").set(viscosity)
            
            # Add collision objects if specified
            for i, collision in enumerate(collision_objects):
                coll_type = collision.get("type", "sphere")
                coll_size = collision.get("size", [1, 1, 1])
                coll_pos = collision.get("position", [0, 0, 0])
                
                # Create collision object
                coll_obj = None
                if coll_type == "sphere":
                    coll_obj = geo.createNode("sphere", f"collision_{i}")
                    coll_obj.parm("rad").set(coll_size[0] / 2.0)
                elif coll_type == "box":
                    coll_obj = geo.createNode("box", f"collision_{i}")
                    coll_obj.parmTuple("size").set(coll_size)
                else:
                    continue
                    
                # Position the collision object
                coll_xform = coll_obj.createOutputNode("xform")
                coll_xform.parmTuple("t").set(coll_pos)
                
                # Create static object
                static_obj = dop.createNode("staticobject", f"static_collision_{i}")
                static_obj.setInput(0, flip_solver)
            
            # Layout nodes
            dop.layoutChildren()
            geo.layoutChildren()
            
            return {
                "status": "success",
                "message": "FLIP fluid simulation created",
                "container_path": geo.path(),
                "dopnet_path": dop.path(),
            }
        except Exception as e:
            print(f"Error creating fluid sim: {str(e)}")
            traceback.print_exc()
            return {
                "status": "error",
                "message": f"Error creating fluid simulation: {str(e)}"
            }
            
    def create_pyro_sim(self, params):
        """Create a Pyro simulation (fire/smoke) with specified parameters"""
        try:
            # Get parameters
            container_size = params.get("container_size", [10, 10, 10])
            position = params.get("position", [0, 0, 0])
            resolution = params.get("resolution", 100)
            source_type = params.get("source_type", "sphere")
            source_size = params.get("source_size", [2, 2, 2])
            source_pos = params.get("source_pos", [0, 0, 0])
            temperature = params.get("temperature", 1.0)
            fuel = params.get("fuel", 1.0)
            wind_direction = params.get("wind_direction", [0, 0, 0])
            wind_strength = params.get("wind_strength", 0.0)
            
            # Create container
            obj = hou.node("/obj")
            geo = obj.createNode("geo", "pyro_sim")
            geo.setPosition(hou.Vector3(position))
            
            # Create a DOP Network for the simulation
            dop = geo.createNode("dopnet", "pyro_sim")
            dop.setPosition(hou.Vector2(0, 0))
            
            # Create a Pyro Solver
            pyro_solver = dop.createNode("pyrosolver", "pyro_solver")
            
            # Create Pyro container
            smoke_object = dop.createNode("smokeobject", "pyro_container")
            smoke_object.setInput(0, pyro_solver)
            
            # Set container size
            size_parm = smoke_object.parmTuple("size")
            size_parm.set(container_size)
            
            # Set division size (resolution)
            div_size = container_size[0] / resolution
            smoke_object.parm("divsize").set(div_size)
            
            # Create source geometry
            source = None
            if source_type == "box":
                source = geo.createNode("box", "pyro_source")
                source_size_parm = source.parmTuple("size")
                source_size_parm.set(source_size)
            elif source_type == "sphere":
                source = geo.createNode("sphere", "pyro_source")
                source.parm("rad").set(source_size[0] / 2.0)
            else:
                return {
                    "status": "error",
                    "message": f"Unsupported source type: {source_type}"
                }
                
            # Position the source
            source_xform = source.createOutputNode("xform")
            source_xform.parmTuple("t").set(source_pos)
            
            # Create Pyro Source
            pyro_source = dop.createNode("pyrosource", "source")
            pyro_source.setInput(0, pyro_solver)
            
            # Set source parameters
            pyro_source.parm("temperature").set(temperature)
            pyro_source.parm("fuel").set(fuel)
            
            # Add wind if specified
            if wind_strength > 0:
                wind = dop.createNode("gasvelocityfield", "wind")
                wind.setInput(0, pyro_solver)
                wind.parmTuple("direction").set(wind_direction)
                wind.parm("amplitude").set(wind_strength)
            
            # Layout nodes
            dop.layoutChildren()
            geo.layoutChildren()
            
            return {
                "status": "success",
                "message": "Pyro simulation created",
                "container_path": geo.path(),
                "dopnet_path": dop.path(),
            }
        except Exception as e:
            print(f"Error creating pyro sim: {str(e)}")
            traceback.print_exc()
            return {
                "status": "error",
                "message": f"Error creating pyro simulation: {str(e)}"
            }
            
    def run_simulation(self, params):
        """Run a simulation from specified frames"""
        try:
            # Get parameters
            node_path = params.get("node_path")
            start_frame = params.get("start_frame", hou.playbar.playbackRange()[0])
            end_frame = params.get("end_frame", hou.playbar.playbackRange()[1])
            
            if not node_path:
                return {
                    "status": "error",
                    "message": "Missing required parameter: node_path"
                }
                
            # Get node
            node = hou.node(node_path)
            if not node:
                return {
                    "status": "error",
                    "message": f"Node not found: {node_path}"
                }
                
            # Check if node is a dopnet
            if node.type().name() != "dopnet":
                return {
                    "status": "error",
                    "message": f"Node {node_path} is not a dopnet"
                }
                
            # Run simulation
            try:
                node.parm("startframe").set(start_frame)
                node.parm("endframe").set(end_frame)
                node.parm("execute").pressButton()
                
                return {
                    "status": "success",
                    "message": f"Simulation run on {node_path} from frame {start_frame} to {end_frame}"
                }
            except hou.OperationFailed as e:
                return {
                    "status": "error",
                    "message": f"Failed to run simulation: {str(e)}"
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error running simulation: {str(e)}"
            }
            
    # Code execution
    def execute_houdini_code(self, code):
        """Execute arbitrary Python code in Houdini"""
        if not code:
            return {
                "status": "error",
                "message": "No code provided"
            }
            
        try:
            # Create local and global dictionaries
            local_dict = {}
            global_dict = {
                "hou": hou
            }
            
            # Execute the code
            exec(code, global_dict, local_dict)
            
            # Return results if any
            return {
                "status": "success",
                "message": "Code executed successfully",
                "variables": {k: str(v) for k, v in local_dict.items() if not k.startswith("_")}
            }
        except Exception as e:
            traceback.print_exc()
            return {
                "status": "error",
                "message": f"Error executing code: {str(e)}"
            }

# Global server instance
_server_instance = None

def get_server():
    """Get or create the global server instance"""
    global _server_instance
    if not _server_instance:
        _server_instance = HoudiniMCPServer()
    return _server_instance

def show_dialog():
    """Show connection dialog and start server"""
    server = get_server()
    if server.start():
        return server
    else:
        print("Failed to start server")
        return None

def stop_server():
    """Stop the server"""
    global _server_instance
    if _server_instance:
        _server_instance.stop()
        _server_instance = None
        
# Automatically run when this script is loaded
if __name__ == "__main__":
    show_dialog() 