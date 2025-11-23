"""
Tool Module - Base class for MCP Tools

Module: tools.tool
Date: 2025-11-23
Version: 0.2.0-alpha

CHANGELOG:
[2025-11-23 v0.2.0-alpha] Initial implementation
  - Abstract Tool class
  - InputSchema and OutputSchema support
  - Permission declaration
  - Metadata and info methods
  - Tools can be registered with @server.tool()

ARCHITECTURE:
Tool is the abstract base class for all executable tools in MCP.
Each tool:
  - Has a unique name
  - Declares input and output schemas (JSON Schema)
  - Declares required permissions
  - Implements an async execute() method
  - Is registered with the ToolManager

Tools are exposed to clients via tools/list RPC method.
Clients call tools via tools/call RPC method.

SECURITY NOTES:
- Tools must declare all required permissions
- Tools are executed in isolated context
- Input parameters validated against schema
- Output must conform to output schema
- Execution logged to audit trail
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
import logging
import json

from ..security.permission import Permission


@dataclass
class InputSchema:
    """JSON Schema for tool input parameters"""

    properties: Dict[str, Any]
    required: List[str] = field(default_factory=list)
    type: str = "object"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON Schema format"""
        schema = {
            "type": self.type,
            "properties": self.properties,
        }
        if self.required:
            schema["required"] = self.required
        return schema

    @staticmethod
    def create(properties: Dict[str, Any], required: List[str] = None):
        """Create InputSchema from dict"""
        return InputSchema(properties, required or [])


@dataclass
class OutputSchema:
    """JSON Schema for tool output"""

    properties: Dict[str, Any] = field(default_factory=dict)
    type: str = "object"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON Schema format"""
        return {
            "type": self.type,
            "properties": self.properties,
        }

    @staticmethod
    def create(properties: Dict[str, Any] = None):
        """Create OutputSchema from dict"""
        return OutputSchema(properties or {})


class Tool(ABC):
    """
    Abstract base class for MCP tools

    All executable tools must inherit from this class and implement
    the execute() method.

    Attributes:
        name: Unique identifier for the tool
        description: Human-readable description for clients
        input_schema: InputSchema describing required parameters
        output_schema: OutputSchema describing return value
        permissions: List of required Permission objects
        timeout: Execution timeout in seconds (default: 30)
    """

    # Class attributes that subclasses must define
    name: str
    description: str
    input_schema: InputSchema
    output_schema: OutputSchema
    permissions: List[Permission] = []
    timeout: int = 30

    def __init__(self):
        """Initialize tool"""
        self.logger = logging.getLogger(f"tools.{self.name}")

        # Validate required attributes
        if not hasattr(self, "name") or not self.name:
            raise ValueError("Tool must have a 'name' attribute")
        if not hasattr(self, "description"):
            raise ValueError("Tool must have a 'description' attribute")
        if not hasattr(self, "input_schema"):
            self.input_schema = InputSchema({})
        if not hasattr(self, "output_schema"):
            self.output_schema = OutputSchema()
        if not hasattr(self, "permissions"):
            self.permissions = []

    @abstractmethod
    async def execute(
        self,
        client_context,  # ClientContext
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute the tool

        This method must be implemented by subclasses.

        Args:
            client_context: The client's security context
            params: Input parameters (already validated against schema)

        Returns:
            dict: Result data (must conform to output_schema)

        Raises:
            Exception: Any execution errors (will be caught and logged)
        """
        pass

    def get_info(self) -> Dict[str, Any]:
        """
        Get tool information for MCP exposure

        Returns:
            dict: Tool metadata in MCP format
        """
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema.to_dict(),
            "outputSchema": self.output_schema.to_dict(),
            "permissions": [p.to_dict() for p in self.permissions],
        }

    def __repr__(self) -> str:
        """String representation"""
        perms_str = (
            f" ({len(self.permissions)} perms)"
            if self.permissions
            else ""
        )
        return f"Tool({self.name}){perms_str}"


