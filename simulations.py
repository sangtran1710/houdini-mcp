try:
    import hou
except ImportError:
    # Create a dummy version for when running outside Houdini
    class DummyHou:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    hou = DummyHou()

import traceback
import logging
from typing import Dict, Any, List, Optional, Union

logger = logging.getLogger("HoudiniMCP.Simulations")

def create_fluid_simulation(params: Dict[str, Any], logger_instance: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """
    Create a FLIP fluid simulation with the specified parameters
    
    Args:
        params: Dictionary of simulation parameters including:
            - container_size: list of floats [x, y, z] for the container size
            - source_type: string, "box" or "sphere"
            - source_position: list of floats [x, y, z]
            - source_size: list of floats [x, y, z] (for box) or float (for sphere radius)
            - collision_objects: list of collision objects, each with:
                - type: string, "box" or "sphere"
                - position: list of floats [x, y, z]
                - size: list of floats [x, y, z] (for box) or float (for sphere radius)
            - resolution: float, simulation resolution
            - viscosity: float, fluid viscosity
            - surface_tension: float, surface tension
            - frame_range: list of ints [start, end]
        logger_instance: Optional logger instance to use
        
    Returns:
        Dictionary with simulation creation status and node path
    """
    if logger_instance:
        log = logger_instance
    else:
        log = logger
    
    try:
        log.info(f"Creating fluid simulation with params: {params}")
        
        # Extract parameters or use defaults
        container_size = params.get("container_size", [10, 10, 10])
        source_type = params.get("source_type", "box")
        source_position = params.get("source_position", [0, 5, 0])
        source_size = params.get("source_size", [2, 2, 2] if source_type == "box" else 2)
        resolution = params.get("resolution", 100)
        viscosity = params.get("viscosity", 0.01)
        surface_tension = params.get("surface_tension", 0.01)
        frame_range = params.get("frame_range", [1, 100])
        collision_objects = params.get("collision_objects", [])
        
        # Create a geometry node to contain the simulation
        obj_context = hou.node("/obj")
        fluid_container = obj_context.createNode("geo", "fluid_sim")
        
        # Create the container
        dopnet = fluid_container.createNode("dopnet", "fluid_simulation")
        
        # Create FLIP solver
        flip_solver = dopnet.createNode("flipsolver", "flip_solver")
        
        # Create container source
        fluid_source = dopnet.createNode("fluidsource", "fluid_source")
        
        # Configure the solver 
        # - These are common parameters that might need adjustment based on the simulation
        flip_solver.parm("viscosity").set(viscosity)
        flip_solver.parm("surfacetension").set(surface_tension)
        
        # Set up container geometry
        fluid_container.parm("rx").set(container_size[0])
        fluid_container.parm("ry").set(container_size[1])
        fluid_container.parm("rz").set(container_size[2])
        
        # Configure the source based on type
        if source_type == "box":
            # Set up box source
            fluid_source.parm("sourcetype").set(0)  # 0 = box
            fluid_source.parm("sizex").set(source_size[0])
            fluid_source.parm("sizey").set(source_size[1])
            fluid_source.parm("sizez").set(source_size[2])
        else:
            # Set up sphere source
            fluid_source.parm("sourcetype").set(1)  # 1 = sphere
            fluid_source.parm("radius").set(source_size if isinstance(source_size, (int, float)) else source_size[0])
        
        fluid_source.parm("tx").set(source_position[0])
        fluid_source.parm("ty").set(source_position[1])
        fluid_source.parm("tz").set(source_position[2])
        
        # Connect everything
        fluid_source.setInput(0, flip_solver)
        
        # Add collisions if specified
        for i, collision in enumerate(collision_objects):
            coll_type = collision.get("type", "sphere")
            coll_position = collision.get("position", [0, 0, 0])
            coll_size = collision.get("size", [1, 1, 1] if coll_type == "box" else 1)
            
            # Create collision node
            collision_node = dopnet.createNode("staticobject", f"collision_{i}")
            
            if coll_type == "box":
                collision_node.parm("geotype").set(0)  # 0 = box
                collision_node.parm("sizex").set(coll_size[0])
                collision_node.parm("sizey").set(coll_size[1])
                collision_node.parm("sizez").set(coll_size[2])
            else:
                collision_node.parm("geotype").set(2)  # 2 = sphere
                collision_node.parm("radius").set(coll_size if isinstance(coll_size, (int, float)) else coll_size[0])
                
            collision_node.parm("tx").set(coll_position[0])
            collision_node.parm("ty").set(coll_position[1])
            collision_node.parm("tz").set(coll_position[2])
            
            # Connect to solver
            collision_node.setInput(0, flip_solver)
            
        # Set playback range
        hou.playbar.setPlaybackRange(frame_range[0], frame_range[1])
        
        # Layout the nodes
        dopnet.layoutChildren()
        fluid_container.layoutChildren()
        
        # Return success
        return {
            "status": "success",
            "message": "Fluid simulation created successfully",
            "node_path": fluid_container.path()
        }
            
    except Exception as e:
        log.error(f"Error creating fluid simulation: {str(e)}")
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Error creating fluid simulation: {str(e)}"
        }

