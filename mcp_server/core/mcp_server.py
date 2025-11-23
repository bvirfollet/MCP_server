"""
MCP Server - Main server orchestrator

Module: core.mcp_server
Date: 2025-11-23
Version: 0.2.0-alpha

CHANGELOG:
[2025-11-23 v0.2.0-alpha] Phase 2 integration
  - Integrated ToolManager for tool registration
  - Integrated PermissionManager for authorization
  - Integrated ExecutionManager for secure execution
  - Added tools/list and tools/call handlers
  - Added @server.tool() decorator support
  - Client sandbox contexts management

[2025-11-23 v0.1.0-alpha] Initial implementation
  - Main MCP server class
  - Transport management (start/stop)
  - Protocol handler orchestration
  - Health check support
  - Capabilities management
  - Request routing and message handling
  - Graceful shutdown

ARCHITECTURE:
MCPServer is the main entry point that:
1. Manages transport layer (Stdio, TCP, DBus)
2. Coordinates with protocol handler
3. Routes messages from transport to handlers
4. Manages client lifecycle
5. Provides health checks and status

This is the class that applications will use directly.

SECURITY NOTES:
- All messages go through protocol validation
- Client contexts tracked for audit
- Health check available for monitoring
- Graceful shutdown for resource cleanup
"""

import asyncio
import logging
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .constants import (
    SERVER_NAME,
    SERVER_VERSION,
    MCP_PROTOCOL_VERSION,
    DEFAULT_CAPABILITIES,
    DEFAULT_REQUEST_TIMEOUT,
    METHOD_INITIALIZE,
)
from ..transport.base_transport import BaseTransport, TransportMessage, TransportError
from ..transport.stdio_transport import StdioTransport
from ..protocol.mcp_protocol_handler import MCPProtocolHandler
from ..security.client_context import ClientContext
from ..tools.tool_manager import ToolManager
from ..security.permission_manager import PermissionManager
from ..resources.execution_manager import ExecutionManager
from ..resources.sandbox_context import SandboxContext

# Phase 3: Authentication & Persistence
from ..security.authentication import (
    JWTHandler,
    JWTError,
    JWTExpiredError,
    ClientManager,
    ClientError,
)
from ..persistence import (
    TokenManager,
    AuditLogger,
)


@dataclass
class ServerStatus:
    """Status information about the server"""
    name: str
    version: str
    protocol_version: str
    is_running: bool
    is_listening: bool
    uptime_seconds: float
    total_requests: int
    active_clients: int
    capabilities: Dict[str, Any]
    timestamp: datetime


