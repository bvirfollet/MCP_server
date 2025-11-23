"""
MCP Server Entry Point

Allows running the server directly via `python -m mcp_server`.
Configures logging to stderr (to keep stdout clean for JSON-RPC) and starts the server.
"""

import asyncio
import logging
import sys
from .core.mcp_server import MCPServer
from .transport.stdio_transport import StdioTransport

def setup_logging():
    """Configure logging to stderr"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stderr  # CRITICAL: stdout is for JSON-RPC only
    )

async def main():
    """Main entry point"""
    setup_logging()
    logger = logging.getLogger("main")
    
    try:
        # Create server
        server = MCPServer()
        
        # Configure Stdio transport
        transport = StdioTransport()
        server.set_transport(transport)
        
        # Start server
        logger.info("Starting MCP Server on Stdio...")
        await server.run()
        
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
