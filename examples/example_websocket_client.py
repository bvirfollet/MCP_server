#!/usr/bin/env python3
"""
Example WebSocket Client for MCP Server

Demonstrates connecting to MCP server via WebSocket.
Can be run from browser console or as standalone client.

Usage (Browser):
    Open console and run:
    const ws = new WebSocket('ws://localhost:9001/ws');
    ws.onmessage = (e) => console.log(JSON.parse(e.data));
    ws.send(JSON.stringify({jsonrpc: "2.0", method: "initialize", id: 1}));

Usage (Python):
    # Terminal 1: Start MCP server with WebSocket transport
    python -c "
    import asyncio
    from mcp_server import MCPServer
    server = MCPServer()
    asyncio.run(server.run_with_websocket('localhost', 9001))
    "

    # Terminal 2: Run this client
    python examples/example_websocket_client.py
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("websocket_client")


class WebSocketMCPClient:
    """Simple WebSocket client for MCP Server"""

    def __init__(self, url: str = "ws://localhost:9001/ws"):
        """Initialize WebSocket client"""
        if not HAS_AIOHTTP:
            raise ImportError("aiohttp required for WebSocket client")
        self.url = url
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.request_id = 0

    async def connect(self) -> None:
        """Connect to WebSocket server"""
        try:
            self.session = aiohttp.ClientSession()
            self.ws = await self.session.ws_connect(self.url)
            logger.info(f"Connected to {self.url}")
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
            json_data = json.dumps(request)
            await self.ws.send_str(json_data)
            logger.info(f"Sent: {method}")
        except Exception as e:
            logger.error(f"Send failed: {e}")

    async def receive_response(self) -> Optional[Dict[str, Any]]:
        """Receive JSON-RPC response"""
        try:
            msg = await self.ws.receive()

            if msg.type == aiohttp.WSMsgType.TEXT:
                response = json.loads(msg.data)
                logger.info(f"Received: {response.get('method', response.get('result'))}")
                return response
            elif msg.type == aiohttp.WSMsgType.CLOSE:
                logger.info("Server closed connection")
                return None
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {self.ws.exception()}")
                return None

        except Exception as e:
            logger.error(f"Receive failed: {e}")
            return None

    async def close(self) -> None:
        """Close connection"""
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()
        logger.info("Connection closed")

    async def run(self) -> None:
        """Run example client"""
        await self.connect()

        try:
            # Send initialize request
            logger.info("\n=== MCP WebSocket Client Demo ===\n")
            await self.send_request("initialize", {
                "protocolVersion": "2024-11",
                "capabilities": {},
                "clientInfo": {
                    "name": "websocket-example-client",
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
    client = WebSocketMCPClient()
    await client.run()


if __name__ == "__main__":
    if not HAS_AIOHTTP:
        print("Error: aiohttp not installed. Install with: pip install aiohttp")
        exit(1)
    asyncio.run(main())
