"""
Base Transport Class - Abstract interface for all transport implementations

Module: transport.base_transport
Date: 2025-11-23
Version: 0.1.0-alpha

CHANGELOG:
[2025-11-23 v0.1.0-alpha] Initial implementation
  - Abstract BaseTransport class
  - Message send/receive interface
  - Connection lifecycle methods
  - Error handling framework
  - Async-first design using asyncio

ARCHITECTURE:
BaseTransport is the abstract base class that all transport implementations
(Stdio, TCP, DBus) must inherit from. It defines the contract for:
- Starting/stopping the transport
- Sending/receiving JSON-RPC messages
- Handling connections
- Managing state

SECURITY NOTES:
- All messages are JSON-RPC 2.0 compliant
- Subclasses must implement encryption if needed
- Message validation delegated to protocol layer
- Connection authentication delegated to protocol layer
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable, Awaitable
import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime


# ============================================================================
# Types and Data Classes
# ============================================================================

@dataclass
class TransportMessage:
    """
    Represents a message transported by a Transport instance

    Attributes:
        method: JSON-RPC method name or notification
        params: JSON-RPC parameters
        id: JSON-RPC request ID (None for notifications)
        timestamp: When message was created
    """
    method: str
    params: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        """Initialize timestamp if not provided"""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def to_jsonrpc(self) -> Dict[str, Any]:
        """
        Convert to JSON-RPC 2.0 format

        Returns:
            dict: JSON-RPC 2.0 compatible dictionary
        """
        msg = {
            "jsonrpc": "2.0",
            "method": self.method,
        }

        if self.params is not None:
            msg["params"] = self.params

        if self.request_id is not None:
            msg["id"] = self.request_id

        return msg

    @staticmethod
    def from_jsonrpc(data: Dict[str, Any]) -> "TransportMessage":
        """
        Parse JSON-RPC 2.0 message

        Args:
            data: JSON-RPC dictionary

        Returns:
            TransportMessage: Parsed message

        Raises:
            ValueError: If message format is invalid
        """
        if not isinstance(data, dict):
            raise ValueError("Message must be a dictionary")

        method = data.get("method")
        if not method:
            raise ValueError("Missing 'method' field")

        return TransportMessage(
            method=method,
            params=data.get("params"),
            request_id=data.get("id"),
            timestamp=datetime.utcnow()
        )


@dataclass
class TransportError:
    """
    Represents a transport-level error response

    Attributes:
        code: Error code
        message: Error message
        data: Additional error data
        request_id: ID of request that caused error (if applicable)
    """
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None

    def to_jsonrpc_error(self) -> Dict[str, Any]:
        """
        Convert to JSON-RPC 2.0 error format

        Returns:
            dict: JSON-RPC error response
        """
        response = {
            "jsonrpc": "2.0",
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }

        if self.data is not None:
            response["error"]["data"] = self.data

        if self.request_id is not None:
            response["id"] = self.request_id

        return response


# ============================================================================
# Abstract Base Transport Class
# ============================================================================

class BaseTransport(ABC):
    """
    Abstract base class for all transport implementations

    All transport implementations (Stdio, TCP, DBus) must inherit from this
    class and implement all abstract methods.

    The transport layer is responsible for:
    1. Physical message transmission/reception
    2. Connection management
    3. Encoding/decoding (JSON for MCP)
    4. Transport-specific error handling

    Not responsible for:
    1. Authentication/Authorization (Protocol layer)
    2. Message validation (Protocol layer)
    3. Tool execution (Business logic layer)
    """

    def __init__(self, name: str):
        """
        Initialize transport

        Args:
            name: Name of this transport instance
        """
        self.name = name
        self.is_running = False
        self.is_connected = False
        self.logger = logging.getLogger(f"transport.{name}")

        # Message handlers
        self._message_handler: Optional[Callable[[TransportMessage], Awaitable[None]]] = None
        self._error_handler: Optional[Callable[[TransportError], Awaitable[None]]] = None

    @property
    def status(self) -> str:
        """Get current transport status"""
        if not self.is_running:
            return "stopped"
        elif self.is_connected:
            return "connected"
        else:
            return "running"

    @abstractmethod
    async def start(self) -> None:
        """
        Start the transport

        Must be implemented by subclasses to:
        1. Bind to address/socket
        2. Start listening for connections
        3. Initialize any transport-specific resources

        Raises:
            Exception: If transport cannot be started
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """
        Stop the transport

        Must be implemented by subclasses to:
        1. Close all connections
        2. Unbind from address/socket
        3. Clean up resources
        4. Set is_running = False
        """
        pass

    @abstractmethod
    async def send_message(self, message: TransportMessage) -> None:
        """
        Send a message

        Must be implemented by subclasses to:
        1. Serialize message to JSON
        2. Transmit over transport
        3. Handle transmission errors

        Args:
            message: Message to send

        Raises:
            RuntimeError: If transport not connected
            IOError: If transmission fails
        """
        pass

    @abstractmethod
    async def send_error(self, error: TransportError) -> None:
        """
        Send an error response

        Must be implemented by subclasses to:
        1. Serialize error to JSON-RPC format
        2. Transmit over transport
        3. Handle transmission errors

        Args:
            error: Error to send

        Raises:
            RuntimeError: If transport not connected
        """
        pass

    async def set_message_handler(
        self,
        handler: Callable[[TransportMessage], Awaitable[None]]
    ) -> None:
        """
        Register message handler

        Handler will be called for each received message

        Args:
            handler: Async callable(TransportMessage) -> None
        """
        self._message_handler = handler
        self.logger.info(f"Message handler registered")

    async def set_error_handler(
        self,
        handler: Callable[[TransportError], Awaitable[None]]
    ) -> None:
        """
        Register error handler

        Handler will be called for transport-level errors

        Args:
            handler: Async callable(TransportError) -> None
        """
        self._error_handler = handler
        self.logger.info(f"Error handler registered")

    async def _dispatch_message(self, message: TransportMessage) -> None:
        """
        Dispatch received message to handler

        Internal method called by transport implementation when message received

        Args:
            message: Received message
        """
        if self._message_handler:
            try:
                await self._message_handler(message)
            except Exception as e:
                self.logger.error(f"Error in message handler: {e}")
                # Don't propagate - error handler should be called separately

    async def _dispatch_error(self, error: TransportError) -> None:
        """
        Dispatch transport error to handler

        Internal method called by transport implementation on errors

        Args:
            error: Transport error
        """
        if self._error_handler:
            try:
                await self._error_handler(error)
            except Exception as e:
                self.logger.error(f"Error in error handler: {e}")


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    from unittest.mock import Mock, AsyncMock, patch

    class TestTransportMessage(unittest.TestCase):
        """Test suite for TransportMessage"""

        def test_message_creation(self):
            """Test creating a message"""
            msg = TransportMessage(
                method="test/method",
                params={"key": "value"},
                request_id="123"
            )
            self.assertEqual(msg.method, "test/method")
            self.assertEqual(msg.params, {"key": "value"})
            self.assertEqual(msg.request_id, "123")
            self.assertIsNotNone(msg.timestamp)

        def test_to_jsonrpc_with_id(self):
            """Test converting message with ID to JSON-RPC"""
            msg = TransportMessage(
                method="test/method",
                params={"key": "value"},
                request_id="123"
            )
            jsonrpc = msg.to_jsonrpc()
            self.assertEqual(jsonrpc["jsonrpc"], "2.0")
            self.assertEqual(jsonrpc["method"], "test/method")
            self.assertEqual(jsonrpc["params"], {"key": "value"})
            self.assertEqual(jsonrpc["id"], "123")

        def test_to_jsonrpc_notification(self):
            """Test converting notification (no ID) to JSON-RPC"""
            msg = TransportMessage(method="test/method")
            jsonrpc = msg.to_jsonrpc()
            self.assertEqual(jsonrpc["jsonrpc"], "2.0")
            self.assertEqual(jsonrpc["method"], "test/method")
            self.assertNotIn("id", jsonrpc)
            self.assertNotIn("params", jsonrpc)

        def test_from_jsonrpc_valid(self):
            """Test parsing valid JSON-RPC message"""
            data = {
                "jsonrpc": "2.0",
                "method": "test/method",
                "params": {"key": "value"},
                "id": "123"
            }
            msg = TransportMessage.from_jsonrpc(data)
            self.assertEqual(msg.method, "test/method")
            self.assertEqual(msg.params, {"key": "value"})
            self.assertEqual(msg.request_id, "123")

        def test_from_jsonrpc_missing_method(self):
            """Test parsing JSON-RPC with missing method"""
            data = {"jsonrpc": "2.0", "id": "123"}
            with self.assertRaises(ValueError):
                TransportMessage.from_jsonrpc(data)

        def test_from_jsonrpc_invalid_type(self):
            """Test parsing invalid JSON-RPC (not dict)"""
            with self.assertRaises(ValueError):
                TransportMessage.from_jsonrpc("not a dict")

    class TestTransportError(unittest.TestCase):
        """Test suite for TransportError"""

        def test_error_creation(self):
            """Test creating an error"""
            error = TransportError(
                code=-32600,
                message="Invalid Request",
                request_id="123"
            )
            self.assertEqual(error.code, -32600)
            self.assertEqual(error.message, "Invalid Request")
            self.assertEqual(error.request_id, "123")

        def test_to_jsonrpc_error(self):
            """Test converting error to JSON-RPC format"""
            error = TransportError(
                code=-32600,
                message="Invalid Request",
                data={"details": "extra info"},
                request_id="123"
            )
            jsonrpc = error.to_jsonrpc_error()
            self.assertEqual(jsonrpc["jsonrpc"], "2.0")
            self.assertEqual(jsonrpc["error"]["code"], -32600)
            self.assertEqual(jsonrpc["error"]["message"], "Invalid Request")
            self.assertEqual(jsonrpc["error"]["data"], {"details": "extra info"})
            self.assertEqual(jsonrpc["id"], "123")

    class TestBaseTransport(unittest.TestCase):
        """Test suite for BaseTransport"""

        def test_cannot_instantiate_abstract_class(self):
            """Test that BaseTransport cannot be instantiated"""
            with self.assertRaises(TypeError):
                BaseTransport("test")

        def test_status_property(self):
            """Test status property with mock subclass"""
            class MockTransport(BaseTransport):
                async def start(self): pass
                async def stop(self): pass
                async def send_message(self, msg): pass
                async def send_error(self, error): pass

            transport = MockTransport("test")
            self.assertEqual(transport.status, "stopped")

            transport.is_running = True
            self.assertEqual(transport.status, "running")

            transport.is_connected = True
            self.assertEqual(transport.status, "connected")

        def test_message_handler_registration(self):
            """Test registering message handler"""
            class MockTransport(BaseTransport):
                async def start(self): pass
                async def stop(self): pass
                async def send_message(self, msg): pass
                async def send_error(self, error): pass

            async def test_handler(msg):
                pass

            transport = MockTransport("test")

            async def register():
                await transport.set_message_handler(test_handler)
                self.assertEqual(transport._message_handler, test_handler)

            asyncio.run(register())

    # Run tests
    unittest.main()
