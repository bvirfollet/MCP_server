# Phase 4 Architecture - Network Transports (TCP/HTTP+WebSocket)

## 🏗️ High-Level Architecture

### Transport Layer (Extended from Phase 1)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            MCPServer                                     │
│  (Unified server managing multiple transports simultaneously)            │
└────────────────┬────────────────┬────────────────┬──────────────────────┘
                 │                │                │
        ┌────────▼────────┐       │                │
        │   Stdio Handler │       │                │
        │   (Phase 1)     │       │                │
        └─────────────────┘       │                │
                           ┌──────▼──────┐  ┌─────▼──────────┐
                           │ TCP Handler │  │WebSocket       │
                           │ (Phase 4)   │  │Handler         │
                           │             │  │(Phase 4)       │
                           └──────┬──────┘  └─────┬──────────┘
                                  │              │
                           ┌──────▼──────┐       │
                           │ TCP Server  │       │
                           │ Port 9000   │       │
                           └─────────────┘       │
                                          ┌──────▼──────────┐
                                          │HTTP+WebSocket   │
                                          │Server           │
                                          │Port 9001        │
                                          └─────────────────┘
```

### Message Flow (Phase 4)

```
TCP Client                  MCP Server                  Execution Engine
     │                           │                             │
     ├─ JSON-RPC (TCP) ────────>│                             │
     │                           ├─ Parse JSON-RPC           │
     │                           ├─ Validate JWT (Phase 3)   │
     │                           ├─ Route to Protocol        │
     │                           ├─ Call Handler             │
     │                           ├────────────────────────>  │
     │                           │                  execute  │
     │<──── JSON-RPC Response ───┤<─────────────────────────┤
     │     (over TCP)            │
```

## 📦 Component Specifications

### 1. TCPTransport Implementation

**File**: `mcp_server/transport/tcp_transport.py`

```python
from typing import Optional, Dict, Any
import asyncio
import json
import logging
from .base_transport import BaseTransport, ClientConnection, TransportMessage

class TCPClientConnection:
    """Represents a single TCP client connection"""

    def __init__(self, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter,
                 client_id: str):
        self.reader = reader
        self.writer = writer
        self.client_id = client_id
        self.connected = True

    async def send(self, message: TransportMessage) -> None:
        """Send message to TCP client"""
        json_data = json.dumps(message.to_dict())
        # Add length prefix for stream safety: [len:4bytes][data]
        data = json_data.encode('utf-8')
        length = len(data).to_bytes(4, 'big')
        self.writer.write(length + data)
        await self.writer.drain()

    async def receive(self) -> Optional[Dict[str, Any]]:
        """Receive message from TCP client"""
        try:
            # Read 4-byte length prefix
            length_bytes = await self.reader.readexactly(4)
            length = int.from_bytes(length_bytes, 'big')

            # Read JSON data
            data = await self.reader.readexactly(length)
            return json.loads(data.decode('utf-8'))
        except asyncio.IncompleteReadError:
            self.connected = False
            return None

    async def close(self) -> None:
        """Close TCP connection"""
        self.writer.close()
        await self.writer.wait_closed()
        self.connected = False


