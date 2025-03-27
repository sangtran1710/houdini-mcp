# Houdini-MCP

A bridge between Houdini and Claude AI through the Model Context Protocol (MCP). This project allows you to control Houdini and create simulations using natural language commands from Claude.

## 📖 Project Overview

Houdini-MCP is a Python-based integration that enables seamless communication between Claude AI and SideFX Houdini. Through the Model Context Protocol (MCP), Claude can:

- Create and manipulate Houdini nodes
- Configure parameters and attributes
- Generate complex simulations
- Execute Houdini Python code
- Query scene information

This bridge unlocks the power of natural language control over Houdini's procedural workflow, allowing artists and technical directors to leverage AI assistance in their pipeline.

## 🧱 Features

- **Procedural Houdini Control**: Control Houdini via structured JSON commands
- **Socket Server Integration**: Direct socket connection on port 8095 (configurable)
- **REST API Adapter**: HTTP interface on port 5000 (configurable) 
- **Modular Command Architecture**: Easily extensible command system
- **Custom Simulation Generation**: Create FLIP fluid and Pyro fire/smoke simulations
- **Secure Local-Only REST Interface**: Restricted to localhost for security
- **CLI Launcher**: Multiple startup options via command line interface
- **Python Package Ready**: Structured as a proper Python package with pyproject.toml
- **Type Annotations**: Comprehensive type hints for better code maintainability
- **Unit Tests**: Comprehensive test suite for core functionality

## 🚀 Installation

### Prerequisites

- Python 3.10 or newer
- SideFX Houdini (19.5 or newer recommended)
- Flask (for REST API)

### Installation Methods

#### From Source

```bash
git clone https://github.com/yourname/houdini-mcp.git
cd houdini-mcp
pip install .
```

#### Using pip

```bash
pip install houdini-mcp
```

#### Development Installation

```bash
git clone https://github.com/yourname/houdini-mcp.git
cd houdini-mcp
pip install -e ".[dev]"
```

## ⚙️ Usage

### Starting the Server from Command Line

The MCP server can be started directly from the command line:

```bash
python -m houdini_mcp server --host localhost --port 8095 --log-to-file
```

### Starting the Server from Houdini

Open the Python Shell in Houdini (Alt+P) and run:

```python
import houdini_plugin
houdini_plugin.show_dialog()
```

This will display a connection dialog where you can start the socket server.

### Starting the REST API Proxy

To start the REST API proxy that converts HTTP requests to socket commands:

```bash
python -m houdini_mcp rest --socket-port 8095 --api-port 5000 --log-to-file
```

### Command Line Options

The main script supports various command line options:

```bash
python -m houdini_mcp --help
```

## 🧠 Available Commands

The MCP interface supports the following commands:

- **list_available_commands**: List all available commands
- **create_node**: Create a new node in Houdini
- **connect_nodes**: Connect two nodes together
- **set_param**: Set a parameter value on a node
- **get_scene_info**: Get information about the current Houdini scene
- **get_object_info**: Get detailed information about a specific node
- **create_fluid_sim**: Create a FLIP fluid simulation
- **create_pyro_sim**: Create a Pyro simulation (fire/smoke)
- **run_simulation**: Run a simulation for specified frames
- **execute_houdini_code**: Execute arbitrary Python code in Houdini

For a complete reference of all commands and their parameters, see the `command_schema.json` file or access the `/mcp/schema` endpoint of the REST API.

## 📡 API Examples

### REST API Examples

```bash
# Check if the server is running
curl http://localhost:5000/mcp/status

# Get the full command schema
curl http://localhost:5000/mcp/schema

# Create a new geometry node
curl -X POST http://localhost:5000/mcp/command \
  -H "Content-Type: application/json" \
  -d '{"type": "create_node", "params": {"parent_path": "/obj", "node_type": "geo", "node_name": "my_geometry"}}'

# Create a fluid simulation
curl -X POST http://localhost:5000/mcp/command \
  -H "Content-Type: application/json" \
  -d '{
    "type": "create_fluid_sim",
    "params": {
      "container_size": [10, 10, 10],
      "source_type": "box",
      "source_position": [0, 5, 0],
      "collision_objects": [
        {
          "type": "sphere",
          "position": [0, 0, 0],
          "size": 2.0
        }
      ]
    }
  }'
```

### Socket API Example

```python
import socket
import json

# Connect to the server
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(("localhost", 8095))

# Create a command
command = {
    "type": "create_node",
    "params": {
        "parent_path": "/obj",
        "node_type": "geo",
        "node_name": "my_geometry"
    }
}

# Send the command
client.sendall(json.dumps(command).encode('utf-8'))

# Receive the response
response = b''
while True:
    chunk = client.recv(4096)
    if not chunk:
        break
    response += chunk

# Parse the response
result = json.loads(response.decode('utf-8'))
print(result)

# Close the connection
client.close()
```

## 🔐 Security Notes

- The REST API only accepts connections from localhost (127.0.0.1) to prevent unauthorized access
- The `execute_houdini_code` command should be used with caution as it allows arbitrary code execution
- No authentication is currently implemented; use in a protected environment
- The socket server binds to localhost by default, but can be configured to accept remote connections if needed (not recommended)

## 💡 Development Notes

### Project Structure

```
houdini-mcp/
├── README.md                # This documentation
├── pyproject.toml           # Python package configuration
├── requirements.txt         # Dependencies
├── requirements-dev.txt     # Development dependencies
├── .python-version          # Python version specification
├── main.py                  # CLI entry point
├── houdini_plugin.py        # Houdini plugin interface
├── server.py                # Socket server implementation
├── commands.py              # Command execution logic
├── simulations.py           # Simulation-specific commands
├── rest_to_socket_proxy.py  # REST API proxy
├── command_schema.json      # Command specification
├── tests/                   # Unit tests
└── assets/                  # Additional resources
```

### Adding a New Command

To add a new command to the MCP system:

1. Add the command handler to the `CommandExecutor` class in `commands.py`
2. Update the command handler dictionary in the `__init__` method
3. Add the command schema to `command_schema.json`
4. (Optional) Add unit tests for the new command

Example of a new command implementation:

```python
def my_new_command(self, params):
    """
    Description of what the command does
    
    Args:
        params: Dictionary with command parameters
        
    Returns:
        Dictionary with command results
    """
    try:
        # Implementation here
        return {
            "status": "success",
            "message": "Command executed successfully",
            "result": "Some result data"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error executing command: {str(e)}"
        }
```

### Running Tests

The project includes a comprehensive test suite that can be run with pytest:

```bash
# Run all tests
pytest

# Run tests with coverage report
pytest --cov=.

# Run specific test file
pytest tests/test_rest_api.py
```

## 👥 Credits / License

Developed by [Your Name]

Inspired by [Blender-MCP](https://github.com/gd3kr/BlenderGPT)

Licensed under the MIT License - see the LICENSE file for details.
