import argparse
import logging
import sys
import os
from typing import Optional
from houdini_plugin import show_dialog, start_server, stop_server

# Configure logging
def setup_logging(log_to_file: bool = False, log_level: str = "INFO", log_dir: Optional[str] = None) -> None:
    """
    Set up logging configuration
    
    Args:
        log_to_file: Whether to log to a file
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
        
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Add file handler if requested
    if log_to_file:
        # Create logs directory if it doesn't exist
        log_directory = log_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_directory, exist_ok=True)
        
        # Create log file path
        log_file = os.path.join(log_directory, "houdini_mcp.log")
        
        # Add file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        print(f"Logging to file: {log_file}")

# Get logger for this module
logger = logging.getLogger("HoudiniMCP.Main")

def main() -> int:
    """
    Main entry point for the Houdini-MCP package.
    This function handles command line arguments and starts the MCP server.
    
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = argparse.ArgumentParser(description="Houdini Model Context Protocol (MCP) Server")
    
    # Add global options
    parser.add_argument("--log-to-file", action="store_true", help="Log to file")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], 
                        help="Logging level")
    parser.add_argument("--log-dir", help="Directory to store log files")
    
    # Add subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Server command
    server_parser = subparsers.add_parser("server", help="Start the MCP server")
    server_parser.add_argument("--host", default="localhost", help="Host to bind to")
    server_parser.add_argument("--port", type=int, default=8095, help="Port to bind to")
    
    # REST proxy command
    rest_parser = subparsers.add_parser("rest", help="Start the REST API proxy")
    rest_parser.add_argument("--socket-port", type=int, default=8095, help="Socket server port")
    rest_parser.add_argument("--api-port", type=int, default=5000, help="REST API port")
    
    # GUI command (for showing the dialog in Houdini)
    gui_parser = subparsers.add_parser("gui", help="Show the MCP dialog in Houdini")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.log_to_file, args.log_level, args.log_dir)
    
    # Handle command
    if args.command == "server":
        # Start the server directly
        logger.info(f"Starting MCP server on {args.host}:{args.port}")
        success = start_server(args.host, args.port)
        
        if success:
            logger.info("Server started successfully")
            logger.info("Press Ctrl+C to stop the server")
            
            # Keep the script running
            try:
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Stopping server...")
                stop_server()
                logger.info("Server stopped")
        else:
            logger.error("Failed to start server")
            return 1
            
    elif args.command == "rest":
        # Start the REST proxy
        logger.info("Starting REST API proxy")
        logger.info(f"Socket server port: {args.socket_port}")
        logger.info(f"REST API port: {args.api_port}")
        
        # Update REST proxy config and import to avoid circular imports
        from rest_to_socket_proxy import main as rest_main
        import rest_to_socket_proxy
        
        # Set global variables
        rest_to_socket_proxy.DEFAULT_PORT = args.socket_port
        rest_to_socket_proxy.DEFAULT_API_PORT = args.api_port
        
        # Start REST proxy
        rest_main()
        
    elif args.command == "gui":
        # Show the dialog in Houdini
        logger.info("Showing MCP dialog in Houdini")
        show_dialog()
        
    else:
        # No command specified, show help
        parser.print_help()
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
