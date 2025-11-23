# Phase 4 UseCase Definition - Network Transports (TCP/HTTP+WebSocket)

## 📋 UseCase Overview

**Title**: Network-based MCP Server with TCP and WebSocket Support

**Problem Statement**:
Currently, the MCP server only supports Stdio transport (local process communication via stdin/stdout). This limits the server to local client connections. We need to enable remote client connections over the network via TCP and HTTP+WebSocket protocols.

**Business Value**:
- Remote clients can connect to MCP server from different machines
- Browser-based clients can connect via WebSocket
- Enables integration with remote AI agents
- Supports multi-user scenarios
- Maintains backward compatibility with Stdio transport

## 🎯 Goals & Objectives

### Primary Goals
1. **TCP Transport**: Support raw TCP socket connections for network communication
   - JSON-RPC over TCP protocol
   - Support for multiple concurrent clients
   - Proper connection lifecycle management

2. **HTTP+WebSocket Transport**: Support modern web-based clients
   - HTTP endpoint for client connections
   - WebSocket upgrade for persistent connections
   - Browser-compatible communication

3. **Multi-Transport Architecture**: Support simultaneous use of multiple transports
   - Stdio (Phase 1) for local clients
   - TCP (Phase 4) for network clients
   - WebSocket (Phase 4) for web clients
   - All transports work independently

4. **Network Security**: Prepare for future mTLS (Phase 3.1)
   - SSL/TLS-ready architecture
   - Certificate support (prepared but not enforced)
   - Authentication via JWT from Phase 3

### Secondary Goals
1. Support multiple concurrent clients on TCP/WebSocket
2. Graceful client disconnection handling
3. Port configuration (default: 9000 for TCP, 9001 for HTTP/WebSocket)
4. Health checks for remote clients

## 📐 Architecture Overview

### Transport Layers (Pluggable)

```
┌─────────────────────────────────────────────────────────────────┐
│                         MCP Server                               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              Protocol Handler (MCP 2024-11)               │ │
│  │  (Handles initialization, routing, capabilities)          │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
     │              │              │
     │              │              │
┌────▼──────┐ ┌────▼──────┐ ┌────▼──────────┐
│   Stdio    │ │    TCP    │ │ WebSocket     │
│ Transport  │ │ Transport │ │ (HTTP+WS)     │
└────────────┘ └───────────┘ └───────────────┘
     │              │              │
     ▼              ▼              ▼
┌─────────┐   ┌──────────┐   ┌──────────────┐
│ stdin/  │   │TCP Socket│   │HTTP Server   │
│ stdout  │   │Client    │   │+ WebSocket   │
│ (local) │   │(network) │   │ (web)        │
└─────────┘   └──────────┘   └──────────────┘
```

## 📦 Components to Implement (Phase 4)

### 1. TCP Transport Layer
**File**: `mcp_server/transport/tcp_transport.py`

- **TCPTransport** class extending BaseTransport
- **TCPServer** class for listening on TCP port
- Support for multiple concurrent TCP client connections
- JSON-RPC message handling over TCP
- Connection lifecycle (accept, read, write, close)
- Error handling for network failures

**Key Methods**:
```python
class TCPTransport(BaseTransport):
    async def start(host: str, port: int)
    async def accept_connection() -> TCPClientConnection
    async def send_message(client_id, message)
    async def receive_message(client_id) -> message
    async def close_connection(client_id)
```

**Tests**: ~15 unit tests
- Server startup/shutdown
- Client connection/disconnection
- Message sending/receiving
- Multiple concurrent clients
- Network error handling

### 2. HTTP+WebSocket Transport Layer
**File**: `mcp_server/transport/websocket_transport.py`

- **WebSocketTransport** class extending BaseTransport
- HTTP server for upgrades to WebSocket
- WebSocket connection management
- Support for browser clients
- JSON-RPC over WebSocket

**Key Methods**:
```python
class WebSocketTransport(BaseTransport):
    async def start(host: str, port: int)
    async def accept_connection() -> WebSocketClientConnection
    async def send_message(client_id, message)
    async def receive_message(client_id) -> message
```

**Tests**: ~12 unit tests
- HTTP upgrade handshake
- WebSocket frame handling
- Browser client compatibility
- Multiple WebSocket clients

### 3. MCPServer Integration (Phase 4)
**File**: `mcp_server/core/mcp_server.py` (modified)

- Support multiple transports simultaneously
- Transport selection/initialization
- Client routing across transports
- Unified message handling

**Key Changes**:
```python
class MCPServer:
    async def run_with_stdio()          # Phase 1
    async def run_with_tcp()            # Phase 4 new
    async def run_with_websocket()      # Phase 4 new
    async def run_multi_transport()     # Phase 4 new (runs Stdio + TCP + WebSocket)
```

**Tests**: ~8 tests
- Multi-transport initialization
- Client identification across transports
- Message routing by transport type

## 🧪 Acceptance Criteria (Definition of Done)

### AC1: TCP Server Accepts Connections
**Scenario**: Start TCP server, connect remote client
- [ ] TCP server listens on configurable port (default 9000)
- [ ] Remote clients can connect via TCP socket
- [ ] Multiple clients can connect simultaneously
- [ ] Each client gets unique ID
- [ ] Connection established without errors

**Validation**:
```bash
# Terminal 1: Start server
python -c "asyncio.run(server.run_with_tcp('0.0.0.0', 9000))"

# Terminal 2: Connect with netcat
nc localhost 9000
# Should establish connection
```

