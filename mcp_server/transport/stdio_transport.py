"""
Stdio Transport - JSON-RPC over stdin/stdout

Module: transport.stdio_transport
Date: 2025-11-23
Version: 0.1.0-alpha

CHANGELOG:
[2025-11-23 v0.1.0-alpha] Initial implementation
  - JSON-RPC 2.0 over stdin/stdout
  - Async message reading/writing
  - Line-buffered communication
  - Error handling for JSON parsing
  - Support for requests and notifications

ARCHITECTURE:
StdioTransport implements JSON-RPC 2.0 communication over stdin/stdout.
This is the primary transport for initial deployment and is safe/secure.

Each message is a single line containing JSON-RPC 2.0 format:
- Requests: {"jsonrpc": "2.0", "method": "...", "params": {...}, "id": "..."}
- Responses: {"jsonrpc": "2.0", "result": {...}, "id": "..."}
- Errors: {"jsonrpc": "2.0", "error": {"code": ..., "message": "..."}, "id": "..."}
- Notifications: {"jsonrpc": "2.0", "method": "...", "params": {...}}

SECURITY NOTES:
- JSON parsing is strict (no code execution)
- Message size limits enforced
- All input validated before processing
- No environment variable injection
- No subprocess execution from messages
"""

import asyncio
import json
import logging
import sys
from typing import Optional, Dict, Any
from datetime import datetime

from .base_transport import BaseTransport, TransportMessage, TransportError
from ..core.constants import (
    JSONRPC_VERSION,
    STDIO_BUFFER_SIZE,
    STDIO_ENCODING,
    MAX_REQUEST_SIZE,
    INVALID_REQUEST,
    PARSE_ERROR,
    INTERNAL_ERROR,
)


