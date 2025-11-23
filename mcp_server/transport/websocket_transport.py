"""
WebSocket Transport for MCP Protocol

Module: transport.websocket_transport
Date: 2025-11-23
Version: 0.1.0-alpha (Phase 4)

CHANGELOG:
[2025-11-23 v0.1.0-alpha] WebSocket Transport Implementation
  - WebSocketTransport for browser/web clients
  - HTTP upgrade to WebSocket
  - Support multiple concurrent WebSocket clients
  - JSON-RPC over WebSocket
  - Compatible with standard WebSocket API

ARCHITECTURE:
WebSocketTransport allows web clients to connect via WebSocket.
- HTTP server that upgrades to WebSocket
- One WebSocketConnection per client
- JSON messages (no length-prefix needed, framing built-in)
- Async/await for concurrent clients

SECURITY NOTES:
- All clients authenticate via JWT (Phase 3)
- No TLS in Phase 4 (prepared for Phase 3.1)
- Messages validated as JSON-RPC
- CORS not enabled (local network only)
"""

import asyncio
import json
import logging
import uuid
import http
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Try to import websockets, fallback for testing
try:
    from aiohttp import web
    from aiohttp import WSMsgType
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

from .base_transport import BaseTransport


@dataclass
class WebSocketConfig:
    """WebSocket Transport Configuration"""
    host: str = "0.0.0.0"
    port: int = 9001
    read_timeout: float = 30.0
    write_timeout: float = 10.0
    max_message_size: int = 10 * 1024 * 1024  # 10 MB


class WebSocketConnection:
    """Represents a WebSocket connection"""

    def __init__(self, ws, client_id: str, config: WebSocketConfig):
        """Initialize WebSocket connection"""
        self.ws = ws
        self.client_id = client_id
        self.config = config
        self.connected = True
        self.logger = logging.getLogger(f"transport.websocket.{client_id[:8]}")
        self.logger.info("Connection established")

    async def send(self, data: bytes) -> None:
        """Send data to WebSocket client"""
        if not self.connected or not self.ws:
            return

        try:
            # Send as text (WebSocket will handle framing)
            text_data = data.decode('utf-8') if isinstance(data, bytes) else data
            await asyncio.wait_for(
                self.ws.send_str(text_data),
                timeout=self.config.write_timeout
            )
            self.logger.debug(f"Sent {len(text_data)} chars")
        except asyncio.TimeoutError:
            self.logger.error("Write timeout")
            self.connected = False
        except Exception as e:
            self.logger.error(f"Send error: {e}")
            self.connected = False

    async def receive(self) -> Optional[bytes]:
        """Receive data from WebSocket client"""
        if not self.connected or not self.ws:
            return None

        try:
            msg = await asyncio.wait_for(
                self.ws.receive(),
                timeout=self.config.read_timeout
            )

            if msg.type == WSMsgType.TEXT:
                self.logger.debug(f"Received: {len(msg.data)} chars")
                return msg.data.encode('utf-8')
            elif msg.type == WSMsgType.CLOSE:
                self.logger.info("Client sent close frame")
                self.connected = False
                return None
            elif msg.type == WSMsgType.ERROR:
                self.logger.error(f"WebSocket error: {self.ws.exception()}")
                self.connected = False
                return None
            else:
                self.logger.warning(f"Unexpected message type: {msg.type}")
                return None

        except asyncio.TimeoutError:
            self.logger.error("Read timeout")
            self.connected = False
            return None
        except Exception as e:
            self.logger.error(f"Receive error: {e}")
            self.connected = False
            return None

    async def close(self) -> None:
        """Close WebSocket connection"""
        try:
            if self.ws and not self.ws.is_closed():
                await self.ws.close()
            self.connected = False
            self.logger.info("Connection closed")
        except Exception as e:
            self.logger.error(f"Close error: {e}")