### AC2: JSON-RPC over TCP Works
**Scenario**: Send MCP initialize request via TCP
- [ ] Client sends JSON-RPC request to TCP socket
- [ ] Server processes request (MCP initialize)
- [ ] Server returns proper JSON-RPC response
- [ ] Response contains protocol_version, capabilities, etc.

**Validation**:
```json
// Client sends
{"jsonrpc": "2.0", "method": "initialize", "params": {...}, "id": 1}

// Server responds
{"jsonrpc": "2.0", "result": {"protocolVersion": "2024-11", ...}, "id": 1}
```

### AC3: WebSocket Server Accepts Connections
**Scenario**: Browser client connects via WebSocket
- [ ] HTTP server listens on configurable port (default 9001)
- [ ] Browser can upgrade to WebSocket connection
- [ ] Multiple WebSocket clients can connect simultaneously
- [ ] Client receives upgrade confirmation

**Validation**:
```javascript
// Browser JavaScript
const ws = new WebSocket('ws://localhost:9001');
ws.onopen = () => console.log('Connected');
ws.onmessage = (e) => console.log('Message:', e.data);
```

### AC4: Multi-Transport Server Works
**Scenario**: Run server with all transports simultaneously
- [ ] Server can listen on Stdio, TCP, and WebSocket at same time
- [ ] Clients can connect via any transport
- [ ] Tools executed via any transport work identically
- [ ] Permissions checked consistently across transports
- [ ] Audit trail captures all transports

**Validation**:
```
Stdio client -> tool call -> executes ✓
TCP client -> tool call -> executes ✓
WebSocket client -> tool call -> executes ✓
All audit logged identically
```

### AC5: Backward Compatibility
**Scenario**: Existing Stdio clients continue to work
- [ ] Phase 1 Stdio transport still works
- [ ] Phase 2 tool execution unchanged
- [ ] Phase 3 authentication unchanged
- [ ] No breaking changes to existing APIs

## 📊 Implementation Strategy (AGILE)

### Step 1: Planning & Architecture (Current)
- [x] Define UseCase
- [x] Define acceptance criteria
- [ ] Create ARCHITECTURE_PHASE4.md
- [ ] Validate approach with user

### Step 2: Core TCP Transport Implementation
- [ ] Create TCPTransport class
- [ ] Implement connection handling
- [ ] Add JSON-RPC over TCP
- [ ] Write 15 unit tests
- [ ] Validate AC1 & AC2

### Step 3: Core WebSocket Transport Implementation
- [ ] Create WebSocketTransport class
- [ ] Implement HTTP+WebSocket upgrade
- [ ] Add JSON-RPC over WebSocket
- [ ] Write 12 unit tests
- [ ] Validate AC3

### Step 4: Multi-Transport Integration
- [ ] Modify MCPServer for multi-transport
- [ ] Update message routing
- [ ] Write 8 integration tests
- [ ] Validate AC4 & AC5

### Step 5: Integration Testing & Documentation
- [ ] Create example TCP client
- [ ] Create example WebSocket client
- [ ] Update examples/README.md
- [ ] Write integration tests (15-20 tests)
- [ ] Update CHANGELOG.md, README.md

## 🔒 Security Considerations (Phase 4)

### Current Security Model
- JWT authentication (from Phase 3) validates all clients
- All transports use same permission system
- Audit trail logs all transports equally

### Network Security (mTLS prepared for Phase 3.1)
- TLS support prepared but not enforced
- Will add in Phase 3.1 with optional mTLS
- For now: Rely on firewall + JWT authentication

### Risks & Mitigations
| Risk | Mitigation |
|------|-----------|
| Network man-in-the-middle | mTLS in Phase 3.1, for now: private network |
| DoS attacks | Rate limiting (Phase 7), connection limits |
| Invalid JSON-RPC | Validation same as Stdio |
| Client crashes | Graceful disconnect handling |

## 📝 Testing Strategy

### Unit Tests (35 tests total)
- TCP Transport: 15 tests
- WebSocket Transport: 12 tests
- MCPServer Phase 4: 8 tests

### Integration Tests (15-20 tests)
- TCP client connection workflow
- WebSocket browser compatibility
- Multi-transport simultaneous operation
- Tool execution across all transports
- Permission checking consistency
- Audit trail consistency

### Example Clients
- `examples/example_tcp_client.py` - TCP raw socket client
- `examples/example_websocket_client.py` - WebSocket browser client
- `examples/example_multi_transport_server.py` - Server with all transports

## 🎬 Success Criteria

✅ **Phase 4 Complete When**:
1. All 35 unit tests PASS
2. All 15-20 integration tests PASS
3. All 5 acceptance criteria validated
4. TCP and WebSocket example clients work correctly
5. Multi-transport server can run all transports simultaneously
6. Documentation complete (CHANGELOG, README, architecture)
7. No breaking changes to Phase 1-3

---

## Questions for Clarification

1. **Port Configuration**: Should ports be configurable? (yes - args)
2. **Concurrent Clients**: Should limit concurrent connections? (no limit for now, prepare for Phase 7)
3. **Message Format**: Keep same JSON-RPC format? (yes)
4. **TLS Preparation**: Should structure code for TLS-readiness? (yes, but not enforce)
5. **Load Balancing**: Out of scope for Phase 4? (yes, Phase 7+)

---

**Version**: 1.0
**Status**: Ready for Architecture Design
**Date**: 2025-11-23

