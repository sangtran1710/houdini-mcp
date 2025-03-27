"""
Houdini Model Context Protocol (MCP) Bridge

This package provides a bridge between Houdini and Claude AI through the Model Context Protocol.
It allows controlling Houdini and creating simulations using natural language commands.
"""

__version__ = '0.2.0'

# Import key components
from houdini_plugin import show_dialog, start_server, stop_server
from commands import CommandExecutor
from server import HoudiniMCPServer

# Export common functions and classes
__all__ = [
    'show_dialog',
    'start_server',
    'stop_server',
    'CommandExecutor',
    'HoudiniMCPServer'
] 