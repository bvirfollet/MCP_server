#!/usr/bin/env python3
"""
Example TCP Client for MCP Server

Demonstrates connecting to MCP server via TCP socket.
Sends JSON-RPC initialize request and receives response.

Usage:
    # Terminal 1: Start MCP server with TCP transport
    python -c "
    import asyncio
    from mcp_server import MCPServer
    server = MCPServer()
    asyncio.run(server.run_with_tcp('localhost', 9000))
    "

    # Terminal 2: Run this client
    python examples/example_tcp_client.py
"""

import asyncio
import json
import socket
import logging
from typing import Optional, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("tcp_client")


class TCPMCPClient:
    """Simple TCP client for MCP Server"""

    def __init__(self, host: str = "localhost", port: int = 9000):
        """Initialize TCP client"""
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.request_id = 0

    async def connect(self) -> None:
        """Connect to TCP server"""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port
            )
            logger.info(f"Connected to {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise

    async def send_request(self, method: str, params: Dict[str, Any] = None) -> None:
        """Send JSON-RPC request"""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self.request_id
        }
        if params:
            request["params"] = params

        try:
            json_data = json.dumps(request).encode('utf-8')
            length = len(json_data).to_bytes(4, byteorder='big')
            self.writer.write(length + json_data)
            await self.writer.drain()
            logger.info(f"Sent: {method}")
        except Exception as e:
            logger.error(f"Send failed: {e}")

    async def receive_response(self) -> Optional[Dict[str, Any]]:
        """Receive JSON-RPC response"""
        try:
            # Read 4-byte length prefix
            length_bytes = await self.reader.readexactly(4)
            length = int.from_bytes(length_bytes, byteorder='big')

            # Read JSON data
            data = await self.reader.readexactly(length)
            response = json.loads(data.decode('utf-8'))

            logger.info(f"Received response: {response.get('method', response.get('result'))}")
            return response
        except asyncio.IncompleteReadError:
            logger.info("Server closed connection")
            return None
        except Exception as e:
            logger.error(f"Receive failed: {e}")
            return None

    async def close(self) -> None:
        """Close connection"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            logger.info("Connection closed")

    async def run(self) -> None:
        """Run example client"""
        await self.connect()

        try:
            # Send initialize request
            logger.info("\n=== MCP TCP Client Demo ===\n")
            await self.send_request("initialize", {
                "protocolVersion": "2024-11",
                "capabilities": {},
                "clientInfo": {
                    "name": "tcp-example-client",
                    "version": "1.0.0"
                }
            })

            # Receive response
            response = await self.receive_response()
            if response:
                logger.info(f"Server protocol version: {response.get('result', {}).get('protocolVersion')}")

            # Send tools/list request
            logger.info("\nListing available tools...")
            await self.send_request("tools/list")
            response = await self.receive_response()
            if response:
                tools = response.get('result', {}).get('tools', [])
                logger.info(f"Found {len(tools)} tools")
                for tool in tools[:3]:  # Show first 3
                    logger.info(f"  - {tool.get('name')}: {tool.get('description')}")

        finally:
            await self.close()


async def main():
    """Main entry point"""
    client = TCPMCPClient()
    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