class StdioTransport(BaseTransport):
    """
    JSON-RPC 2.0 Transport over stdin/stdout

    Communicates with clients via stdin/stdout using JSON-RPC 2.0 protocol.
    Each message is a complete line of JSON.

    This is suitable for:
    - Local AI model integration
    - Subprocess communication
    - Testing and development
    - Initial security-first deployments

    Thread-safe: Uses asyncio for async operations only
    """

    def __init__(self):
        """Initialize Stdio transport"""
        super().__init__("stdio")
        self._read_task: Optional[asyncio.Task] = None
        self._write_queue: asyncio.Queue = asyncio.Queue()
        self._write_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """
        Start the transport

        Creates async tasks for reading from stdin and writing to stdout
        """
        if self.is_running:
            self.logger.warning("Transport already running")
            return

        self.is_running = True
        self.is_connected = True
        self.logger.info("Stdio transport started")

        # Start background tasks for reading and writing
        self._read_task = asyncio.create_task(self._read_loop())
        self._write_task = asyncio.create_task(self._write_loop())

    async def stop(self) -> None:
        """
        Stop the transport

        Cancels reading/writing tasks and closes streams
        """
        if not self.is_running:
            return

        self.is_running = False
        self.is_connected = False

        # Cancel background tasks
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        if self._write_task:
            self._write_task.cancel()
            try:
                await self._write_task
            except asyncio.CancelledError:
                pass

        self.logger.info("Stdio transport stopped")

    async def send_message(self, message: TransportMessage) -> None:
        """
        Send a message via stdout

        Args:
            message: Message to send

        Raises:
            RuntimeError: If transport not running
        """
        if not self.is_running:
            raise RuntimeError("Transport not running")

        await self._write_queue.put(message)

    async def send_error(self, error: TransportError) -> None:
        """
        Send an error response

        Args:
            error: Error to send

        Raises:
            RuntimeError: If transport not running
        """
        if not self.is_running:
            raise RuntimeError("Transport not running")

        # Convert error to message-like object for queue
        await self._write_queue.put(error)

    async def _read_loop(self) -> None:
        """
        Background task for reading from stdin

        Reads lines from stdin, parses as JSON-RPC, dispatches to handlers
        """
        try:
            loop = asyncio.get_event_loop()

            while self.is_running:
                try:
                    # Read line from stdin (non-blocking via executor)
                    line = await loop.run_in_executor(None, self._read_line)

                    if not line:
                        # EOF reached
                        self.logger.info("stdin closed, stopping transport")
                        break

                    # Parse JSON-RPC message
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"JSON parse error: {e}")
                        error = TransportError(
                            code=PARSE_ERROR,
                            message="Parse error",
                            data={"details": str(e)}
                        )
                        await self._dispatch_error(error)
                        continue

                    # Validate JSON-RPC structure
                    if not isinstance(data, dict):
                        error = TransportError(
                            code=INVALID_REQUEST,
                            message="Message must be an object",
                            request_id=data.get("id") if isinstance(data, dict) else None
                        )
                        await self._dispatch_error(error)
                        continue

                    # Validate required fields
                    if "jsonrpc" not in data or data["jsonrpc"] != JSONRPC_VERSION:
                        error = TransportError(
                            code=INVALID_REQUEST,
                            message=f"Invalid jsonrpc version, expected {JSONRPC_VERSION}",
                            request_id=data.get("id")
                        )
                        await self._dispatch_error(error)
                        continue

                    if "method" not in data:
                        error = TransportError(
                            code=INVALID_REQUEST,
                            message="Missing 'method' field",
                            request_id=data.get("id")
                        )
                        await self._dispatch_error(error)
                        continue

                    # Parse message
                    try:
                        message = TransportMessage.from_jsonrpc(data)
                        await self._dispatch_message(message)
                    except ValueError as e:
                        error = TransportError(
                            code=INVALID_REQUEST,
                            message=str(e),
                            request_id=data.get("id")
                        )
                        await self._dispatch_error(error)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"Error in read loop: {e}")
                    error = TransportError(
                        code=INTERNAL_ERROR,
                        message="Internal server error"
                    )
                    await self._dispatch_error(error)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Fatal error in read loop: {e}")
            self.is_running = False

    async def _write_loop(self) -> None:
        """
        Background task for writing to stdout

        Writes messages/errors from queue to stdout as JSON-RPC
        """
        try:
            while self.is_running:
                try:
                    # Get next message with timeout
                    item = await asyncio.wait_for(
                        self._write_queue.get(),
                        timeout=1.0
                    )

                    if isinstance(item, TransportMessage):
                        jsonrpc = item.to_jsonrpc()
                    elif isinstance(item, TransportError):
                        jsonrpc = item.to_jsonrpc_error()
                    else:
                        self.logger.error(f"Unknown item type: {type(item)}")
                        continue

                    # Serialize and write
                    try:
                        line = json.dumps(jsonrpc, separators=(",", ":"))
                        await self._write_line(line)
                    except (TypeError, ValueError) as e:
                        self.logger.error(f"JSON serialization error: {e}")

                except asyncio.TimeoutError:
                    # Queue timeout is normal - just loop again
                    continue
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"Error in write loop: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Fatal error in write loop: {e}")
            self.is_running = False

    def _read_line(self) -> Optional[str]:
        """
        Read a line from stdin (blocking, called in executor)

        Returns:
            str: Line read (without newline), or None on EOF

        Note:
            This is a blocking operation run in thread pool executor
        """
        try:
            line = sys.stdin.readline()
            if not line:
                return None

            # Strip newline
            line = line.rstrip("\n\r")

            # Check size limit
            if len(line) > MAX_REQUEST_SIZE:
                self.logger.warning(f"Message exceeds size limit: {len(line)}")
                return None

            return line
        except Exception as e:
            self.logger.error(f"Error reading from stdin: {e}")
            return None

    async def _write_line(self, line: str) -> None:
        """
        Write a line to stdout (non-blocking)

        Args:
            line: Line to write (without newline)

        Note:
            This is async but actual I/O is sync (stdout is usually buffered)
        """
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._write_line_sync, line)
        except Exception as e:
            self.logger.error(f"Error writing to stdout: {e}")

    @staticmethod
    def _write_line_sync(line: str) -> None:
        """
        Write a line to stdout (blocking, called in executor)

        Args:
            line: Line to write (without newline)
        """
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    from unittest.mock import Mock, patch, MagicMock, AsyncMock
    from io import StringIO

    class TestStdioTransport(unittest.TestCase):
        """Test suite for StdioTransport"""

        def setUp(self):
            """Setup before each test"""
            self.transport = StdioTransport()

        def test_initialization(self):
            """Test transport initialization"""
            self.assertEqual(self.transport.name, "stdio")
            self.assertFalse(self.transport.is_running)
            self.assertFalse(self.transport.is_connected)
            self.assertEqual(self.transport.status, "stopped")

        def test_status_transitions(self):
            """Test status property transitions"""
            self.assertEqual(self.transport.status, "stopped")

            self.transport.is_running = True
            self.assertEqual(self.transport.status, "running")

            self.transport.is_connected = True
            self.assertEqual(self.transport.status, "connected")

            self.transport.is_running = False
            self.assertEqual(self.transport.status, "stopped")

        def test_send_message_not_running(self):
            """Test sending message when not running raises error"""
            async def test():
                msg = TransportMessage(method="test/method")
                with self.assertRaises(RuntimeError):
                    await self.transport.send_message(msg)

            asyncio.run(test())

        def test_send_error_not_running(self):
            """Test sending error when not running raises error"""
            async def test():
                error = TransportError(code=-32600, message="Invalid Request")
                with self.assertRaises(RuntimeError):
                    await self.transport.send_error(error)

            asyncio.run(test())

        def test_send_message_while_running(self):
            """Test sending message when running succeeds"""
            async def test():
                self.transport.is_running = True
                msg = TransportMessage(method="test/method")
                # Should not raise
                await self.transport.send_message(msg)
                # Message should be in queue
                self.assertEqual(self.transport._write_queue.qsize(), 1)

            asyncio.run(test())

        def test_stop_when_not_running(self):
            """Test stopping when not running is safe"""
            async def test():
                await self.transport.stop()
                self.assertFalse(self.transport.is_running)

            asyncio.run(test())

        def test_read_line_max_size(self):
            """Test read_line respects max size"""
            with patch("builtins.open", create=True):
                # Line exceeding max size
                with patch("sys.stdin") as mock_stdin:
                    mock_stdin.readline.return_value = "x" * (MAX_REQUEST_SIZE + 1) + "\n"
                    result = self.transport._read_line()
                    self.assertIsNone(result)

        def test_read_line_eof(self):
            """Test read_line handles EOF"""
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.readline.return_value = ""
                result = self.transport._read_line()
                self.assertIsNone(result)

        def test_read_line_strips_newlines(self):
            """Test read_line strips newlines"""
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.readline.return_value = "test message\n"
                result = self.transport._read_line()
                self.assertEqual(result, "test message")

                mock_stdin.readline.return_value = "test message\r\n"
                result = self.transport._read_line()
                self.assertEqual(result, "test message")

    class TestStdioIntegration(unittest.TestCase):
        """Integration tests for StdioTransport"""

        def test_message_roundtrip(self):
            """Test message can be serialized and deserialized"""
            original = TransportMessage(
                method="test/method",
                params={"key": "value"},
                request_id="123"
            )

            # Serialize
            jsonrpc = original.to_jsonrpc()
            json_str = json.dumps(jsonrpc)

            # Deserialize
            parsed = json.loads(json_str)
            restored = TransportMessage.from_jsonrpc(parsed)

            self.assertEqual(restored.method, original.method)
            self.assertEqual(restored.params, original.params)
            self.assertEqual(restored.request_id, original.request_id)

    # Run tests
    unittest.main()
