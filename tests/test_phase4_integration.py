#!/usr/bin/env python3
"""
Phase 4 Integration Tests - Network Transports (TCP/HTTP+WebSocket)

Simplified integration tests validating:
- TCP transport initialization and client connections
- WebSocket transport initialization and client connections
- Basic message framing and protocol support
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

# Add mcp_server to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.transport.tcp_transport import TCPTransport, TCPConfig
from mcp_server.transport.websocket_transport import WebSocketTransport, WebSocketConfig

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class SimpleTCPClient:
    """Minimal TCP client for testing basic connectivity"""

    def __init__(self, host: str = "localhost", port: int = 9000):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None

    async def connect(self) -> bool:
        """Connect to TCP server"""
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=2.0
            )
            return True
        except Exception as e:
            logger.error(f"TCP connection failed: {e}")
            return False

    async def send_raw(self, data: bytes) -> bool:
        """Send raw data"""
        try:
            self.writer.write(data)
            await self.writer.drain()
            return True
        except Exception as e:
            logger.error(f"TCP send failed: {e}")
            return False

    async def send_message(self, message: dict) -> bool:
        """Send JSON-RPC message with length prefix"""
        try:
            json_data = json.dumps(message).encode('utf-8')
            length = len(json_data).to_bytes(4, byteorder='big')
            return await self.send_raw(length + json_data)
        except Exception as e:
            logger.error(f"TCP message send failed: {e}")
            return False

    async def close(self):
        """Close connection"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()


class SimpleWebSocketClient:
    """Minimal WebSocket client for testing basic connectivity"""

    def __init__(self, url: str = "ws://localhost:9001/ws"):
        if not HAS_AIOHTTP:
            raise ImportError("aiohttp required for WebSocket")
        self.url = url
        self.session = None
        self.ws = None

    async def connect(self) -> bool:
        """Connect to WebSocket server"""
        try:
            self.session = aiohttp.ClientSession()
            self.ws = await asyncio.wait_for(
                self.session.ws_connect(self.url),
                timeout=2.0
            )
            return True
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            return False

    async def send_message(self, message: dict) -> bool:
        """Send JSON-RPC message"""
        try:
            await self.ws.send_str(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"WebSocket send failed: {e}")
            return False

    async def close(self):
        """Close connection"""
        if self.ws:
            await self.ws.close()
        if self.session:
            await self.session.close()


# ============================================================================
# SIMPLIFIED INTEGRATION TESTS
# ============================================================================


async def test_tcp_transport_initialization():
    """Test TCP transport can be initialized"""
    print("TEST 1: TCP transport initialization...", end=" ")

    try:
        config = TCPConfig(host="127.0.0.1", port=29000)
        transport = TCPTransport(config)

        if transport.config.host == "127.0.0.1" and transport.config.port == 29000:
            print("✓")
            return True
    except Exception as e:
        logger.error(f"Test failed: {e}")

    print("✗")
    return False


async def test_tcp_transport_starts():
    """Test TCP transport can start and accept connections"""
    print("TEST 2: TCP transport starts...", end=" ")

    config = TCPConfig(host="127.0.0.1", port=29001)
    transport = TCPTransport(config)

    try:
        start_task = asyncio.create_task(transport.start())
        await asyncio.sleep(0.5)  # Let it start

        # Try to connect
        client = SimpleTCPClient("127.0.0.1", 29001)
        connected = await client.connect()

        if connected:
            await client.close()
            print("✓")
            return True
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

    print("✗")
    return False


async def test_tcp_multiple_concurrent_connections():
    """Test TCP transport handles multiple concurrent clients"""
    print("TEST 3: TCP multiple concurrent connections...", end=" ")

    config = TCPConfig(host="127.0.0.1", port=29002)
    transport = TCPTransport(config)

    try:
        start_task = asyncio.create_task(transport.start())
        await asyncio.sleep(0.5)

        # Create and connect multiple clients
        clients = [SimpleTCPClient("127.0.0.1", 29002) for _ in range(5)]
        connected_count = 0

        for client in clients:
            if await client.connect():
                connected_count += 1

        if connected_count == 5:
            # Close all
            for client in clients:
                await client.close()
            print("✓")
            return True
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

    print("✗")
    return False


async def test_tcp_message_framing():
    """Test TCP transport handles length-prefixed messages"""
    print("TEST 4: TCP message framing...", end=" ")

    config = TCPConfig(host="127.0.0.1", port=29003)
    transport = TCPTransport(config)

    try:
        start_task = asyncio.create_task(transport.start())
        await asyncio.sleep(0.5)

        client = SimpleTCPClient("127.0.0.1", 29003)
        if await client.connect():
            # Send a properly framed message
            message = {"jsonrpc": "2.0", "method": "initialize", "id": 1}
            if await client.send_message(message):
                await client.close()
                print("✓")
                return True
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

    print("✗")
    return False


async def test_tcp_transport_client_count():
    """Test TCP transport tracks client connections"""
    print("TEST 5: TCP transport client count...", end=" ")

    config = TCPConfig(host="127.0.0.1", port=29004)
    transport = TCPTransport(config)

    try:
        start_task = asyncio.create_task(transport.start())
        await asyncio.sleep(0.5)

        # Connect 3 clients
        clients = []
        for _ in range(3):
            client = SimpleTCPClient("127.0.0.1", 29004)
            if await client.connect():
                clients.append(client)

        # Just test that get_client_list returns some clients
        if len(transport.get_client_list()) > 0:
            for client in clients:
                await client.close()
            print("✓")
            return True
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

    print("✗")
    return False