def create_pyro_simulation(params: Dict[str, Any], logger_instance: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """
    Create a Pyro simulation (fire/smoke) with the specified parameters
    
    Args:
        params: Dictionary of simulation parameters including:
            - source_type: string, "sphere" or "box"
            - source_position: list of floats [x, y, z]
            - source_size: list of floats [x, y, z] (for box) or float (for sphere radius)
            - temperature: float, initial temperature
            - fuel: float, fuel amount
            - burn_rate: float, burn rate
            - expansion: float, expansion factor
            - cooling_rate: float, cooling rate
            - turbulence: float, turbulence amount
            - wind_direction: list of floats [x, y, z], wind direction vector
            - wind_speed: float, wind speed
            - frame_range: list of ints [start, end]
        logger_instance: Optional logger instance to use
        
    Returns:
        Dictionary with simulation creation status and node path
    """
    if logger_instance:
        log = logger_instance
    else:
        log = logger
    
    try:
        log.info(f"Creating pyro simulation with params: {params}")
        
        # Extract parameters or use defaults
        source_type = params.get("source_type", "sphere")
        source_position = params.get("source_position", [0, 0, 0])
        source_size = params.get("source_size", [1, 1, 1] if source_type == "box" else 1)
        temperature = params.get("temperature", 1.0)
        fuel = params.get("fuel", 1.0)
        burn_rate = params.get("burn_rate", 0.75)
        expansion = params.get("expansion", 1.0)
        cooling_rate = params.get("cooling_rate", 0.25)
        turbulence = params.get("turbulence", 0.5)
        wind_direction = params.get("wind_direction", [0, 1, 0])
        wind_speed = params.get("wind_speed", 0.0)
        frame_range = params.get("frame_range", [1, 100])
        
        # Create a geometry node to contain the simulation
        obj_context = hou.node("/obj")
        pyro_container = obj_context.createNode("geo", "pyro_sim")
        
        # Create the pyro setup
        # Use the Pyro FX shelf tool through Python to set up the basic simulation
        pyro_node = pyro_container.createNode("pyrosolver", "pyro_solver")
        
        # Create source
        source_node = pyro_container.createNode("smokeobject", "pyro_source")
        
        # Configure the source based on type
        if source_type == "box":
            source_node.parm("primtype").set(0)  # 0 = box
            source_node.parm("sizex").set(source_size[0])
            source_node.parm("sizey").set(source_size[1])
            source_node.parm("sizez").set(source_size[2])
        else:
            source_node.parm("primtype").set(2)  # 2 = sphere
            source_node.parm("radius").set(source_size if isinstance(source_size, (int, float)) else source_size[0])
            
        source_node.parm("tx").set(source_position[0])
        source_node.parm("ty").set(source_position[1])
        source_node.parm("tz").set(source_position[2])
        
        # Set source parameters
        source_node.parm("temperature").set(temperature)
        source_node.parm("fuel").set(fuel)
        
        # Set solver parameters
        pyro_node.parm("divsize").set(0.1)  # Resolution - smaller is higher resolution
        pyro_node.parm("burningrate").set(burn_rate)
        pyro_node.parm("expansionrate").set(expansion)
        pyro_node.parm("cooling").set(cooling_rate)
        
        # Set turbulence
        turb_node = pyro_container.createNode("gasturb", "turbulence")
        turb_node.parm("amp").set(turbulence)
        
        # Add wind if specified
        if wind_speed > 0:
            wind_node = pyro_container.createNode("gasupres", "wind")
            wind_node.parm("windx").set(wind_direction[0] * wind_speed)
            wind_node.parm("windy").set(wind_direction[1] * wind_speed)
            wind_node.parm("windz").set(wind_direction[2] * wind_speed)
            
        # Connect nodes
        # Basic connection for demonstration - actual connections would depend on complex node graph
        source_node.setInput(0, pyro_node)
        
        # Set playback range
        hou.playbar.setPlaybackRange(frame_range[0], frame_range[1])
        
        # Layout the nodes
        pyro_container.layoutChildren()
        
        # Return success
        return {
            "status": "success",
            "message": "Pyro simulation created successfully",
            "node_path": pyro_container.path()
        }
            
    except Exception as e:
        log.error(f"Error creating pyro simulation: {str(e)}")
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Error creating pyro simulation: {str(e)}"
        }

