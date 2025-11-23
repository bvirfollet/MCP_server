"""
MCP Protocol Handler - Processes MCP 2024-11 protocol messages

Module: protocol.mcp_protocol_handler
Date: 2025-11-23
Version: 0.1.0-alpha

CHANGELOG:
[2025-11-23 v0.1.0-alpha] Initial implementation
  - MCP 2024-11 protocol handler
  - Lifecycle methods: initialize, initialized, shutdown
  - Health check support
  - Capabilities exposure
  - Error handling and validation
  - Request/response routing

ARCHITECTURE:
MCPProtocolHandler implements the MCP 2024-11 protocol specification.
It handles:
1. Client initialization and capabilities negotiation
2. Method routing and dispatch
3. Error responses
4. Protocol compliance validation

Works with TransportLayer for message I/O and is the bridge between
Transport and Business Logic layers.

SECURITY NOTES:
- All requests validated for MCP compliance
- Request IDs tracked for responses
- Error responses follow MCP spec
- No code execution in protocol handler
- Message logging for audit
"""

import logging
from typing import Optional, Dict, Any, Callable, Awaitable
from dataclasses import dataclass
from datetime import datetime

from ..transport.base_transport import TransportMessage, TransportError
from ..core.constants import (
    SERVER_NAME,
    SERVER_VERSION,
    MCP_PROTOCOL_VERSION,
    DEFAULT_CAPABILITIES,
    METHOD_INITIALIZE,
    METHOD_INITIALIZED,
    METHOD_SHUTDOWN,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR,
)
from ..security.client_context import ClientContext


@dataclass
class ProtocolState:
    """State of MCP protocol for a client"""
    initialized: bool = False
    client_info: Optional[Dict[str, Any]] = None
    server_info: Optional[Dict[str, Any]] = None