class FunctionTool(Tool):
    """
    Tool implemented as a simple function

    Wraps a regular async function as a Tool.
    Used for decorator-based registration.
    """

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable,
        input_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        permissions: Optional[List[Permission]] = None,
        timeout: int = 30,
    ):
        """
        Initialize function-based tool

        Args:
            name: Tool name
            description: Tool description
            func: Async callable to execute
            input_schema: Input JSON schema
            output_schema: Output JSON schema
            permissions: List of required permissions
            timeout: Execution timeout
        """
        self.name = name
        self.description = description
        self._func = func
        self.input_schema = InputSchema.create(input_schema or {})
        self.output_schema = OutputSchema.create(output_schema or {})
        self.permissions = permissions or []
        self.timeout = timeout

        super().__init__()

    async def execute(
        self,
        client_context,  # ClientContext
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the wrapped function"""
        return await self._func(client_context, params)


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    from unittest.mock import AsyncMock

    class TestInputSchema(unittest.TestCase):
        """Test suite for InputSchema"""

        def test_creation(self):
            """Test InputSchema creation"""
            schema = InputSchema(
                properties={
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                required=["name"],
            )
            self.assertEqual(len(schema.properties), 2)
            self.assertEqual(schema.required, ["name"])

        def test_to_dict(self):
            """Test schema serialization"""
            schema = InputSchema(
                properties={"name": {"type": "string"}},
                required=["name"],
            )
            d = schema.to_dict()
            self.assertEqual(d["type"], "object")
            self.assertIn("properties", d)
            self.assertEqual(d["required"], ["name"])

        def test_create_static(self):
            """Test static creation method"""
            schema = InputSchema.create(
                {"name": {"type": "string"}}, ["name"]
            )
            self.assertEqual(len(schema.properties), 1)

    class TestOutputSchema(unittest.TestCase):
        """Test suite for OutputSchema"""

        def test_creation(self):
            """Test OutputSchema creation"""
            schema = OutputSchema(
                properties={"result": {"type": "string"}}
            )
            self.assertIn("result", schema.properties)

        def test_to_dict(self):
            """Test schema serialization"""
            schema = OutputSchema.create(
                {"result": {"type": "string"}}
            )
            d = schema.to_dict()
            self.assertEqual(d["type"], "object")
            self.assertIn("properties", d)

    class TestFunctionTool(unittest.TestCase):
        """Test suite for FunctionTool"""

        def test_creation(self):
            """Test FunctionTool creation"""

            async def my_tool(ctx, params):
                return {"result": "ok"}

            tool = FunctionTool(
                name="my_tool",
                description="A test tool",
                func=my_tool,
                input_schema={"arg": {"type": "string"}},
            )
            self.assertEqual(tool.name, "my_tool")
            self.assertEqual(tool.description, "A test tool")

        def test_get_info(self):
            """Test get_info method"""

            async def my_tool(ctx, params):
                return {}

            tool = FunctionTool(
                name="test",
                description="Test tool",
                func=my_tool,
            )
            info = tool.get_info()
            self.assertEqual(info["name"], "test")
            self.assertEqual(info["description"], "Test tool")
            self.assertIn("inputSchema", info)
            self.assertIn("outputSchema", info)

        def test_cannot_instantiate_abstract_tool(self):
            """Test abstract Tool cannot be instantiated"""
            with self.assertRaises(TypeError):
                Tool()

        def test_function_tool_execute(self):
            """Test FunctionTool execution"""
            import asyncio

            async def my_tool(ctx, params):
                return {"result": params.get("value")}

            tool = FunctionTool(
                name="test",
                description="Test",
                func=my_tool,
            )

            async def run_test():
                result = await tool.execute(None, {"value": 42})
                self.assertEqual(result["result"], 42)

            asyncio.run(run_test())

    unittest.main()