class TCPTransport(BaseTransport):
    """TCP Socket Transport for MCP Protocol"""

    def __init__(self):
        super().__init__()
        self.server: Optional[asyncio.Server] = None
        self.clients: Dict[str, TCPClientConnection] = {}
        self.logger = logging.getLogger("transport.tcp")

    async def start(self, host: str = "0.0.0.0", port: int = 9000) -> None:
        """Start TCP server"""
        self.server = await asyncio.start_server(
            self._handle_client, host, port
        )
        self.logger.info(f"TCP server listening on {host}:{port}")

        async with self.server:
            await self.server.serve_forever()

    async def _handle_client(self,
                            reader: asyncio.StreamReader,
                            writer: asyncio.StreamWriter) -> None:
        """Handle individual client connection"""
        client_id = self._generate_client_id()
        addr = writer.get_extra_info('peername')
        self.logger.info(f"TCP client connected: {client_id} from {addr}")

        connection = TCPClientConnection(reader, writer, client_id)
        self.clients[client_id] = connection

        # Register with parent handler
        if self._client_handler:
            await self._client_handler(client_id)

        # Listen for messages
        try:
            while connection.connected:
                msg = await connection.receive()
                if msg:
                    await self._on_message(client_id, msg)
                else:
                    break
        except Exception as e:
            self.logger.error(f"Error handling client {client_id}: {e}")
        finally:
            await connection.close()
            del self.clients[client_id]
            self.logger.info(f"TCP client disconnected: {client_id}")

    async def send_message(self, client_id: str,
                          message: TransportMessage) -> None:
        """Send message to specific client"""
        if client_id in self.clients:
            await self.clients[client_id].send(message)

    async def broadcast_message(self, message: TransportMessage) -> None:
        """Send message to all clients"""
        for connection in self.clients.values():
            await connection.send(message)

    async def stop(self) -> None:
        """Stop TCP server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Close all client connections
        for connection in self.clients.values():
            await connection.close()

        self.logger.info("TCP transport stopped")
```

**Tests** (15 tests):
- `test_tcp_server_startup` - Server starts on port 9000
- `test_tcp_client_connection` - Client can connect
- `test_tcp_client_disconnect` - Client disconnect handled
- `test_send_message_to_client` - Server sends message to client
- `test_receive_message_from_client` - Server receives message from client
- `test_multiple_tcp_clients` - Multiple clients connect simultaneously
- `test_json_rpc_request_response` - Complete request/response cycle
- `test_message_length_prefix` - Length-prefixed messages work
- `test_malformed_json_handling` - Invalid JSON handled gracefully
- `test_client_reconnection` - Client can reconnect after disconnect
- `test_concurrent_messages` - Multiple messages processed concurrently
- `test_large_message_handling` - Large JSON messages work
- `test_server_shutdown` - Server shutdown closes all connections
- `test_client_timeout` - Idle clients timeout (optional)
- `test_network_error_handling` - Network errors handled gracefully

### 2. WebSocketTransport Implementation

**File**: `mcp_server/transport/websocket_transport.py`

```python
from typing import Optional, Dict, Any
import asyncio
import json
import logging
import websockets
from websockets.server import WebSocketServerProtocol
from .base_transport import BaseTransport, TransportMessage

class WebSocketConnection:
    """Represents a WebSocket connection"""

    def __init__(self, websocket: WebSocketServerProtocol, client_id: str):
        self.websocket = websocket
        self.client_id = client_id
        self.connected = True

    async def send(self, message: TransportMessage) -> None:
        """Send message over WebSocket"""
        await self.websocket.send(json.dumps(message.to_dict()))

    async def receive(self) -> Optional[Dict[str, Any]]:
        """Receive message over WebSocket"""
        try:
            data = await self.websocket.recv()
            return json.loads(data)
        except websockets.exceptions.ConnectionClosed:
            self.connected = False
            return None

    async def close(self) -> None:
        """Close WebSocket connection"""
        await self.websocket.close()
        self.connected = False


class WebSocketTransport(BaseTransport):
    """WebSocket Transport for MCP Protocol (HTTP+WS)"""

    def __init__(self):
        super().__init__()
        self.server: Optional[asyncio.Server] = None
        self.clients: Dict[str, WebSocketConnection] = {}
        self.logger = logging.getLogger("transport.websocket")

    async def start(self, host: str = "0.0.0.0", port: int = 9001) -> None:
        """Start WebSocket server"""
        async def ws_handler(websocket, path):
            await self._handle_client(websocket)

        self.server = await websockets.serve(
            ws_handler, host, port
        )
        self.logger.info(f"WebSocket server listening on ws://{host}:{port}")

        # Keep server running
        await asyncio.Future()  # run forever

    async def _handle_client(self, websocket: WebSocketServerProtocol) -> None:
        """Handle WebSocket client"""
        client_id = self._generate_client_id()
        addr = websocket.remote_address
        self.logger.info(f"WebSocket client connected: {client_id} from {addr}")

        connection = WebSocketConnection(websocket, client_id)
        self.clients[client_id] = connection

        # Register with handler
        if self._client_handler:
            await self._client_handler(client_id)

        # Listen for messages
        try:
            while connection.connected:
                msg = await connection.receive()
                if msg:
                    await self._on_message(client_id, msg)
                else:
                    break
        except Exception as e:
            self.logger.error(f"Error handling WebSocket {client_id}: {e}")
        finally:
            await connection.close()
            del self.clients[client_id]
            self.logger.info(f"WebSocket client disconnected: {client_id}")

    async def send_message(self, client_id: str,
                          message: TransportMessage) -> None:
        """Send message to specific WebSocket client"""
        if client_id in self.clients:
            await self.clients[client_id].send(message)

    async def broadcast_message(self, message: TransportMessage) -> None:
        """Broadcast message to all WebSocket clients"""
        for connection in self.clients.values():
            await connection.send(message)

    async def stop(self) -> None:
        """Stop WebSocket server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Close all connections
        for connection in self.clients.values():
            await connection.close()

        self.logger.info("WebSocket transport stopped")
