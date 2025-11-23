"""
Integration Tests - Phase 1 Acceptance Tests

Module: tests.test_integration_phase1
Date: 2025-11-23
Version: 0.1.0-alpha

CHANGELOG:
[2025-11-23 v0.1.0-alpha] Initial integration tests
  - Scenario 1: Server startup
  - Scenario 2: Client initialization
  - Scenario 3: Capabilities exposure
  - Scenario 4: Health check
  - Scenario 5: Shutdown

These tests validate the UseCase 1 acceptance criteria from ARCHITECTURE.md

Gherkin Scenarios Tested:
1. Démarrage du serveur MCP
2. Client se connecte au serveur
3. Serveur expose les capabilities
4. Health check du serveur

SECURITY NOTES:
- Phase 1 tests don't validate authentication (no auth yet)
- Validate protocol compliance
- Validate error handling
- Validate message format
"""

import unittest
import asyncio
import json
import logging
from typing import Optional, Dict, Any
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server.core.mcp_server import MCPServer
from mcp_server.transport.base_transport import TransportMessage, TransportError
from mcp_server.transport.stdio_transport import StdioTransport
from mcp_server.security.client_context import ClientContext
from mcp_server.core.constants import (
    MCP_PROTOCOL_VERSION,
    METHOD_INITIALIZE,
    METHOD_SHUTDOWN,
    JSONRPC_VERSION,
    DEFAULT_CAPABILITIES,
)