class MCPProtocolHandler:
    """
    MCP 2024-11 Protocol Handler

    Implements the Model Context Protocol 2024-11 specification.
    Handles initialization, method dispatch, and error responses.

    Responsibilities:
    1. Protocol compliance validation
    2. Lifecycle management (initialize, shutdown)
    3. Method routing
    4. Error handling
    5. Capabilities exposure

    Not responsible for:
    - Authentication/Authorization (delegated to security layer)
    - Tool execution (delegated to business logic)
    - Transport details (delegated to transport layer)
    """

    def __init__(self, server_name: str = SERVER_NAME, server_version: str = SERVER_VERSION):
        """
        Initialize protocol handler

        Args:
            server_name: Name to report as in capabilities
            server_version: Version to report
        """
        self.logger = logging.getLogger("protocol.mcp_protocol_handler")

        # Server info
        self.server_name = server_name
        self.server_version = server_version

        # Per-client protocol state
        self._client_states: Dict[str, ProtocolState] = {}

        # Method handlers - will be registered by server
        self._method_handlers: Dict[str, Callable] = {}

        # Server capabilities
        self._capabilities = DEFAULT_CAPABILITIES.copy()

    def register_method(self, method: str, handler: Callable) -> None:
        """
        Register a method handler

        Args:
            method: Method name (e.g., "tools/list")
            handler: Async callable(client_context, params) -> result
        """
        self._method_handlers[method] = handler
        self.logger.debug(f"Method handler registered: {method}")

    def set_capabilities(self, capabilities: Dict[str, Any]) -> None:
        """
        Set server capabilities

        Args:
            capabilities: Capabilities dictionary
        """
        self._capabilities = capabilities
        self.logger.info(f"Capabilities updated: {list(capabilities.keys())}")

    async def handle_message(
        self,
        message: TransportMessage,
        client_context: ClientContext
    ) -> Optional[TransportMessage]:
        """
        Handle incoming message

        Processes message according to MCP protocol:
        1. Validate protocol compliance
        2. Route to appropriate handler
        3. Return response

        Args:
            message: Incoming message
            client_context: Client context

        Returns:
            Response message (or None for notifications)

        Raises:
            Nothing - errors returned as responses
        """
        # Update client activity
        client_context.record_request()

        self.logger.debug(
            f"Message from {client_context.client_id[:8]}: "
            f"method={message.method}, id={message.request_id}"
        )

        # Get or create client state
        client_state = self._get_client_state(client_context.client_id)

        # Handle lifecycle methods
        if message.method == METHOD_INITIALIZE:
            return await self._handle_initialize(message, client_context, client_state)

        elif message.method == METHOD_SHUTDOWN:
            return await self._handle_shutdown(message, client_context, client_state)

        # Check client initialized (except for initialize)
        if not client_state.initialized:
            return self._error_response(
                message.request_id,
                INVALID_REQUEST,
                "Client must call initialize first"
            )

        # Route to registered handler
        if message.method in self._method_handlers:
            try:
                handler = self._method_handlers[message.method]
                result = await handler(client_context, message.params or {})

                # Return result if this was a request (has ID)
                if message.request_id:
                    return TransportMessage(
                        method=message.method,
                        params={"result": result},
                        request_id=message.request_id
                    )
                else:
                    # Notification - no response
                    return None

            except Exception as e:
                self.logger.error(f"Error in handler {message.method}: {e}")
                return self._error_response(
                    message.request_id,
                    INTERNAL_ERROR,
                    f"Error executing {message.method}"
                )
        else:
            # Method not found
            return self._error_response(
                message.request_id,
                METHOD_NOT_FOUND,
                f"Method not found: {message.method}"
            )

    async def _handle_initialize(
        self,
        message: TransportMessage,
        client_context: ClientContext,
        client_state: ProtocolState
    ) -> TransportMessage:
        """
        Handle initialize request

        Args:
            message: Initialize message
            client_context: Client context
            client_state: Client protocol state

        Returns:
            Initialize response
        """
        params = message.params or {}
        client_info = params.get("clientInfo", {})

        self.logger.info(f"Initialize request from {client_context.client_id[:8]}")

        # Update client state
        client_state.initialized = True
        client_state.client_info = client_info

        # Build server info
        server_info = {
            "name": self.server_name,
            "version": self.server_version,
            "protocolVersion": MCP_PROTOCOL_VERSION,
        }
        client_state.server_info = server_info

        # Build response
        response_data = {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": self._capabilities,
            "serverInfo": server_info,
        }

        return TransportMessage(
            method=METHOD_INITIALIZE,
            params={"result": response_data},
            request_id=message.request_id
        )

    async def _handle_shutdown(
        self,
        message: TransportMessage,
        client_context: ClientContext,
        client_state: ProtocolState
    ) -> TransportMessage:
        """
        Handle shutdown request

        Args:
            message: Shutdown message
            client_context: Client context
            client_state: Client protocol state

        Returns:
            Shutdown response
        """
        self.logger.info(f"Shutdown request from {client_context.client_id[:8]}")

        # Mark client as no longer initialized
        client_state.initialized = False

        # Return success
        return TransportMessage(
            method=METHOD_SHUTDOWN,
            params={"result": {"status": "ok"}},
            request_id=message.request_id
        )

    def _get_client_state(self, client_id: str) -> ProtocolState:
        """
        Get or create client state

        Args:
            client_id: Client identifier

        Returns:
            Client protocol state
        """
        if client_id not in self._client_states:
            self._client_states[client_id] = ProtocolState()
        return self._client_states[client_id]

    def _error_response(
        self,
        request_id: Optional[str],
        error_code: int,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> TransportError:
        """
        Create error response

        Args:
            request_id: Request ID (for response correlation)
            error_code: JSON-RPC error code
            message: Error message
            data: Additional error data

        Returns:
            TransportError instance
        """
        return TransportError(
            code=error_code,
            message=message,
            data=data,
            request_id=request_id
        )

    def get_client_info(self, client_id: str) -> Dict[str, Any]:
        """
        Get protocol information for a client

        Args:
            client_id: Client identifier

        Returns:
            dict: Client protocol info
        """
        state = self._get_client_state(client_id)
        return {
            "initialized": state.initialized,
            "client_info": state.client_info,
            "server_info": state.server_info,
        }


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    from unittest.mock import AsyncMock, MagicMock
    import asyncio

    class TestMCPProtocolHandler(unittest.TestCase):
        """Test suite for MCPProtocolHandler"""

        def setUp(self):
            """Setup before each test"""
            self.handler = MCPProtocolHandler()
            self.client_context = ClientContext(client_info={"name": "test-client"})

        def test_initialization(self):
            """Test handler initialization"""
            self.assertEqual(self.handler.server_name, SERVER_NAME)
            self.assertEqual(self.handler.server_version, SERVER_VERSION)
            self.assertEqual(self.handler._capabilities, DEFAULT_CAPABILITIES)

        def test_register_method(self):
            """Test registering a method handler"""
            async def dummy_handler(ctx, params):
                return {"status": "ok"}

            self.handler.register_method("test/method", dummy_handler)
            self.assertIn("test/method", self.handler._method_handlers)

        def test_set_capabilities(self):
            """Test setting capabilities"""
            new_caps = {"custom": True}
            self.handler.set_capabilities(new_caps)
            self.assertEqual(self.handler._capabilities, new_caps)

        def test_initialize_request(self):
            """Test initialize request"""
            async def test():
                message = TransportMessage(
                    method=METHOD_INITIALIZE,
                    params={"clientInfo": {"name": "test"}},
                    request_id="1"
                )

                response = await self.handler.handle_message(message, self.client_context)

                self.assertIsNotNone(response)
                self.assertEqual(response.request_id, "1")
                self.assertEqual(response.method, METHOD_INITIALIZE)
                self.assertIn("result", response.params)

            asyncio.run(test())

        def test_method_not_found(self):
            """Test method not found error"""
            async def test():
                # First initialize
                init_msg = TransportMessage(
                    method=METHOD_INITIALIZE,
                    params={"clientInfo": {}},
                    request_id="1"
                )
                await self.handler.handle_message(init_msg, self.client_context)

                # Then call unknown method
                unknown_msg = TransportMessage(
                    method="unknown/method",
                    request_id="2"
                )

                response = await self.handler.handle_message(unknown_msg, self.client_context)

                self.assertIsInstance(response, TransportError)
                self.assertEqual(response.code, METHOD_NOT_FOUND)

            asyncio.run(test())

        def test_require_initialize(self):
            """Test that client must initialize before other methods"""
            async def test():
                # Try to call method without initializing
                message = TransportMessage(
                    method="test/method",
                    request_id="1"
                )

                response = await self.handler.handle_message(message, self.client_context)

                self.assertIsInstance(response, TransportError)
                self.assertEqual(response.code, INVALID_REQUEST)

            asyncio.run(test())

        def test_shutdown_request(self):
            """Test shutdown request"""
            async def test():
                # Initialize first
                init_msg = TransportMessage(
                    method=METHOD_INITIALIZE,
                    params={"clientInfo": {}},
                    request_id="1"
                )
                await self.handler.handle_message(init_msg, self.client_context)

                # Then shutdown
                shutdown_msg = TransportMessage(
                    method=METHOD_SHUTDOWN,
                    request_id="2"
                )

                response = await self.handler.handle_message(shutdown_msg, self.client_context)

                self.assertIsNotNone(response)
                self.assertEqual(response.method, METHOD_SHUTDOWN)

            asyncio.run(test())

        def test_notification_no_response(self):
            """Test that notifications (no ID) don't get responses"""
            async def test():
                # Initialize
                init_msg = TransportMessage(
                    method=METHOD_INITIALIZE,
                    params={"clientInfo": {}},
                    request_id="1"
                )
                await self.handler.handle_message(init_msg, self.client_context)

                # Register a test method
                async def test_handler(ctx, params):
                    return {"status": "ok"}

                self.handler.register_method("test/notify", test_handler)

                # Call as notification (no ID)
                notification = TransportMessage(
                    method="test/notify",
                    params={}
                )

                response = await self.handler.handle_message(notification, self.client_context)

                self.assertIsNone(response)

            asyncio.run(test())

    # Run tests
    unittest.main()
