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

# Metadata cho plugin
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
        except Exception as e:
            print(f"Failed to start server: {str(e)}")
            self.stop()
            
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

        # Scene information commands
        if cmd_type == "get_scene_info":
            return {"status": "success", "result": self.get_scene_info()}
        elif cmd_type == "get_object_info":
            return {"status": "success", "result": self.get_object_info(params.get("object_name"))}
            
        # Object manipulation commands
        elif cmd_type == "create_object":
            result = self.create_object(params)
            return {"status": "success", "result": result}
        elif cmd_type == "modify_object":
            result = self.modify_object(params)
            return {"status": "success", "result": result}
        elif cmd_type == "delete_object":
            result = self.delete_object(params.get("name"))
            return {"status": "success", "result": result}
            
        # Material commands
        elif cmd_type == "set_material":
            result = self.set_material(params)
            return {"status": "success", "result": result}
            
        # Simulation specific commands
        elif cmd_type == "create_fluid_simulation":
            result = self.create_fluid_simulation(params)
            return {"status": "success", "result": result}
        elif cmd_type == "create_pyro_simulation":
            result = self.create_pyro_simulation(params)
            return {"status": "success", "result": result}
        elif cmd_type == "simulate":
            result = self.simulate(params)
            return {"status": "success", "result": result}
            
        # Code execution
        elif cmd_type == "execute_houdini_code":
            result = self.execute_houdini_code(params.get("code", ""))
            return {"status": "success", "result": result}
            
        else:
            return {"status": "error", "message": f"Unknown command type: {cmd_type}"}

    # Scene information methods
    def get_scene_info(self):
        """Get general information about the current Houdini scene"""
        result = {
            "hip_file": hou.hipFile.path(),
            "hip_name": hou.hipFile.basename(),
            "frame_rate": hou.fps(),
            "current_frame": hou.frame(),
            "start_frame": hou.playbar.playbackRange()[0],
            "end_frame": hou.playbar.playbackRange()[1],
            "objects": []
        }
        
        # List top-level objects
        for node in hou.node("/obj").children():
            result["objects"].append({
                "name": node.name(),
                "type": node.type().name(),
                "path": node.path()
            })
        
        return result
    
    def get_object_info(self, object_name):
        """Get detailed information about a specific node"""
        if not object_name:
            return {"error": "No object name provided"}
        
        # Try to find the node
        node = hou.node(object_name)
        if not node:
            # Try with /obj/ prefix if not specified
            if not object_name.startswith("/"):
                node = hou.node(f"/obj/{object_name}")
        
        if not node:
            return {"error": f"Node '{object_name}' not found"}
        
        # Get node information
        result = {
            "name": node.name(),
            "type": node.type().name(),
            "path": node.path(),
            "parent": node.parent().path() if node.parent() else None,
            "children": [child.name() for child in node.children()],
            "parameters": {}
        }
        
        # Add parameter information
        for parm in node.parms():
            result["parameters"][parm.name()] = {
                "value": parm.eval(),
                "type": parm.parmTemplate().type().name()
            }
        
        return result

    # Object manipulation methods
    def create_object(self, params):
        """Create a new object in Houdini"""
        obj_type = params.get("type", "geo")
        name = params.get("name")
        
        if not name:
            name = f"{obj_type}_node"
        
        # Create the node
        parent_path = params.get("parent_path", "/obj")
        parent = hou.node(parent_path)
        if not parent:
            return {"error": f"Parent node '{parent_path}' not found"}
        
        node = parent.createNode(obj_type, name)
        
        # Process additional parameters based on object type
        if obj_type == "geo":
            # For geometry nodes, we can add SOP nodes inside
            sop_type = params.get("sop_type")
            if sop_type:
                sop_name = params.get("sop_name", f"{sop_type}_node")
                sop = node.createNode(sop_type, sop_name)
                
                # Set SOP parameters if provided
                sop_params = params.get("sop_params", {})
                for param_name, param_value in sop_params.items():
                    parm = sop.parm(param_name)
                    if parm:
                        parm.set(param_value)
                
                # Make display node
                sop.setDisplayFlag(True)
                sop.setRenderFlag(True)
        
        # Set node position if specified
        position = params.get("position")
        if position and len(position) == 2:
            node.setPosition([float(position[0]), float(position[1])])
        
        # Set parameters if provided
        node_params = params.get("parameters", {})
        for param_name, param_value in node_params.items():
            parm = node.parm(param_name)
            if parm:
                parm.set(param_value)
        
        return {
            "name": node.name(),
            "path": node.path()
        }
    
    def modify_object(self, params):
        """Modify an existing object in Houdini"""
        node_path = params.get("name")
        if not node_path:
            return {"error": "No node path provided"}
        
        node = hou.node(node_path)
        if not node:
            # Try with /obj/ prefix if not specified
            if not node_path.startswith("/"):
                node = hou.node(f"/obj/{node_path}")
        
        if not node:
            return {"error": f"Node '{node_path}' not found"}
        
        # Update parameters
        node_params = params.get("parameters", {})
        for param_name, param_value in node_params.items():
            parm = node.parm(param_name)
            if parm:
                parm.set(param_value)
        
        # Move node if position specified
        position = params.get("position")
        if position and len(position) == 2:
            node.setPosition([float(position[0]), float(position[1])])
        
        return {
            "name": node.name(),
            "path": node.path()
        }
    
    def delete_object(self, node_path):
        """Delete an object from Houdini"""
        if not node_path:
            return {"error": "No node path provided"}
        
        node = hou.node(node_path)
        if not node:
            # Try with /obj/ prefix if not specified
            if not node_path.startswith("/"):
                node = hou.node(f"/obj/{node_path}")
        
        if not node:
            return {"error": f"Node '{node_path}' not found"}
        
        node.destroy()
        return {"message": f"Node '{node_path}' deleted"}

    # Material methods
    def set_material(self, params):
        """Set material for an object"""
        node_path = params.get("object_name")
        if not node_path:
            return {"error": "No node path provided"}
        
        node = hou.node(node_path)
        if not node:
            # Try with /obj/ prefix if not specified
            if not node_path.startswith("/"):
                node = hou.node(f"/obj/{node_path}")
        
        if not node:
            return {"error": f"Node '{node_path}' not found"}
        
        # Check if we're dealing with a geometry object
        if node.type().name() != "geo":
            return {"error": f"Node '{node_path}' is not a geometry object"}
        
        # Get or create material
        material_name = params.get("material_name", "default_material")
        
        # Check if a material with this name already exists in /mat
        mat_node = hou.node(f"/mat/{material_name}")
        if not mat_node:
            # Create a new material
            mat_context = hou.node("/mat")
            mat_node = mat_context.createNode("principledshader", material_name)
            
            # Set material parameters if provided
            color = params.get("color")
            if color and len(color) >= 3:
                mat_node.parm("basecolorr").set(color[0])
                mat_node.parm("basecolorg").set(color[1])
                mat_node.parm("basecolorb").set(color[2])
                
            # Set other material properties if provided
            roughness = params.get("roughness")
            if roughness is not None:
                mat_node.parm("rough").set(roughness)
                
            metallic = params.get("metallic")
            if metallic is not None:
                mat_node.parm("metallic").set(metallic)
        
        # Assign material to object
        # In Houdini, we typically assign materials at the SOP level or use a material SOP
        # For simplicity, we'll assign it at the object level
        node.parm("shop_materialpath").set(mat_node.path())
        
        return {
            "material_path": mat_node.path(),
            "object_path": node.path()
        }

    # Simulation methods
    def create_fluid_simulation(self, params):
        """Create a FLIP fluid simulation setup"""
        # Create a container for the simulation
        name = params.get("name", "fluid_sim")
        container = hou.node("/obj").createNode("geo", name)
        
        # Create DOP Network for simulation
        dopnet = container.createNode("dopnet", "fluid_dopnet")
        dopnet.setDisplayFlag(True)
        
        # Create FLIP solver inside DOP network
        dopnet.setCurrent(True, True)  # Enter the DOP network
        fluid_object = dopnet.createNode("fluidobject", "fluid_object")
        flip_solver = dopnet.createNode("flipsolver", "flip_solver")
        
        # Create source geometry
        source_type = params.get("source_type", "box")
        source = None
        
        if source_type == "box":
            source = container.createNode("box", "fluid_source")
            # Set box parameters
            size = params.get("source_size", [1, 1, 1])
            source.parm("sizex").set(size[0])
            source.parm("sizey").set(size[1])
            source.parm("sizez").set(size[2])
            
            # Set box position
            position = params.get("source_position", [0, 0, 0])
            source.parm("tx").set(position[0])
            source.parm("ty").set(position[1])
            source.parm("tz").set(position[2])
        elif source_type == "sphere":
            source = container.createNode("sphere", "fluid_source")
            # Set sphere parameters
            radius = params.get("source_radius", 1.0)
            source.parm("rad").set(radius)
            
            # Set sphere position
            position = params.get("source_position", [0, 0, 0])
            source.parm("tx").set(position[0])
            source.parm("ty").set(position[1])
            source.parm("tz").set(position[2])
        
        # Create collision geometry (optional)
        if params.get("create_collision", False):
            collision_type = params.get("collision_type", "box")
            collision = None
            
            if collision_type == "box":
                collision = container.createNode("box", "collision")
                # Set box parameters
                size = params.get("collision_size", [2, 2, 2])
                collision.parm("sizex").set(size[0])
                collision.parm("sizey").set(size[1])
                collision.parm("sizez").set(size[2])
                
                # Set box position
                position = params.get("collision_position", [0, 0, 0])
                collision.parm("tx").set(position[0])
                collision.parm("ty").set(position[1])
                collision.parm("tz").set(position[2])
        
        # Set up source volume
        sourceVolume = container.createNode("volumevizsop", "source_volume")
        if source:
            sourceVolume.setInput(0, source)
            
        # Create a FLIP solver in the container
        flipSolver = container.createNode("flipfluid", "flip_fluid")
        flipSolver.setInput(0, sourceVolume)
        
        # Configure FLIP solver parameters
        resolution = params.get("resolution", 100)
        flipSolver.parm("particlesep").set(1.0 / resolution)
        
        # Configure fluid properties
        viscosity = params.get("viscosity", 0.0)
        flipSolver.parm("viscosity").set(viscosity)
        
        # Set up particle fluid surface
        fluidSurface = container.createNode("fluidparticlesurface", "fluid_surface")
        fluidSurface.setInput(0, flipSolver)
        fluidSurface.setDisplayFlag(True)
        fluidSurface.setRenderFlag(True)
        
        # Layout the network
        container.layoutChildren()
        
        # Set simulation frame range
        start_frame = params.get("start_frame", 1)
        end_frame = params.get("end_frame", 100)
        
        # Return path information
        return {
            "container_path": container.path(),
            "dopnet_path": dopnet.path(),
            "solver_path": flipSolver.path(),
            "surface_path": fluidSurface.path(),
            "message": f"Fluid simulation created at {container.path()}"
        }
    
    def create_pyro_simulation(self, params):
        """Create a Pyro simulation for fire and smoke"""
        # Create a container for the simulation
        name = params.get("name", "pyro_sim")
        container = hou.node("/obj").createNode("geo", name)
        
        # Create DOP Network for simulation
        dopnet = container.createNode("dopnet", "pyro_dopnet")
        dopnet.setDisplayFlag(True)
        
        # Create gas source
        source_type = params.get("source_type", "box")
        source = None
        
        if source_type == "box":
            source = container.createNode("box", "pyro_source")
            # Set box parameters
            size = params.get("source_size", [1, 1, 1])
            source.parm("sizex").set(size[0])
            source.parm("sizey").set(size[1])
            source.parm("sizez").set(size[2])
            
            # Set box position
            position = params.get("source_position", [0, 0, 0])
            source.parm("tx").set(position[0])
            source.parm("ty").set(position[1])
            source.parm("tz").set(position[2])
        elif source_type == "sphere":
            source = container.createNode("sphere", "pyro_source")
            # Set sphere parameters
            radius = params.get("source_radius", 1.0)
            source.parm("rad").set(radius)
            
            # Set sphere position
            position = params.get("source_position", [0, 0, 0])
            source.parm("tx").set(position[0])
            source.parm("ty").set(position[1])
            source.parm("tz").set(position[2])
        
        # Create Pyro solver
        pyroSolver = container.createNode("pyrosolver", "pyro_solver")
        if source:
            pyroSolver.setInput(0, source)
        
        # Set up simulation type
        sim_type = params.get("sim_type", "fire")  # fire, smoke, both
        if sim_type == "fire":
            pyroSolver.parm("enable_smoke").set(0)
            pyroSolver.parm("enable_fire").set(1)
        elif sim_type == "smoke":
            pyroSolver.parm("enable_smoke").set(1)
            pyroSolver.parm("enable_fire").set(0)
        else:  # both
            pyroSolver.parm("enable_smoke").set(1)
            pyroSolver.parm("enable_fire").set(1)
        
        # Configure simulation parameters
        resolution = params.get("resolution", 100)
        pyroSolver.parm("resolutionx").set(resolution)
        pyroSolver.parm("resolutiony").set(resolution)
        pyroSolver.parm("resolutionz").set(resolution)
        
        # Set temperature and fuel for fire
        if sim_type in ["fire", "both"]:
            temperature = params.get("temperature", 1.0)
            pyroSolver.parm("temperature").set(temperature)
            
            fuel_amount = params.get("fuel_amount", 1.0)
            pyroSolver.parm("fuel").set(fuel_amount)
        
        # Set up smoke density for smoke
        if sim_type in ["smoke", "both"]:
            smoke_density = params.get("smoke_density", 1.0)
            pyroSolver.parm("density").set(smoke_density)
        
        # Add forces (optional)
        if params.get("add_forces", False):
            # Add a force like wind or turbulence
            force_type = params.get("force_type", "wind")
            if force_type == "wind":
                gasForce = container.createNode("gasforce", "wind_force")
                direction = params.get("wind_direction", [0, 0, 1])
                strength = params.get("wind_strength", 1.0)
                
                gasForce.parm("forcetype").set(0)  # Wind force
                gasForce.parm("windx").set(direction[0] * strength)
                gasForce.parm("windy").set(direction[1] * strength)
                gasForce.parm("windz").set(direction[2] * strength)
                
                # Connect force to solver
                pyroSolver.setInput(1, gasForce)
        
        # Set up visualization
        pyroVolume = container.createNode("volumevizsop", "pyro_volume")
        pyroVolume.setInput(0, pyroSolver)
        pyroVolume.setDisplayFlag(True)
        pyroVolume.setRenderFlag(True)
        
        # Layout the network
        container.layoutChildren()
        
        # Return path information
        return {
            "container_path": container.path(),
            "dopnet_path": dopnet.path() if dopnet else None,
            "solver_path": pyroSolver.path(),
            "volume_path": pyroVolume.path(),
            "message": f"Pyro simulation created at {container.path()}"
        }
    
    def simulate(self, params):
        """Run a simulation for a specified node path"""
        node_path = params.get("node_path")
        if not node_path:
            return {"error": "No node path provided"}
        
        node = hou.node(node_path)
        if not node:
            return {"error": f"Node '{node_path}' not found"}
        
        # Get frame range to simulate
        start_frame = params.get("start_frame", hou.playbar.playbackRange()[0])
        end_frame = params.get("end_frame", hou.playbar.playbackRange()[1])
        
        # Set current frame to start frame
        hou.setFrame(start_frame)
        
        # Get DOP Network
        dopnet = None
        if node.type().name() == "dopnet":
            dopnet = node
        else:
            # Try to find dopnet inside the node if it's a geo node
            for child in node.children():
                if child.type().name() == "dopnet":
                    dopnet = child
                    break
        
        if not dopnet:
            return {"error": f"Node '{node_path}' is not a DOP Network and does not contain one"}
        
        # Run simulation
        try:
            for frame in range(int(start_frame), int(end_frame) + 1):
                # Print progress
                print(f"Simulating frame {frame}/{end_frame}")
                
                # Simulate one frame
                hou.setFrame(frame)
                
                # Force cook the DOP Network to update the simulation
                dopnet.cook(force=True)
            
            return {
                "message": f"Simulation completed from frame {start_frame} to {end_frame}",
                "start_frame": start_frame,
                "end_frame": end_frame
            }
        except Exception as e:
            return {"error": f"Simulation failed: {str(e)}"}

    # Code execution method
    def execute_houdini_code(self, code):
        """Execute arbitrary Python code in Houdini"""
        if not code:
            return {"error": "No code provided"}
        
        try:
            # Create a local dictionary to capture outputs
            local_dict = {}
            
            # Execute the code
            exec(code, globals(), local_dict)
            
            # Return any variable named 'result' if it exists
            result = local_dict.get("result", {"message": "Code executed successfully"})
            
            return result
        except Exception as e:
            traceback.print_exc()
            return {"error": f"Code execution failed: {str(e)}"}