class TestMCPServerPhase1(unittest.TestCase):
    """
    Integration tests for Phase 1 - Server Initialization

    Tests cover:
    - Server startup and shutdown
    - Client initialization
    - Capabilities exposure
    - Protocol compliance
    - Error handling
    """

    def setUp(self):
        """Setup before each test"""
        self.server = MCPServer()
        logging.basicConfig(level=logging.INFO)

    def tearDown(self):
        """Cleanup after each test"""
        if self.server.is_running:
            asyncio.run(self.server.stop())

    # ========================================================================
    # Scenario 1 : Démarrage du serveur MCP
    # ========================================================================

    def test_scenario_1_server_startup(self):
        """
        Scenario: Démarrage du serveur MCP
        Given: le serveur MCP n'est pas en cours d'exécution
        When: je démarre le serveur MCP sur le port 8080
        Then: le serveur doit écouter sur le port 8080
              Et aucune erreur de démarrage ne doit être enregistrée
              Et le serveur doit être prêt à accepter les connexions
        """
        async def test():
            # Given: Server not running
            self.assertFalse(self.server.is_running)

            # When: Start server
            transport = StdioTransport()
            self.server.set_transport(transport)
            await self.server.start()

            # Then: Server should be running
            self.assertTrue(self.server.is_running)
            self.assertTrue(self.server.is_listening)

            # And: Status should be available
            status = self.server.get_status()
            self.assertTrue(status.is_running)
            self.assertTrue(status.is_listening)

            # And: Server info should be correct
            self.assertEqual(status.name, self.server.server_name)
            self.assertEqual(status.protocol_version, MCP_PROTOCOL_VERSION)

        asyncio.run(test())

    def test_scenario_1_server_shutdown(self):
        """Test clean server shutdown"""
        async def test():
            transport = StdioTransport()
            self.server.set_transport(transport)
            await self.server.start()
            self.assertTrue(self.server.is_running)

            # Stop server
            await self.server.stop()
            self.assertFalse(self.server.is_running)

        asyncio.run(test())

    # ========================================================================
    # Scenario 2 : Client se connecte au serveur
    # ========================================================================

    def test_scenario_2_client_initialization(self):
        """
        Scenario: Client se connecte au serveur
        Given: le serveur MCP fonctionne
        When: un client MCP envoie une requête initialize
        Then: la connexion doit être établie avec succès
              Et le client doit recevoir la version du protocole
              Et le client doit recevoir l'ID du serveur
        """
        async def test():
            # Given: Server running
            transport = StdioTransport()
            self.server.set_transport(transport)
            await self.server.start()

            # When: Client sends initialize request
            client_context = ClientContext(client_info={"name": "test-client", "version": "1.0"})
            init_message = TransportMessage(
                method=METHOD_INITIALIZE,
                params={
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0"
                    }
                },
                request_id="init-1"
            )

            response = await self.server.protocol_handler.handle_message(init_message, client_context)

            # Then: Response should be successful
            self.assertIsNotNone(response)
            self.assertEqual(response.request_id, "init-1")

            # And: Should contain protocol version
            result = response.params.get("result", {})
            self.assertEqual(result.get("protocolVersion"), MCP_PROTOCOL_VERSION)

            # And: Should contain server info
            server_info = result.get("serverInfo", {})
            self.assertIn("name", server_info)
            self.assertIn("version", server_info)

        asyncio.run(test())

    # ========================================================================
    # Scenario 3 : Serveur expose les capabilities
    # ========================================================================

    def test_scenario_3_capabilities_exposure(self):
        """
        Scenario: Serveur expose les capabilities
        Given: un client est connecté au serveur MCP
        When: le client demande les capabilities du serveur
        Then: le serveur retourne une liste de tools disponibles
              Et chaque tool contient (nom, description, paramètres)
              Et la réponse est conforme au standard MCP
        """
        async def test():
            # Given: Server running and client initialized
            transport = StdioTransport()
            self.server.set_transport(transport)
            await self.server.start()

            client_context = ClientContext()
            init_message = TransportMessage(
                method=METHOD_INITIALIZE,
                params={"clientInfo": {}},
                request_id="1"
            )
            await self.server.protocol_handler.handle_message(init_message, client_context)

            # When: Get initialize response which contains capabilities
            status = self.server.get_status()

            # Then: Capabilities should be present
            capabilities = status.capabilities
            self.assertIsInstance(capabilities, dict)

            # And: Should follow MCP structure
            self.assertIn("tools", capabilities)

        asyncio.run(test())

    # ========================================================================
    # Scenario 4 : Health check du serveur
    # ========================================================================

    def test_scenario_4_health_check(self):
        """
        Scenario: Health check du serveur
        Given: le serveur MCP est en cours d'exécution
        When: je demande le statut de santé du serveur
        Then: le serveur répond avec un statut OK
              Et la réponse contient le timestamp
              Et la réponse contient la version du serveur
        """
        async def test():
            # Given: Server running
            transport = StdioTransport()
            self.server.set_transport(transport)
            await self.server.start()

            # When: Request status
            status = self.server.get_status()

            # Then: Status should be OK
            self.assertTrue(status.is_running)
            self.assertTrue(status.is_listening)

            # And: Should contain timestamp
            self.assertIsNotNone(status.timestamp)

            # And: Should contain version
            self.assertEqual(status.version, self.server.server_version)
            self.assertEqual(status.protocol_version, MCP_PROTOCOL_VERSION)

        asyncio.run(test())

    # ========================================================================
    # Additional Tests - Protocol Compliance
    # ========================================================================

    def test_json_rpc_compliance_valid_message(self):
        """Test JSON-RPC message parsing"""
        async def test():
            client_context = ClientContext()

            # Valid JSON-RPC message
            jsonrpc_dict = {
                "jsonrpc": "2.0",
                "method": METHOD_INITIALIZE,
                "params": {"clientInfo": {}},
                "id": "1"
            }

            message = TransportMessage.from_jsonrpc(jsonrpc_dict)
            self.assertEqual(message.method, METHOD_INITIALIZE)
            self.assertEqual(message.request_id, "1")

        asyncio.run(test())

    def test_json_rpc_message_creation(self):
        """Test JSON-RPC message parsing"""
        # Valid message
        data = {
            "jsonrpc": "2.0",
            "method": "test/method",
            "params": {"key": "value"},
            "id": "1"
        }
        msg = TransportMessage.from_jsonrpc(data)
        self.assertEqual(msg.method, "test/method")
        self.assertEqual(msg.params, {"key": "value"})
        self.assertEqual(msg.request_id, "1")

    def test_error_response_format(self):
        """Test error response follows JSON-RPC format"""
        error = TransportError(
            code=-32600,
            message="Invalid Request",
            request_id="1"
        )

        jsonrpc_error = error.to_jsonrpc_error()

        # Should have JSON-RPC structure
        self.assertEqual(jsonrpc_error["jsonrpc"], "2.0")
        self.assertIn("error", jsonrpc_error)
        self.assertEqual(jsonrpc_error["error"]["code"], -32600)
        self.assertEqual(jsonrpc_error["error"]["message"], "Invalid Request")
        self.assertEqual(jsonrpc_error["id"], "1")

    def test_message_requires_initialize_first(self):
        """Test that methods require initialize first"""
        async def test():
            transport = StdioTransport()
            self.server.set_transport(transport)
            await self.server.start()

            client_context = ClientContext()

            # Try to call method before initialize
            unknown_message = TransportMessage(
                method="tools/list",
                request_id="1"
            )

            response = await self.server.protocol_handler.handle_message(
                unknown_message,
                client_context
            )

            # Should get error
            self.assertIsInstance(response, TransportError)

        asyncio.run(test())

    def test_shutdown_sequence(self):
        """Test proper shutdown sequence"""
        async def test():
            transport = StdioTransport()
            self.server.set_transport(transport)
            await self.server.start()

            client_context = ClientContext()

            # Initialize
            init_msg = TransportMessage(
                method=METHOD_INITIALIZE,
                params={"clientInfo": {}},
                request_id="1"
            )
            await self.server.protocol_handler.handle_message(init_msg, client_context)

            # Shutdown
            shutdown_msg = TransportMessage(
                method=METHOD_SHUTDOWN,
                request_id="2"
            )
            response = await self.server.protocol_handler.handle_message(
                shutdown_msg,
                client_context
            )

            # Should succeed
            self.assertIsNotNone(response)
            self.assertEqual(response.method, METHOD_SHUTDOWN)

        asyncio.run(test())

    def test_server_status_transitions(self):
        """Test server status during lifecycle"""
        async def test():
            # Before start
            self.assertFalse(self.server.is_running)
            status = self.server.get_status()
            self.assertFalse(status.is_running)

            # After start
            transport = StdioTransport()
            self.server.set_transport(transport)
            await self.server.start()

            self.assertTrue(self.server.is_running)
            status = self.server.get_status()
            self.assertTrue(status.is_running)

            # After stop
            await self.server.stop()
            self.assertFalse(self.server.is_running)

        asyncio.run(test())