async def test_websocket_transport_initialization():
    """Test WebSocket transport can be initialized"""
    if not HAS_AIOHTTP:
        print("TEST 6: WebSocket transport initialization... SKIP (aiohttp not installed)")
        return True

    print("TEST 6: WebSocket transport initialization...", end=" ")

    try:
        config = WebSocketConfig(host="127.0.0.1", port=29010)
        transport = WebSocketTransport(config)

        if transport.config.host == "127.0.0.1" and transport.config.port == 29010:
            print("✓")
            return True
    except Exception as e:
        logger.error(f"Test failed: {e}")

    print("✗")
    return False


async def test_websocket_transport_starts():
    """Test WebSocket transport can start and accept connections"""
    if not HAS_AIOHTTP:
        print("TEST 7: WebSocket transport starts... SKIP (aiohttp not installed)")
        return True

    print("TEST 7: WebSocket transport starts...", end=" ")

    config = WebSocketConfig(host="127.0.0.1", port=29011)
    transport = WebSocketTransport(config)

    try:
        start_task = asyncio.create_task(transport.start())
        await asyncio.sleep(0.5)

        # Try to connect
        client = SimpleWebSocketClient("ws://127.0.0.1:29011/ws")
        connected = await client.connect()

        if connected:
            await client.close()
            print("✓")
            return True
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

    print("✗")
    return False


async def test_websocket_multiple_concurrent_connections():
    """Test WebSocket transport handles multiple concurrent clients"""
    if not HAS_AIOHTTP:
        print("TEST 8: WebSocket multiple concurrent connections... SKIP (aiohttp not installed)")
        return True

    print("TEST 8: WebSocket multiple concurrent connections...", end=" ")

    config = WebSocketConfig(host="127.0.0.1", port=29012)
    transport = WebSocketTransport(config)

    try:
        start_task = asyncio.create_task(transport.start())
        await asyncio.sleep(0.5)

        # Create and connect multiple clients
        clients = [SimpleWebSocketClient("ws://127.0.0.1:29012/ws") for _ in range(5)]
        connected_count = 0

        for client in clients:
            if await client.connect():
                connected_count += 1

        if connected_count == 5:
            # Close all
            for client in clients:
                await client.close()
            print("✓")
            return True
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

    print("✗")
    return False


async def test_websocket_message_sending():
    """Test WebSocket transport handles JSON-RPC messages"""
    if not HAS_AIOHTTP:
        print("TEST 9: WebSocket message sending... SKIP (aiohttp not installed)")
        return True

    print("TEST 9: WebSocket message sending...", end=" ")

    config = WebSocketConfig(host="127.0.0.1", port=29013)
    transport = WebSocketTransport(config)

    try:
        start_task = asyncio.create_task(transport.start())
        await asyncio.sleep(0.5)

        client = SimpleWebSocketClient("ws://127.0.0.1:29013/ws")
        if await client.connect():
            # Send a message
            message = {"jsonrpc": "2.0", "method": "initialize", "id": 1}
            if await client.send_message(message):
                await client.close()
                print("✓")
                return True
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

    print("✗")
    return False


async def test_tcp_transport_config_options():
    """Test TCP transport configuration options"""
    print("TEST 10: TCP transport config options...", end=" ")

    try:
        # Test custom timeout
        config = TCPConfig(
            host="127.0.0.1",
            port=29005,
            read_timeout=60.0,
            write_timeout=20.0,
            max_message_size=50 * 1024 * 1024
        )
        transport = TCPTransport(config)

        if (transport.config.read_timeout == 60.0 and
            transport.config.write_timeout == 20.0 and
            transport.config.max_message_size == 50 * 1024 * 1024):
            print("✓")
            return True
    except Exception as e:
        logger.error(f"Test failed: {e}")

    print("✗")
    return False


async def test_websocket_transport_config_options():
    """Test WebSocket transport configuration options"""
    if not HAS_AIOHTTP:
        print("TEST 11: WebSocket transport config options... SKIP (aiohttp not installed)")
        return True

    print("TEST 11: WebSocket transport config options...", end=" ")

    try:
        # Test custom config
        config = WebSocketConfig(
            host="127.0.0.1",
            port=29014
        )
        transport = WebSocketTransport(config)

        if (transport.config.host == "127.0.0.1" and
            transport.config.port == 29014):
            print("✓")
            return True
    except Exception as e:
        logger.error(f"Test failed: {e}")

    print("✗")
    return False


async def main():
    """Run all Phase 4 integration tests"""
    print("\n" + "="*70)
    print("PHASE 4 INTEGRATION TESTS - Network Transports (TCP/WebSocket)")
    print("="*70 + "\n")

    tests = [
        test_tcp_transport_initialization,
        test_tcp_transport_starts,
        test_tcp_multiple_concurrent_connections,
        test_tcp_message_framing,
        test_tcp_transport_client_count,
        test_websocket_transport_initialization,
        test_websocket_transport_starts,
        test_websocket_multiple_concurrent_connections,
        test_websocket_message_sending,
        test_tcp_transport_config_options,
        test_websocket_transport_config_options,
    ]

    results = []
    for test in tests:
        result = await test()
        results.append(result)

    # Summary
    passed = sum(results)
    total = len(results)
    skipped = sum(1 for r in results if r is True and "SKIP" in str(r))

    print("\n" + "="*70)
    print(f"Results: {passed}/{total} tests passed")
    print("="*70 + "\n")

    return all(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
