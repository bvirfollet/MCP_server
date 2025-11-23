"""
Integration Tests - Phase 2: Tools & Permissions

Module: tests.test_integration_phase2
Date: 2025-11-23
Version: 0.2.0-alpha

DESCRIPTION:
Integration tests for Phase 2 functionality:
- Tool registration and listing
- Permission management
- Tool execution with authorization
- Error handling and validation
- Audit logging

These tests verify that all Phase 2 components work together correctly.
"""

import unittest
import asyncio
import logging
from typing import Dict, Any

# Phase 2 components
from mcp_server.core.mcp_server import MCPServer
from mcp_server.security.client_context import ClientContext
from mcp_server.security.permission import Permission, PermissionType
from mcp_server.tools.tool import FunctionTool
from mcp_server.resources.execution_manager import (
    ExecutionError,
    ValidationError,
)
from mcp_server.security.permission_manager import PermissionDeniedError

# Configure logging for tests
logging.basicConfig(
    level=logging.WARNING,
    format="%(name)s - %(levelname)s - %(message)s"
)


class TestPhase2ToolRegistration(unittest.TestCase):
    """Test tool registration and discovery"""

    def setUp(self):
        """Setup before each test"""
        self.server = MCPServer()
        self.client = ClientContext()

    def test_register_tool_with_decorator(self):
        """Test registering a tool using @server.tool() decorator"""

        @self.server.tool(
            name="test_tool",
            description="A test tool",
            input_schema={
                "arg1": {"type": "string"},
                "arg2": {"type": "integer"},
            },
        )
        async def test_tool(client, params):
            return {"result": "ok"}

        # Verify tool is registered
        self.assertTrue(self.server.tool_manager.exists("test_tool"))
        tool = self.server.tool_manager.get("test_tool")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "test_tool")

    def test_register_multiple_tools(self):
        """Test registering multiple tools"""

        @self.server.tool(name="tool1", description="Tool 1")
        async def tool1(client, params):
            return {}

        @self.server.tool(name="tool2", description="Tool 2")
        async def tool2(client, params):
            return {}

        @self.server.tool(name="tool3", description="Tool 3")
        async def tool3(client, params):
            return {}

        self.assertEqual(self.server.tool_manager.count(), 3)

    def test_tools_list_handler(self):
        """Test tools/list handler returns correct format"""

        @self.server.tool(
            name="example_tool",
            description="An example tool",
            input_schema={"param": {"type": "string"}},
        )
        async def example_tool(client, params):
            return {"result": params.get("param")}

        async def run_test():
            result = await self.server._handle_tools_list(
                self.client, {}
            )

            self.assertIn("tools", result)
            self.assertEqual(len(result["tools"]), 1)

            tool_info = result["tools"][0]
            self.assertEqual(tool_info["name"], "example_tool")
            self.assertEqual(tool_info["description"], "An example tool")
            self.assertIn("inputSchema", tool_info)

        asyncio.run(run_test())


class TestPhase2PermissionManagement(unittest.TestCase):
    """Test permission management and authorization"""

    def setUp(self):
        """Setup before each test"""
        self.server = MCPServer()
        self.client = ClientContext()

    def test_client_default_permissions(self):
        """Test client gets default permissions on initialization"""
        self.server.permission_manager.initialize_client(
            self.client.client_id
        )

        perms = self.server.permission_manager.get_client_permissions(
            self.client.client_id
        )
        self.assertGreater(len(perms), 0)

    def test_grant_permission(self):
        """Test granting permission to client"""
        self.server.permission_manager.initialize_client(
            self.client.client_id, []
        )

        perm = Permission(PermissionType.FILE_READ, "/app/data/*")
        self.server.permission_manager.grant_permission(
            self.client.client_id, perm
        )

        self.assertTrue(
            self.server.permission_manager.has_permission(
                self.client.client_id, perm
            )
        )

    def test_revoke_permission(self):
        """Test revoking permission from client"""
        perm = Permission(PermissionType.FILE_READ, "/test/*")
        self.server.permission_manager.initialize_client(
            self.client.client_id, [perm]
        )

        self.assertTrue(
            self.server.permission_manager.has_permission(
                self.client.client_id, perm
            )
        )

        self.server.permission_manager.revoke_permission(
            self.client.client_id, PermissionType.FILE_READ
        )

        self.assertFalse(
            self.server.permission_manager.has_permission(
                self.client.client_id, perm
            )
        )


