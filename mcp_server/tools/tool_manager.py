"""
Tool Manager - Central registry for tools

Module: tools.tool_manager
Date: 2025-11-23
Version: 0.2.0-alpha

CHANGELOG:
[2025-11-23 v0.2.0-alpha] Initial implementation
  - Tool registration and retrieval
  - Centralized registry
  - Tool listing and filtering
  - Decorator support via tool() method
  - Tool info exposure for MCP clients

ARCHITECTURE:
ToolManager is the central registry for all tools.
Responsibilities:
  - Store registered tools
  - Provide access to tools by name
  - List available tools
  - Expose tool info to clients
  - Support decorator-based registration

ToolManager is owned by MCPServer and used by ExecutionManager.

SECURITY NOTES:
- Tools are registered only with server setup
- Tool list exposed includes required permissions
- Tool execution validation done by ExecutionManager
"""

import logging
from typing import Dict, Optional, Callable, Any, List

from .tool import Tool, FunctionTool
from ..security.permission import Permission


class ToolManager:
    """
    Central registry and manager for MCP tools

    Stores all registered tools and provides methods to access and list them.
    """

    def __init__(self):
        """Initialize tool manager"""
        self.logger = logging.getLogger("tools.manager")
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """
        Register a tool

        Args:
            tool: Tool instance to register

        Raises:
            ValueError: If tool with same name already exists
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")

        self._tools[tool.name] = tool
        self.logger.info(f"Tool registered: {tool.name}")

    def unregister(self, tool_name: str) -> None:
        """
        Unregister a tool

        Args:
            tool_name: Name of tool to unregister
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            self.logger.info(f"Tool unregistered: {tool_name}")

    def get(self, tool_name: str) -> Optional[Tool]:
        """
        Get a tool by name

        Args:
            tool_name: Name of tool to retrieve

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(tool_name)

    def exists(self, tool_name: str) -> bool:
        """
        Check if tool exists

        Args:
            tool_name: Name of tool

        Returns:
            bool: True if tool is registered
        """
        return tool_name in self._tools

    def list_all(self) -> Dict[str, Tool]:
        """
        Get all registered tools

        Returns:
            dict: All tools keyed by name
        """
        return dict(self._tools)

    def count(self) -> int:
        """
        Get number of registered tools

        Returns:
            int: Count of tools
        """
        return len(self._tools)

    def get_info_list(self) -> List[Dict[str, Any]]:
        """
        Get list of tool info for MCP exposure

        Returns tool information in MCP format for tools/list response.

        Returns:
            list: Tool info dictionaries
        """
        return [tool.get_info() for tool in self._tools.values()]

    def get_info_for_client(self, client) -> List[Dict[str, Any]]:
        """
        Get filtered tool info for a specific client

        Currently returns all tools. Future versions could filter based
        on client permissions.

        Args:
            client: ClientContext

        Returns:
            list: Tool info dictionaries visible to client
        """
        # TODO: Phase 3 - Filter by client permissions
        return self.get_info_list()

    def tool(
        self,
        name: str,
        description: str,
        input_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        permissions: Optional[List[Permission]] = None,
        timeout: int = 30,
    ):
        """
        Decorator to register a tool

        Usage:
            @tool_manager.tool(
                name="read_file",
                description="Read a file",
                input_schema={"path": {"type": "string"}},
                permissions=[Permission(PermissionType.FILE_READ)]
            )
            async def read_file(client, params):
                return {"content": "..."}

        Args:
            name: Tool name
            description: Tool description
            input_schema: Input JSON schema
            output_schema: Output JSON schema
            permissions: Required permissions
            timeout: Execution timeout

        Returns:
            decorator: Function decorator
        """

        def decorator(func: Callable):
            tool = FunctionTool(
                name=name,
                description=description,
                func=func,
                input_schema=input_schema,
                output_schema=output_schema,
                permissions=permissions or [],
                timeout=timeout,
            )
            self.register(tool)
            return func

        return decorator


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    from unittest.mock import MagicMock
    from .tool import InputSchema, OutputSchema

    class TestToolManager(unittest.TestCase):
        """Test suite for ToolManager"""

        def setUp(self):
            """Setup before each test"""
            self.manager = ToolManager()

        def test_initialization(self):
            """Test ToolManager initialization"""
            self.assertEqual(self.manager.count(), 0)
            self.assertEqual(self.manager.list_all(), {})

        def test_register_tool(self):
            """Test registering a tool"""

            async def dummy(ctx, params):
                return {}

            tool = FunctionTool(
                name="test_tool",
                description="Test tool",
                func=dummy,
            )
            self.manager.register(tool)

            self.assertEqual(self.manager.count(), 1)
            self.assertTrue(self.manager.exists("test_tool"))

        def test_register_duplicate_error(self):
            """Test registering duplicate tool raises error"""

            async def dummy(ctx, params):
                return {}

            tool = FunctionTool(
                name="test",
                description="Test",
                func=dummy,
            )
            self.manager.register(tool)

            with self.assertRaises(ValueError):
                self.manager.register(tool)

        def test_get_tool(self):
            """Test getting a tool"""

            async def dummy(ctx, params):
                return {}

            tool = FunctionTool(
                name="test",
                description="Test",
                func=dummy,
            )
            self.manager.register(tool)

            retrieved = self.manager.get("test")
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.name, "test")

        def test_get_nonexistent_tool(self):
            """Test getting nonexistent tool returns None"""
            result = self.manager.get("nonexistent")
            self.assertIsNone(result)

        def test_unregister_tool(self):
            """Test unregistering a tool"""

            async def dummy(ctx, params):
                return {}

            tool = FunctionTool(
                name="test",
                description="Test",
                func=dummy,
            )
            self.manager.register(tool)
            self.assertEqual(self.manager.count(), 1)

            self.manager.unregister("test")
            self.assertEqual(self.manager.count(), 0)
            self.assertIsNone(self.manager.get("test"))

        def test_list_all_tools(self):
            """Test listing all tools"""

            async def dummy(ctx, params):
                return {}

            tool1 = FunctionTool(
                name="tool1",
                description="Tool 1",
                func=dummy,
            )
            tool2 = FunctionTool(
                name="tool2",
                description="Tool 2",
                func=dummy,
            )

            self.manager.register(tool1)
            self.manager.register(tool2)

            tools = self.manager.list_all()
            self.assertEqual(len(tools), 2)
            self.assertIn("tool1", tools)
            self.assertIn("tool2", tools)

        def test_get_info_list(self):
            """Test getting info list for MCP"""

            async def dummy(ctx, params):
                return {}

            tool = FunctionTool(
                name="test",
                description="Test tool",
                func=dummy,
                input_schema={"arg": {"type": "string"}},
            )
            self.manager.register(tool)

            info_list = self.manager.get_info_list()
            self.assertEqual(len(info_list), 1)
            self.assertEqual(info_list[0]["name"], "test")
            self.assertEqual(info_list[0]["description"], "Test tool")

        def test_decorator_registration(self):
            """Test decorator-based registration"""

            @self.manager.tool(
                name="decorated",
                description="Decorated tool",
                input_schema={"x": {"type": "number"}},
            )
            async def my_tool(ctx, params):
                return {"result": params["x"]}

            self.assertTrue(self.manager.exists("decorated"))
            tool = self.manager.get("decorated")
            self.assertEqual(tool.name, "decorated")

    unittest.main()