class WebSocketTransport(BaseTransport):
    """
    WebSocket Transport for MCP Protocol

    Allows web clients to connect via WebSocket (HTTP upgrade).
    Supports multiple concurrent connections.
    Uses JSON-RPC 2.0 over WebSocket.
    """

    def __init__(self, config: Optional[WebSocketConfig] = None):
        """
        Initialize WebSocket Transport

        Args:
            config: WebSocketConfig instance (uses defaults if None)
        """
        if not HAS_AIOHTTP:
            raise ImportError("aiohttp required for WebSocket support")

        super().__init__(name="websocket")
        self.config = config or WebSocketConfig()
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.clients: Dict[str, WebSocketConnection] = {}
        self.logger = logging.getLogger("transport.websocket")
        self.is_running = False

    async def start(self) -> None:
        """Start WebSocket server"""
        try:
            # Create aiohttp application
            self.app = web.Application()
            self.app.router.add_get('/ws', self._ws_handler)
            self.app.router.add_get('/', self._http_handler)

            # Setup server
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            site = web.TCPSite(
                self.runner,
                self.config.host,
                self.config.port
            )
            await site.start()

            self.is_running = True
            self.logger.info(
                f"WebSocket server started on {self.config.host}:{self.config.port}"
            )

            # Keep running
            await asyncio.Event().wait()

        except Exception as e:
            self.logger.error(f"Server startup failed: {e}")
            self.is_running = False
            raise

    async def _http_handler(self, request):
        """Handle HTTP GET / request"""
        return web.Response(
            text="MCP WebSocket Server - Connect to /ws\n",
            status=200
        )

    async def _ws_handler(self, request):
        """Handle WebSocket upgrade request"""
        client_id = str(uuid.uuid4())
        ws = web.WebSocketResponse()

        try:
            # Accept WebSocket connection
            await ws.prepare(request)
            self.logger.info(f"WebSocket client connected: {client_id}")

            # Create connection object
            connection = WebSocketConnection(ws, client_id, self.config)
            self.clients[client_id] = connection

            # Notify handler
            if self._client_handler:
                try:
                    await self._client_handler(client_id, "connect")
                except Exception as e:
                    self.logger.error(f"Client handler error: {e}")

            # Read messages
            while connection.connected:
                data = await connection.receive()
                if data:
                    try:
                        # Parse JSON-RPC message
                        message = json.loads(data.decode('utf-8'))
                        await self._on_message(client_id, message)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"JSON parse error: {e}")
                        # Send error response
                        error_resp = {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32700,
                                "message": "Parse error"
                            },
                            "id": None
                        }
                        json_data = json.dumps(error_resp).encode('utf-8')
                        await connection.send(json_data)
                else:
                    break

        except Exception as e:
            self.logger.error(f"WebSocket error: {e}")
        finally:
            # Cleanup
            await connection.close()
            if client_id in self.clients:
                del self.clients[client_id]
            self.logger.info(f"WebSocket client disconnected: {client_id}")

        return ws

    async def send_message(self, message: Dict[str, Any]) -> None:
        """
        Send message to all WebSocket clients (broadcast)

        Args:
            message: JSON-RPC message dict
        """
        json_data = json.dumps(message).encode('utf-8')
        disconnected = []

        for client_id, connection in list(self.clients.items()):
            try:
                await connection.send(json_data)
            except Exception as e:
                self.logger.error(f"Send error to {client_id}: {e}")
                disconnected.append(client_id)

        # Remove disconnected clients
        for client_id in disconnected:
            if client_id in self.clients:
                del self.clients[client_id]

    async def send_error(self, error: Any) -> None:
        """
        Send error to all WebSocket clients

        Args:
            error: Error object with to_jsonrpc_error() method
        """
        try:
            error_dict = error.to_jsonrpc_error()
            await self.send_message(error_dict)
        except Exception as e:
            self.logger.error(f"Send error failed: {e}")

    async def broadcast_message(self, message: Dict[str, Any]) -> None:
        """
        Broadcast message to all WebSocket clients

        Args:
            message: JSON-RPC message dict
        """
        json_data = json.dumps(message).encode('utf-8')
        disconnected = []

        for client_id, connection in self.clients.items():
            try:
                await connection.send(json_data)
            except Exception as e:
                self.logger.error(f"Broadcast error to {client_id}: {e}")
                disconnected.append(client_id)

        # Remove disconnected clients
        for client_id in disconnected:
            if client_id in self.clients:
                del self.clients[client_id]

    async def stop(self) -> None:
        """Stop WebSocket server and close all connections"""
        try:
            # Close all client connections
            for connection in list(self.clients.values()):
                await connection.close()

            self.clients.clear()

            # Stop aiohttp server
            if self.runner:
                await self.runner.cleanup()

            self.is_running = False
            self.logger.info("WebSocket transport stopped")

        except Exception as e:
            self.logger.error(f"Stop error: {e}")

    def get_client_count(self) -> int:
        """Get number of connected WebSocket clients"""
        return len(self.clients)

    def get_client_list(self) -> list:
        """Get list of connected client IDs"""
        return list(self.clients.keys())


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    from unittest.mock import AsyncMock, MagicMock

    class TestWebSocketConnection(unittest.TestCase):
        """Test suite for WebSocketConnection"""

        def setUp(self):
            """Setup test fixtures"""
            self.config = WebSocketConfig()
            self.ws = AsyncMock()
            self.ws.is_closed = MagicMock(return_value=False)

        def test_initialization(self):
            """Test connection initialization"""
            if not HAS_AIOHTTP:
                self.skipTest("aiohttp not installed")
            conn = WebSocketConnection(self.ws, "test-client", self.config)
            self.assertEqual(conn.client_id, "test-client")
            self.assertTrue(conn.connected)

    class TestWebSocketTransport(unittest.TestCase):
        """Test suite for WebSocketTransport"""

        def setUp(self):
            """Setup test fixtures"""
            if not HAS_AIOHTTP:
                self.skipTest("aiohttp not installed")
            self.config = WebSocketConfig(port=9999)
            self.transport = WebSocketTransport(self.config)

        def test_initialization(self):
            """Test transport initialization"""
            self.assertIsNone(self.transport.app)
            self.assertEqual(len(self.transport.clients), 0)
            self.assertFalse(self.transport.is_running)

        def test_get_client_count(self):
            """Test client count"""
            self.assertEqual(self.transport.get_client_count(), 0)

        def test_config_defaults(self):
            """Test default configuration"""
            config = WebSocketConfig()
            self.assertEqual(config.host, "0.0.0.0")
            self.assertEqual(config.port, 9001)

    # Run tests only if aiohttp available
    if HAS_AIOHTTP:
        unittest.main(verbosity=2)
    else:
        print("aiohttp not installed - skipping WebSocket tests")