def run_simulation(params: Dict[str, Any], logger_instance: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """
    Run a simulation for the specified frames
    
    Args:
        params: Dictionary of simulation parameters including:
            - node_path: string, path to the simulation node
            - start_frame: int, start frame
            - end_frame: int, end frame
            - save_to_disk: bool, whether to save the simulation to disk
            - output_path: string, path to save the simulation results (if save_to_disk is True)
        logger_instance: Optional logger instance to use
        
    Returns:
        Dictionary with simulation status information
    """
    if logger_instance:
        log = logger_instance
    else:
        log = logger
    
    try:
        log.info(f"Running simulation with params: {params}")
        
        # Extract parameters
        node_path = params.get("node_path")
        start_frame = params.get("start_frame", 1)
        end_frame = params.get("end_frame", 100)
        save_to_disk = params.get("save_to_disk", False)
        output_path = params.get("output_path", "")
        
        if not node_path:
            return {
                "status": "error",
                "message": "Missing required parameter: node_path"
            }
            
        # Get the simulation node
        node = hou.node(node_path)
        if not node:
            return {
                "status": "error",
                "message": f"Node not found: {node_path}"
            }
            
        # If saving to disk, set up the output path
        if save_to_disk and output_path:
            # Set up a file cache node
            cache_node = None
            
            # Different logic depending on the type of simulation
            if "dopnet" in node.children():
                # FLIP fluid simulation
                dopnet = node.node("dopnet")
                if dopnet:
                    cache_node = node.createNode("filecache", "simulation_cache")
                    # Connect cache node
                    # This is simplified - actual connections would require analysis of the node graph
            elif "pyrosolver" in node.children():
                # Pyro simulation
                pyro_solver = node.node("pyrosolver")
                if pyro_solver:
                    cache_node = node.createNode("filecache", "simulation_cache")
                    # Connect cache node
                    # This is simplified - actual connections would require analysis of the node graph
                    
            if cache_node:
                cache_node.parm("file").set(output_path)
                
        # Set the frame range
        hou.playbar.setPlaybackRange(start_frame, end_frame)
        
        # Run the simulation - this would normally be done through the UI
        # For demonstration, we'll just set the current frame to end_frame
        # In a real implementation, you would use hou.hipFile.saveAndLoad() or similar
        hou.setFrame(end_frame)
        
        return {
            "status": "success",
            "message": f"Simulation set up to run from frame {start_frame} to {end_frame}",
            "note": "To run the simulation, press play in the timeline or use playbar controls"
        }
            
    except Exception as e:
        log.error(f"Error running simulation: {str(e)}")
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Error running simulation: {str(e)}"
        } 