# Panel class for Houdini UI
class HoudiniMCPPanel:
    def __init__(self):
        self.server = None
        
    def create_interface(self):
        # Create panel UI
        return hou.PaneTabType.PythonPanel
    
    def build_ui(self, parent):
        layout = parent.createVerticalLayout()
        
        # Add server control widgets
        server_layout = layout.createHorizontalLayout()
        
        server_label = server_layout.createLabel("Server:")
        
        host_layout = layout.createHorizontalLayout()
        host_label = host_layout.createLabel("Host:")
        self.host_field = host_layout.createStringField()
        self.host_field.setValue("localhost")
        
        port_layout = layout.createHorizontalLayout()
        port_label = port_layout.createLabel("Port:")
        self.port_field = port_layout.createIntField()
        self.port_field.setValue(9876)
        
        button_layout = layout.createHorizontalLayout()
        self.start_button = button_layout.createButton("Connect to Claude")
        self.stop_button = button_layout.createButton("Disconnect")
        self.stop_button.setEnabled(False)
        
        # Connect button events
        self.start_button.clicked.connect(self.start_server)
        self.stop_button.clicked.connect(self.stop_server)
        
        # Add status label
        status_layout = layout.createHorizontalLayout()
        status_label = status_layout.createLabel("Status:")
        self.status_field = status_layout.createLabel("Not connected")
        
    def start_server(self):
        host = self.host_field.value()
        port = self.port_field.value()
        
        if self.server:
            self.stop_server()
        
        self.server = HoudiniMCPServer(host, port)
        self.server.start()
        
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_field.setText("Connected")
        
    def stop_server(self):
        if self.server:
            self.server.stop()
            self.server = None
            
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_field.setText("Not connected")

# Initialize and create the panel
def create_panel():
    panel = HoudiniMCPPanel()
    return panel

# Function to create and start server from Python Shell
def start_server():
    server = HoudiniMCPServer()
    server.start()
    return server

# Show a dialog to start the server
def show_dialog():
    # Create a dialog
    dialog = hou.ui.createDialog()
    panel = HoudiniMCPPanel()
    panel.build_ui(dialog)
    dialog.show()

# For testing
if __name__ == "__main__":
    show_dialog() 