class TestPhase2ToolExecution(unittest.TestCase):
    """Test tool execution with permissions"""

    def setUp(self):
        """Setup before each test"""
        self.server = MCPServer()
        self.client = ClientContext()

    def test_execute_tool_with_permission(self):
        """Test executing a tool when client has permission"""

        # Register tool with permission requirement
        @self.server.tool(
            name="read_file",
            description="Read a file",
            input_schema={"path": {"type": "string"}},
            permissions=[
                Permission(PermissionType.FILE_READ, "/app/data/*")
            ],
        )
        async def read_file(client, params):
            return {"content": f"File content from {params['path']}"}

        # Grant permission to client
        self.server.permission_manager.initialize_client(
            self.client.client_id,
            [Permission(PermissionType.FILE_READ, "/app/data/*")],
        )

        async def run_test():
            result = await self.server._handle_tools_call(
                self.client,
                {
                    "name": "read_file",
                    "arguments": {"path": "/app/data/test.txt"},
                },
            )

            self.assertIn("content", result)
            self.assertFalse(result["isError"])

        asyncio.run(run_test())

    def test_execute_tool_without_permission(self):
        """Test executing a tool without permission fails"""

        # Register tool with permission requirement
        @self.server.tool(
            name="write_file",
            description="Write a file",
            permissions=[Permission(PermissionType.FILE_WRITE)],
        )
        async def write_file(client, params):
            return {"status": "written"}

        # Initialize client with NO permissions
        self.server.permission_manager.initialize_client(
            self.client.client_id, []
        )

        async def run_test():
            with self.assertRaises(PermissionDeniedError):
                await self.server._handle_tools_call(
                    self.client,
                    {"name": "write_file", "arguments": {}},
                )

        asyncio.run(run_test())

    def test_execute_tool_with_invalid_params(self):
        """Test executing a tool with invalid parameters"""
        from mcp_server.tools.tool import InputSchema

        # Create tool with proper schema including required fields
        async def calculate_func(client, params):
            return {"result": params["x"] + params["y"]}

        tool = FunctionTool(
            name="calculate",
            description="Calculate something",
            func=calculate_func,
            input_schema={
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
        )
        # Set required fields
        tool.input_schema.required = ["x", "y"]
        self.server.tool_manager.register(tool)

        self.server.permission_manager.initialize_client(
            self.client.client_id
        )

        async def run_test():
            # Missing required parameter
            with self.assertRaises(ValidationError):
                tool = self.server.tool_manager.get("calculate")
                await self.server.execution_manager.execute_tool(
                    tool, self.client, {"x": 5}  # Missing 'y'
                )

            # Wrong type
            with self.assertRaises(ValidationError):
                tool = self.server.tool_manager.get("calculate")
                await self.server.execution_manager.execute_tool(
                    tool, self.client, {"x": "not_int", "y": 10}
                )

        asyncio.run(run_test())

    def test_execute_tool_with_timeout(self):
        """Test tool execution timeout"""

        @self.server.tool(
            name="slow_tool",
            description="A slow tool",
            timeout=1,  # 1 second timeout
        )
        async def slow_tool(client, params):
            await asyncio.sleep(5)  # Sleep longer than timeout
            return {"result": "done"}

        self.server.permission_manager.initialize_client(
            self.client.client_id
        )

        async def run_test():
            with self.assertRaises(ExecutionError) as ctx:
                await self.server._handle_tools_call(
                    self.client,
                    {"name": "slow_tool", "arguments": {}},
                )
            self.assertIn("timeout", str(ctx.exception).lower())

        asyncio.run(run_test())


class TestPhase2AuditLogging(unittest.TestCase):
    """Test audit logging of tool executions"""

    def setUp(self):
        """Setup before each test"""
        self.server = MCPServer()
        self.client = ClientContext()

    def test_execution_logged(self):
        """Test that tool execution is logged"""

        @self.server.tool(
            name="logged_tool",
            description="A tool that gets logged",
        )
        async def logged_tool(client, params):
            return {"status": "ok"}

        self.server.permission_manager.initialize_client(
            self.client.client_id
        )

        async def run_test():
            # Execute tool
            await self.server._handle_tools_call(
                self.client,
                {"name": "logged_tool", "arguments": {}},
            )

            # Check execution log
            log = self.server.execution_manager.get_execution_log()
            self.assertEqual(len(log), 1)

            entry = log[0]
            self.assertEqual(entry["tool_name"], "logged_tool")
            self.assertEqual(entry["status"], "success")
            self.assertEqual(entry["client_id"], self.client.client_id)

        asyncio.run(run_test())

    def test_permission_denied_logged(self):
        """Test that permission denial is logged"""

        @self.server.tool(
            name="restricted_tool",
            description="Requires permission",
            permissions=[Permission(PermissionType.FILE_WRITE)],
        )
        async def restricted_tool(client, params):
            return {}

        # Client has no permissions
        self.server.permission_manager.initialize_client(
            self.client.client_id, []
        )

        async def run_test():
            try:
                await self.server._handle_tools_call(
                    self.client,
                    {"name": "restricted_tool", "arguments": {}},
                )
            except PermissionDeniedError:
                pass

            # Check execution log
            log = self.server.execution_manager.get_execution_log()
            self.assertEqual(len(log), 1)
            self.assertEqual(log[0]["status"], "permission_denied")

            # Check permission audit trail
            audit = self.server.permission_manager.get_audit_trail()
            denied_events = [
                e for e in audit if e["event_type"] == "permission_denied"
            ]
            self.assertGreater(len(denied_events), 0)

        asyncio.run(run_test())


class TestPhase2CompleteWorkflow(unittest.TestCase):
    """Test complete workflows combining multiple features"""

    def setUp(self):
        """Setup before each test"""
        self.server = MCPServer()
        self.client = ClientContext()

    def test_complete_tool_workflow(self):
        """Test complete workflow: register -> list -> execute"""

        # Step 1: Register tools
        @self.server.tool(
            name="add",
            description="Add two numbers",
            input_schema={
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
        )
        async def add(client, params):
            return {"result": params["a"] + params["b"]}

        @self.server.tool(
            name="multiply",
            description="Multiply two numbers",
            input_schema={
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
        )
        async def multiply(client, params):
            return {"result": params["a"] * params["b"]}

        # Initialize client permissions
        self.server.permission_manager.initialize_client(
            self.client.client_id
        )

        async def run_test():
            # Step 2: List tools
            tools_list = await self.server._handle_tools_list(
                self.client, {}
            )
            self.assertEqual(len(tools_list["tools"]), 2)

            # Step 3: Execute tools
            add_result = await self.server._handle_tools_call(
                self.client,
                {"name": "add", "arguments": {"a": 5, "b": 3}},
            )
            self.assertIn("content", add_result)

            multiply_result = await self.server._handle_tools_call(
                self.client,
                {"name": "multiply", "arguments": {"a": 4, "b": 7}},
            )
            self.assertIn("content", multiply_result)

            # Step 4: Verify execution stats
            stats = self.server.execution_manager.get_stats()
            self.assertEqual(stats["total_executions"], 2)
            self.assertEqual(stats["success_count"], 2)

        asyncio.run(run_test())


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
