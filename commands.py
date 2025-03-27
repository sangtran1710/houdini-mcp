try:
    import hou
except ImportError:
    # Create a dummy version for when running outside Houdini
    class DummyHou:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    hou = DummyHou()

import json
import traceback
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("HoudiniMCP.Commands")

class CommandExecutor:
    def __init__(self):
        self.logger = logger
        # Initialize command handlers
        self.command_handlers = {
            "list_available_commands": self.list_available_commands,
            "create_node": self.create_node,
            "connect_nodes": self.connect_nodes,
            "set_param": self.set_param,
            "get_scene_info": self.get_scene_info,
            "get_object_info": self.get_object_info,
            "create_fluid_sim": self.create_fluid_sim,
            "create_pyro_sim": self.create_pyro_sim,
            "run_simulation": self.run_simulation,
            "execute_houdini_code": self.execute_houdini_code
        }
    
    def log(self, level: str, message: str) -> None:
        """
        Log a message with the specified level
        
        Args:
            level: Log level (info, error, debug, warning)
            message: Message to log
        """
        if level == "info":
            self.logger.info(message)
            print(message)
        elif level == "error":
            self.logger.error(message)
            print(message)
        elif level == "debug":
            self.logger.debug(message)
        elif level == "warning":
            self.logger.warning(message)
            print(message)
        else:
            print(message)
    
    def execute_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a command using the appropriate handler
        
        Args:
            command: Command dictionary with 'type' and optional 'params'
        
        Returns:
            Dictionary with command execution results
        """
        try:
            # Log the command being executed
            self.log("info", f"Executing command: {command.get('type')} with params: {command.get('params', {})}")
            
            # Get command type and params
            cmd_type = command.get("type")
            params = command.get("params", {})
            
            # Check if we have a handler for this command
            if cmd_type in self.command_handlers:
                response = self.command_handlers[cmd_type](params)
            else:
                return {"status": "error", "message": f"Unknown command type: {cmd_type}"}
            
            # Log the raw response
            self.log("info", f"Raw response: {response}")
            
            # Ensure consistent response format
            if not isinstance(response, dict):
                self.log("warning", f"Response is not a dictionary: {response}")
                return {"status": "error", "message": f"Invalid response format: {str(response)}"}
            
            # Make sure we have a status field
            if "status" not in response:
                self.log("warning", f"Response missing status field: {response}")
                if "error" in response:
                    return {"status": "error", "message": response["error"]}
                else:
                    # Default to success if no error found
                    response["status"] = "success"
                    if "message" not in response:
                        response["message"] = "Command executed successfully"
            
            # One final check to ensure we have a message
            if "message" not in response:
                self.log("warning", f"Response missing message field: {response}")
                if response["status"] == "error":
                    response["message"] = "An unknown error occurred"
                else:
                    response["message"] = "Command executed successfully"
            
            # Make sure the response is serializable to JSON
            try:
                json.dumps(response)
            except (TypeError, ValueError) as e:
                self.log("warning", f"Response is not JSON serializable: {response}, Error: {str(e)}")
                return {
                    "status": "error", 
                    "message": f"Server generated a non-serializable response: {str(e)}"
                }
            
            self.log("info", f"Final validated response: {response}")
            return response
        except Exception as e:
            self.log("error", f"ERROR in execute_command: {str(e)}")
            traceback.print_exc()
            return {"status": "error", "message": str(e)}
    
    # Command handlers
    def list_available_commands(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        List all available commands
        
        Args:
            params: Command parameters (not used for this command)
            
        Returns:
            Dictionary with list of available commands
        """
        return {
            "status": "success",
            "commands": list(self.command_handlers.keys())
        }
    
    def create_node(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a node of specified type under a parent
        
        Args:
            params: Command parameters including:
                - parent_path: Path to parent node (default: "/obj")
                - node_type: Type of node to create
                - node_name: Optional name for the new node
                
        Returns:
            Dictionary with creation status and node path
        """
        self.log("info", f"Creating node with params: {params}")
        parent_path = params.get("parent_path", "/obj")
        node_type = params.get("node_type")
        node_name = params.get("node_name", None)
        
        if not node_type:
            self.log("error", "ERROR: Missing required parameter: node_type")
            return {
                "status": "error", 
                "message": "Missing required parameter: node_type"
            }
            
        try:
            # Get parent node
            try:
                parent = hou.node(parent_path)
                if not parent:
                    self.log("error", f"ERROR: Parent node not found: {parent_path}")
                    return {
                        "status": "error",
                        "message": f"Parent node not found: {parent_path}"
                    }
            except hou.OperationFailed as e:
                self.log("error", f"ERROR: Invalid parent path: {parent_path}. Error: {str(e)}")
                return {
                    "status": "error",
                    "message": f"Invalid parent path: {parent_path}. Error: {str(e)}"
                }
                
            # Create the node
            try:
                node = parent.createNode(node_type, node_name)
                node_path = node.path()
                
                self.log("info", f"SUCCESS: Node created: {node_path}")
                return {
                    "status": "success",
                    "message": f"Node created: {node_path}",
                    "node_path": node_path
                }
            except hou.OperationFailed as e:
                self.log("error", f"ERROR: Failed to create node of type {node_type}. Error: {str(e)}")
                return {
                    "status": "error",
                    "message": f"Failed to create node of type {node_type}. Error: {str(e)}"
                }
                
        except Exception as e:
            self.log("error", f"ERROR: Unexpected error creating node: {str(e)}")
            traceback.print_exc()
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
    
    def get_scene_info(self, params):
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
            self.log("error", f"Error getting scene info: {str(e)}")
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
            self.log("error", f"Error getting object info: {str(e)}")
            return {"error": str(e)}
            
    # Simulation methods will be imported from simulations.py
    def create_fluid_sim(self, params):
        """Create a FLIP fluid simulation with specified parameters"""
        from simulations import create_fluid_simulation
        return create_fluid_simulation(params, self.logger)
    
    def create_pyro_sim(self, params):
        """Create a Pyro simulation (fire/smoke) with specified parameters"""
        from simulations import create_pyro_simulation
        return create_pyro_simulation(params, self.logger)
    
    def run_simulation(self, params):
        """Run a simulation from specified frames"""
        from simulations import run_simulation
        return run_simulation(params, self.logger)
    
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