```

**Tests** (12 tests):
- `test_websocket_server_startup` - Server starts on port 9001
- `test_websocket_client_connection` - Browser can connect via WebSocket
- `test_websocket_client_disconnect` - Client disconnect handled
- `test_send_message_to_websocket` - Server sends message to WebSocket client
- `test_receive_message_from_websocket` - Server receives from WebSocket
- `test_multiple_websocket_clients` - Multiple WebSocket clients work
- `test_json_rpc_websocket` - Complete JSON-RPC cycle over WebSocket
- `test_websocket_broadcast` - Broadcast to multiple clients
- `test_websocket_malformed_json` - Invalid JSON handled
- `test_websocket_binary_rejection` - Binary messages rejected
- `test_websocket_server_shutdown` - Clean shutdown
- `test_browser_compatibility` - Works with standard WebSocket API

### 3. Multi-Transport MCPServer

**File**: `mcp_server/core/mcp_server.py` (modifications)

```python
class MCPServer:
    """MCP Server with multi-transport support"""

    def __init__(self, ...):
        # ... existing Phase 1-3 initialization ...
        self.transports: Dict[str, BaseTransport] = {}
        self.client_transport_map: Dict[str, str] = {}

    async def run_with_tcp(self, host: str = "0.0.0.0",
                          port: int = 9000) -> None:
        """Run server with TCP transport only"""
        transport = TCPTransport()
        transport.register_message_handler(self._handle_transport_message)
        self.transports['tcp'] = transport
        await transport.start(host, port)

    async def run_with_websocket(self, host: str = "0.0.0.0",
                                port: int = 9001) -> None:
        """Run server with WebSocket transport only"""
        transport = WebSocketTransport()
        transport.register_message_handler(self._handle_transport_message)
        self.transports['websocket'] = transport
        await transport.start(host, port)

    async def run_multi_transport(self,
                                 stdio: bool = True,
                                 tcp_host: str = "0.0.0.0",
                                 tcp_port: int = 9000,
                                 ws_host: str = "0.0.0.0",
                                 ws_port: int = 9001) -> None:
        """Run server with multiple transports simultaneously"""
        tasks = []

        # Stdio (Phase 1)
        if stdio:
            stdio_transport = StdioTransport()
            stdio_transport.register_message_handler(
                self._handle_transport_message
            )
            self.transports['stdio'] = stdio_transport
            tasks.append(stdio_transport.start())
            self.logger.info("Stdio transport enabled")

        # TCP (Phase 4)
        tcp_transport = TCPTransport()
        tcp_transport.register_message_handler(
            self._handle_transport_message
        )
        self.transports['tcp'] = tcp_transport
        tasks.append(tcp_transport.start(tcp_host, tcp_port))
        self.logger.info(f"TCP transport enabled on {tcp_host}:{tcp_port}")

        # WebSocket (Phase 4)
        ws_transport = WebSocketTransport()
        ws_transport.register_message_handler(
            self._handle_transport_message
        )
        self.transports['websocket'] = ws_transport
        tasks.append(ws_transport.start(ws_host, ws_port))
        self.logger.info(f"WebSocket transport enabled on {ws_host}:{ws_port}")

        # Run all transports concurrently
        await asyncio.gather(*tasks)

    async def _handle_transport_message(self, client_id: str,
                                       message: Dict[str, Any]) -> None:
        """Handle message from any transport"""
        # Create ClientContext (same as before)
        client = ClientContext(client_id=client_id)

        # Route to MCP handler
        response = await self._route_message(client, message)

        # Send response back through same transport
        for transport_name, transport in self.transports.items():
            if client_id in transport.clients:
                await transport.send_message(
                    client_id,
                    TransportMessage(response)
                )
                break