class TestAcceptanceCriteria(unittest.TestCase):
    """
    Direct tests against acceptance criteria from ARCHITECTURE.md
    """

    def test_ac1_server_starts_without_errors(self):
        """AC1: Serveur démarre sans erreurs"""
        async def test():
            server = MCPServer()
            transport = StdioTransport()
            server.set_transport(transport)

            try:
                await server.start()
                self.assertTrue(server.is_running)
            except Exception as e:
                self.fail(f"Server failed to start: {e}")
            finally:
                await server.stop()

        asyncio.run(test())

    def test_ac2_client_receives_protocol_version(self):
        """AC2: Client reçoit la version du protocole"""
        async def test():
            server = MCPServer()
            transport = StdioTransport()
            server.set_transport(transport)
            await server.start()

            client = ClientContext()
            message = TransportMessage(
                method=METHOD_INITIALIZE,
                params={"clientInfo": {}},
                request_id="1"
            )

            response = await server.protocol_handler.handle_message(message, client)
            result = response.params.get("result", {})

            self.assertEqual(
                result.get("protocolVersion"),
                MCP_PROTOCOL_VERSION
            )

            await server.stop()

        asyncio.run(test())

    def test_ac3_capabilities_conform_to_spec(self):
        """AC3: Capabilities conformes au standard MCP"""
        async def test():
            server = MCPServer()
            status = server.get_status()

            # Should have required structure
            self.assertIn("tools", status.capabilities)

            # Should be dict (can be extended)
            self.assertIsInstance(status.capabilities, dict)

        asyncio.run(test())

    def test_ac4_health_check_contains_timestamp(self):
        """AC4: Health check contient le timestamp"""
        async def test():
            server = MCPServer()
            transport = StdioTransport()
            server.set_transport(transport)
            await server.start()

            status = server.get_status()

            # Should have timestamp
            self.assertIsNotNone(status.timestamp)

            # Should be valid datetime
            from datetime import datetime
            self.assertIsInstance(status.timestamp, datetime)

            await server.stop()

        asyncio.run(test())


if __name__ == "__main__":
    unittest.main(verbosity=2)