class MCPServer:
    """
    Main MCP Server

    Orchestrates the entire MCP server:
    - Manages transport layers
    - Coordinates protocol handler
    - Routes messages
    - Manages client lifecycle
    - Provides health checks

    Typical usage:
        server = MCPServer()
        # Register tools...
        await server.start()
    """

    def __init__(
        self,
        server_name: str = SERVER_NAME,
        server_version: str = SERVER_VERSION,
        data_dir: str = "./data",
        jwt_secret_key: Optional[str] = None,
    ):
        """
        Initialize MCP Server

        Args:
            server_name: Name for this server instance
            server_version: Version string
            data_dir: Directory for persistent data (Phase 3)
            jwt_secret_key: Secret key for JWT signing (defaults to env var or generated)
        """
        self.logger = logging.getLogger("core.mcp_server")

        # Server identity
        self.server_name = server_name
        self.server_version = server_version

        # Transport layer
        self.transport: Optional[BaseTransport] = None

        # Protocol handler
        self.protocol_handler = MCPProtocolHandler(server_name, server_version)

        # Client tracking
        self._clients: Dict[str, ClientContext] = {}
        self._total_requests = 0

        # Phase 2: Tool & Permission Management
        self.tool_manager = ToolManager()
        self.permission_manager = PermissionManager()
        self.execution_manager = ExecutionManager(self.permission_manager)

        # Sandbox contexts per client
        self._sandbox_contexts: Dict[str, SandboxContext] = {}

        # Phase 3: Authentication & Persistence
        self.data_dir = data_dir

        # JWT Handler
        jwt_secret = jwt_secret_key or os.getenv(
            "JWT_SECRET_KEY",
            "changeme-32-chars-minimum-for-development-only!!!!"
        )
        self.jwt_handler = JWTHandler(
            secret_key=jwt_secret,
            access_token_expire_minutes=60,
            refresh_token_expire_days=7,
        )

        # Token & Client Management
        self.token_manager = TokenManager(data_dir)
        self.client_manager = ClientManager(data_dir)

        # Audit Logger
        self.audit_logger = AuditLogger(data_dir)

        # Server state
        self._is_running = False
        self._startup_time: Optional[datetime] = None

        # Capabilities
        self._capabilities = DEFAULT_CAPABILITIES.copy()
        # Add tools capability
        self._capabilities["tools"] = {}

        # Register Phase 2 method handlers
        self.register_method("tools/list", self._handle_tools_list)
        self.register_method("tools/call", self._handle_tools_call)

        # Register Phase 3 method handlers
        self.register_method("auth/token", self._handle_auth_token)
        self.register_method("auth/refresh", self._handle_auth_refresh)
        self.register_method("auth/revoke", self._handle_auth_revoke)

        self.logger.info(f"Server initialized: {server_name} v{server_version}")
        self.logger.info(f"Data directory: {data_dir}")
        self.logger.info("Phase 3 (Authentication) initialized")

    @property
    def is_running(self) -> bool:
        """Check if server is running"""
        return self._is_running

    @property
    def is_listening(self) -> bool:
        """Check if transport is listening"""
        return self.transport is not None and self.transport.is_running

    @property
    def active_clients(self) -> int:
        """Get number of active clients"""
        return len(self._clients)

    @property
    def uptime_seconds(self) -> float:
        """Get uptime in seconds"""
        if not self._startup_time:
            return 0.0
        return (datetime.utcnow() - self._startup_time).total_seconds()

    def set_transport(self, transport: BaseTransport) -> None:
        """
        Set the transport layer

        Args:
            transport: Transport instance to use

        Raises:
            RuntimeError: If server already running
        """
        if self._is_running:
            raise RuntimeError("Cannot change transport while running")

        self.transport = transport
        self.logger.info(f"Transport set: {transport.name}")

    def set_capabilities(self, capabilities: Dict[str, Any]) -> None:
        """
        Set server capabilities

        Args:
            capabilities: Capabilities dictionary
        """
        self._capabilities = capabilities
        self.protocol_handler.set_capabilities(capabilities)
        self.logger.info(f"Capabilities set: {list(capabilities.keys())}")

    def register_method(self, method: str, handler) -> None:
        """
        Register a method handler

        Args:
            method: Method name (e.g., "tools/list")
            handler: Async callable(client_context, params) -> result
        """
        self.protocol_handler.register_method(method, handler)
        self.logger.debug(f"Method registered: {method}")

    def tool(self, name: str, description: str, **kwargs):
        """
        Decorator to register a tool

        Usage:
            @server.tool(
                name="read_file",
                description="Read a file",
                input_schema={"path": {"type": "string"}},
                permissions=[Permission(PermissionType.FILE_READ, "/app/data/*")]
            )
            async def read_file(client, params):
                return {"content": "..."}

        Args:
            name: Tool name
            description: Tool description
            **kwargs: Additional arguments (input_schema, output_schema, permissions, timeout)

        Returns:
            decorator: Function decorator
        """
        return self.tool_manager.tool(name, description, **kwargs)

    async def start(self) -> None:
        """
        Start the server

        Starts transport and begins listening for connections

        Raises:
            RuntimeError: If transport not configured
        """
        if self._is_running:
            self.logger.warning("Server already running")
            return

        if not self.transport:
            # Use stdio transport by default
            self.transport = StdioTransport()
            self.logger.info("Using default Stdio transport")

        # Start transport
        try:
            await self.transport.start()

            # Register message and error handlers
            await self.transport.set_message_handler(self._handle_transport_message)
            await self.transport.set_error_handler(self._handle_transport_error)

            self._is_running = True
            self._startup_time = datetime.utcnow()

            self.logger.info(f"Server started: {self.server_name} v{self.server_version}")
            self.logger.info(f"Transport: {self.transport.name}")
            self.logger.info(f"Protocol: MCP {MCP_PROTOCOL_VERSION}")

        except Exception as e:
            self.logger.error(f"Failed to start server: {e}")
            raise

    async def stop(self) -> None:
        """
        Stop the server

        Stops transport and closes all connections
        """
        if not self._is_running:
            return

        self._is_running = False

        if self.transport:
            try:
                await self.transport.stop()
                self.logger.info("Transport stopped")
            except Exception as e:
                self.logger.error(f"Error stopping transport: {e}")

        self.logger.info("Server stopped")

    async def run(self) -> None:
        """
        Run server until interrupted

        Starts server and runs forever (until SIGINT/SIGTERM)
        """
        await self.start()

        try:
            # Keep running
            while self._is_running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
        finally:
            await self.stop()

    def get_status(self) -> ServerStatus:
        """
        Get server status

        Returns:
            ServerStatus: Current server status
        """
        return ServerStatus(
            name=self.server_name,
            version=self.server_version,
            protocol_version=MCP_PROTOCOL_VERSION,
            is_running=self._is_running,
            is_listening=self.is_listening,
            uptime_seconds=self.uptime_seconds,
            total_requests=self._total_requests,
            active_clients=self.active_clients,
            capabilities=self._capabilities,
            timestamp=datetime.utcnow()
        )

    async def _handle_transport_message(self, message: TransportMessage) -> None:
        """
        Handle message from transport

        Internal handler called by transport when message received

        Args:
            message: Received message
        """
        try:
            # Get or create client context
            # In Phase 1, we use a default client ID from transport
            # In Phase 3+, this will be based on authentication
            client_id = getattr(message, "_client_id", "default-client")

            if client_id not in self._clients:
                self._clients[client_id] = ClientContext()

            client = self._clients[client_id]
            self._total_requests += 1

            # Process message through protocol handler
            response = await self.protocol_handler.handle_message(message, client)

            # Send response if any
            if response is not None:
                if isinstance(response, TransportError):
                    await self.transport.send_error(response)
                else:
                    await self.transport.send_message(response)

        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            error = TransportError(
                code=-32603,
                message="Internal server error",
                request_id=getattr(message, "request_id", None)
            )
            try:
                await self.transport.send_error(error)
            except Exception as send_error:
                self.logger.error(f"Error sending error response: {send_error}")

    async def _handle_transport_error(self, error: TransportError) -> None:
        """
        Handle error from transport

        Internal handler called by transport on errors

        Args:
            error: Transport error
        """
        self.logger.warning(f"Transport error: {error.message}")
        # Try to send error response if possible
        try:
            await self.transport.send_error(error)
        except Exception as e:
            self.logger.error(f"Could not send error response: {e}")

    async def _handle_tools_list(
        self,
        client: ClientContext,
        params: dict
    ) -> dict:
        """
        Handle tools/list request

        Returns list of available tools with their metadata.

        Args:
            client: Client context
            params: Request parameters (unused)

        Returns:
            dict: {"tools": [...]} with tool information
        """
        self.logger.debug(f"Client {client.client_id} requested tools list")

        # Get tools visible to this client
        tools_info = self.tool_manager.get_info_for_client(client)

        return {"tools": tools_info}

    async def _handle_tools_call(
        self,
        client: ClientContext,
        params: dict
    ) -> dict:
        """
        Handle tools/call request

        Executes a tool with provided parameters.

        Args:
            client: Client context
            params: {"name": "tool_name", "arguments": {...}}

        Returns:
            dict: Tool execution result

        Raises:
            ValueError: If tool not found or parameters invalid
        """
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            raise ValueError("Tool name is required")

        self.logger.info(
            f"Client {client.client_id} calling tool: {tool_name}"
        )

        # Get tool
        tool = self.tool_manager.get(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        # Ensure client has permissions initialized
        if client.client_id not in self.permission_manager._client_permissions:
            self.permission_manager.initialize_client(client.client_id)

        # Execute tool securely
        result = await self.execution_manager.execute_tool(
            tool, client, arguments
        )

        return result

    # ========================================================================
    # Phase 3: Authentication Handlers
    # ========================================================================

    async def _handle_auth_token(
        self,
        client: ClientContext,
        params: dict
    ) -> dict:
        """
        Handle auth/token request - Authenticate client

        Args:
            client: Client context
            params: {"username": "...", "password": "..."}

        Returns:
            dict: {"access_token": "...", "refresh_token": "...", "expires_in": 3600}

        Raises:
            ValueError: If authentication fails
        """
        username = params.get("username")
        password = params.get("password")

        if not username or not password:
            raise ValueError("username and password required")

        try:
            # Authenticate client
            client_record = self.client_manager.authenticate(username, password)

            # Generate tokens
            token_pair = self.jwt_handler.generate_tokens(
                client_id=client_record.client_id,
                username=client_record.username,
                roles=client_record.roles,
            )

            # Store tokens
            self.token_manager.create_token(
                jti=token_pair.access_token.split(".")[-2][:8],  # Use part of JWT as JTI
                client_id=client_record.client_id,
                username=client_record.username,
                access_token=token_pair.access_token,
                refresh_token=token_pair.refresh_token,
                access_expires_at=token_pair.access_expires_at,
                refresh_expires_at=token_pair.refresh_expires_at,
            )

            # Log authentication
            self.audit_logger.log_auth_success(
                client_id=client_record.client_id,
                username=client_record.username,
            )

            # Enrich client context
            client.authenticated = True
            client.user_id = client_record.client_id
            client.username = client_record.username
            client.roles = client_record.roles
            client.auth_time = datetime.now(timezone.utc)

            return {
                "access_token": token_pair.access_token,
                "refresh_token": token_pair.refresh_token,
                "expires_in": 3600,
                "token_type": "Bearer",
            }

        except ClientError as e:
            # Log failed authentication
            self.audit_logger.log_auth_failed(
                username=username,
                reason=str(e),
            )
            raise ValueError(f"Authentication failed: {e}")

    async def _handle_auth_refresh(
        self,
        client: ClientContext,
        params: dict
    ) -> dict:
        """
        Handle auth/refresh request - Refresh access token

        Args:
            client: Client context
            params: {"refresh_token": "..."}

        Returns:
            dict: {"access_token": "...", "expires_in": 3600}

        Raises:
            ValueError: If refresh fails
        """
        refresh_token = params.get("refresh_token")

        if not refresh_token:
            raise ValueError("refresh_token required")

        try:
            # Validate refresh token and get new access token
            access_token = self.jwt_handler.refresh_access_token(refresh_token)

            # Log token refresh
            self.audit_logger.log_event(
                event_type="auth_token_refresh",
                client_id=client.user_id,
                username=client.username,
                status="success",
                message="Access token refreshed",
            )

            return {
                "access_token": access_token,
                "expires_in": 3600,
                "token_type": "Bearer",
            }

        except (JWTError, JWTExpiredError) as e:
            raise ValueError(f"Token refresh failed: {e}")

    async def _handle_auth_revoke(
        self,
        client: ClientContext,
        params: dict
    ) -> dict:
        """
        Handle auth/revoke request - Revoke a token

        Args:
            client: Client context
            params: {"jti": "..."}

        Returns:
            dict: {"status": "revoked"}

        Raises:
            ValueError: If revocation fails
        """
        jti = params.get("jti")

        if not jti:
            raise ValueError("jti required")

        try:
            # Revoke token
            self.token_manager.revoke_token(jti)

            # Log token revocation
            self.audit_logger.log_event(
                event_type="auth_token_revoked",
                client_id=client.user_id,
                username=client.username,
                status="success",
                message=f"Token revoked: {jti}",
                details={"jti": jti},
            )

            return {"status": "revoked"}

        except Exception as e:
            raise ValueError(f"Token revocation failed: {e}")


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    from unittest.mock import AsyncMock, MagicMock, patch
    import asyncio

    class TestMCPServer(unittest.TestCase):
        """Test suite for MCPServer"""

        def setUp(self):
            """Setup before each test"""
            self.server = MCPServer()

        def test_initialization(self):
            """Test server initialization"""
            self.assertEqual(self.server.server_name, SERVER_NAME)
            self.assertEqual(self.server.server_version, SERVER_VERSION)
            self.assertFalse(self.server.is_running)
            self.assertEqual(self.server.active_clients, 0)
            self.assertEqual(self.server.uptime_seconds, 0.0)

        def test_set_transport(self):
            """Test setting transport"""
            transport = StdioTransport()
            self.server.set_transport(transport)
            self.assertEqual(self.server.transport, transport)

        def test_cannot_change_transport_while_running(self):
            """Test that transport cannot be changed while running"""
            self.server._is_running = True
            transport = StdioTransport()

            with self.assertRaises(RuntimeError):
                self.server.set_transport(transport)

        def test_set_capabilities(self):
            """Test setting capabilities"""
            caps = {"custom": True}
            self.server.set_capabilities(caps)
            self.assertEqual(self.server._capabilities, caps)

        def test_register_method(self):
            """Test registering method"""
            async def handler(ctx, params):
                return {"status": "ok"}

            self.server.register_method("test/method", handler)
            self.assertIn("test/method", self.server.protocol_handler._method_handlers)

        def test_active_clients_count(self):
            """Test active clients tracking"""
            self.assertEqual(self.server.active_clients, 0)

            client1 = ClientContext()
            client2 = ClientContext()
            self.server._clients[client1.client_id] = client1
            self.server._clients[client2.client_id] = client2

            self.assertEqual(self.server.active_clients, 2)

        def test_get_status(self):
            """Test getting server status"""
            status = self.server.get_status()

            self.assertEqual(status.name, SERVER_NAME)
            self.assertEqual(status.version, SERVER_VERSION)
            self.assertEqual(status.protocol_version, MCP_PROTOCOL_VERSION)
            self.assertFalse(status.is_running)
            self.assertFalse(status.is_listening)

        def test_uptime_calculation(self):
            """Test uptime calculation"""
            self.assertEqual(self.server.uptime_seconds, 0.0)

            import time
            self.server._startup_time = datetime.utcnow()
            time.sleep(0.1)

            uptime = self.server.uptime_seconds
            self.assertGreater(uptime, 0.0)
            self.assertLess(uptime, 1.0)

    # Run tests
    unittest.main()