```

**Tests** (8 tests):
- `test_multi_transport_initialization` - All transports start
- `test_client_routing` - Messages routed correctly by transport
- `test_tool_execution_via_tcp` - Tool execution over TCP works
- `test_tool_execution_via_websocket` - Tool execution over WebSocket works
- `test_tool_execution_via_stdio` - Tool execution over Stdio still works
- `test_permissions_consistent_across_transports` - Permissions enforced equally
- `test_audit_logs_all_transports` - All transports logged in audit trail
- `test_simultaneous_clients_different_transports` - Multiple transports work together

## 🔐 Security Model (Phase 4)

### Authentication (From Phase 3)
- All transports require valid JWT from Phase 3
- JWT validation same across all transports
- ClientContext authentication check applies to all

### Authorization (From Phase 2-3)
- Permissions enforced same way across transports
- No transport-specific permissions
- All transports use same PermissionManager

### Network Security (Prepared for Phase 3.1)
- Code structured for optional TLS support
- Certificate parameters accepted but not enforced
- Will add TLS in Phase 3.1

### Audit Trail (Phase 2-3)
- All transports logged equally
- Audit entries include transport type
- Same audit trail across all transports

## 🚀 Implementation Checklist

- [ ] Create TCPTransport class (30 lines + tests)
- [ ] Create WebSocketTransport class (25 lines + tests)
- [ ] Modify MCPServer for multi-transport
- [ ] Write all 35 unit tests
- [ ] Create example TCP client
- [ ] Create example WebSocket client
- [ ] Write 15-20 integration tests
- [ ] Update documentation (CHANGELOG, README)
- [ ] Validate all acceptance criteria
- [ ] Performance testing

## 📈 Performance Considerations

### Scalability (Phase 4)
- Support ~100 concurrent connections (no limits set)
- Phase 7 will add connection pooling + load balancing
- TCP more efficient than WebSocket (less overhead)
- WebSocket better for browsers

### Resource Usage
- Each connection: ~1 KB memory overhead
- 100 clients = ~100 KB (negligible)
- Message buffering: configurable queue sizes

## 🔄 Backward Compatibility

### Phase 1-3 Compatibility
- ✓ Stdio transport unchanged
- ✓ Tool execution unchanged
- ✓ Permission system unchanged
- ✓ JWT authentication unchanged
- ✓ Audit logging unchanged
- ✓ All existing clients work

## 📋 Dependencies

### New Dependencies (for Phase 4)
- `aiohttp>=3.8,<4.0` - HTTP server and WebSocket
- `websockets>=11.0,<12.0` - WebSocket support

### Existing Dependencies (unchanged)
- `pydantic>=2.0,<3.0` - Data validation
- `PyJWT>=2.8,<3.0` - JWT handling
- `bcrypt>=4.1,<5.0` - Password hashing

---

**Version**: 1.0
**Status**: Ready for Implementation
**Date**: 2025-11-23

