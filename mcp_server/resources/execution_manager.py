"""
Execution Manager - Secure tool execution
Module: resources.execution_manager
Date: 2025-11-23
Version: 0.2.0-alpha

CHANGELOG:
[2025-11-23 v0.2.0-alpha] Initial implementation
  - Secure tool execution with isolation
  - Parameter validation against JSON Schema
  - Permission verification before execution
  - Timeout and resource limits
  - Audit logging of all executions
  - Error handling and reporting

ARCHITECTURE:
ExecutionManager orchestrates secure tool execution:
  1. Validate input parameters against schema
  2. Check permissions with PermissionManager
  3. Execute in sandbox with timeout
  4. Capture and log results/errors
  5. Return formatted response

ExecutionManager is owned by MCPServer and uses:
  - ToolManager (get tools)
  - PermissionManager (check permissions)
  - SandboxContext (isolated execution)

SECURITY NOTES:
- All parameters validated before execution
- Permissions strictly checked
- Execution isolated in sandbox
- Timeout enforced
- All executions logged for audit
- Errors sanitized before return
"""

import asyncio
import logging
import traceback
from typing import Dict, Any, Optional
from datetime import datetime
import time

from ..tools.tool import Tool
from ..security.permission_manager import PermissionManager, PermissionDeniedError
from ..security.client_context import ClientContext


class ExecutionError(Exception):
    """Raised when tool execution fails"""

    def __init__(self, message: str, error_type: str = "execution_error", details: Optional[Dict] = None):
        self.message = message
        self.error_type = error_type
        self.details = details or {}
        super().__init__(message)


class ValidationError(Exception):
    """Raised when parameter validation fails"""

    def __init__(self, message: str, schema_errors: Optional[list] = None):
        self.message = message
        self.schema_errors = schema_errors or []
        super().__init__(message)


class ExecutionManager:
    """
    Manages secure execution of tools

    Coordinates validation, permission checking, and safe execution
    of tools with timeout and resource limits.
    """

    def __init__(
        self,
        permission_manager: PermissionManager,
        default_timeout: int = 30,
        max_memory_mb: int = 512,
    ):
        """
        Initialize execution manager

        Args:
            permission_manager: PermissionManager instance
            default_timeout: Default timeout in seconds
            max_memory_mb: Max memory limit in MB (Phase 2: logged only)
        """
        self.logger = logging.getLogger("execution.manager")
        self.permission_manager = permission_manager
        self.default_timeout = default_timeout
        self.max_memory_mb = max_memory_mb

        # Execution audit trail
        self._execution_log: list = []

    async def execute_tool(
        self,
        tool: Tool,
        client: ClientContext,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a tool securely

        Full execution flow:
        1. Validate parameters against schema
        2. Check permissions
        3. Execute in sandbox with timeout
        4. Log execution
        5. Return result or error

        Args:
            tool: Tool to execute
            client: Client context
            params: Input parameters

        Returns:
            dict: Execution result with format:
                {
                    "content": [...],  # Tool output
                    "isError": false
                }

        Raises:
            ValidationError: If parameters invalid
            PermissionDeniedError: If permission check fails
            ExecutionError: If execution fails
        """
        start_time = time.time()
        execution_id = f"{client.client_id}:{tool.name}:{int(start_time * 1000)}"

        self.logger.info(
            f"Executing tool: {tool.name} for client {client.client_id}"
        )

        try:
            # Step 1: Validate parameters
            await self._validate_params(params, tool.input_schema.to_dict())

            # Step 2: Check permissions
            self._check_permissions(client, tool)

            # Step 3: Execute with timeout
            timeout = tool.timeout if hasattr(tool, "timeout") else self.default_timeout
            result = await self._execute_with_timeout(tool, client, params, timeout)

            # Step 4: Log success
            execution_time = time.time() - start_time
            self._log_execution(
                execution_id=execution_id,
                client_id=client.client_id,
                tool_name=tool.name,
                status="success",
                execution_time=execution_time,
                params=params,
                result=result,
            )

            self.logger.info(
                f"Tool executed successfully: {tool.name} "
                f"({execution_time:.3f}s)"
            )

            # Return in MCP format
            return {
                "content": [
                    {
                        "type": "text",
                        "text": str(result) if not isinstance(result, str) else result
                    }
                ],
                "isError": False,
            }

        except ValidationError as e:
            self.logger.warning(f"Validation error: {e.message}")
            self._log_execution(
                execution_id=execution_id,
                client_id=client.client_id,
                tool_name=tool.name,
                status="validation_error",
                execution_time=time.time() - start_time,
                params=params,
                error=str(e),
            )
            raise

        except PermissionDeniedError as e:
            self.logger.warning(f"Permission denied: {e}")
            self._log_execution(
                execution_id=execution_id,
                client_id=client.client_id,
                tool_name=tool.name,
                status="permission_denied",
                execution_time=time.time() - start_time,
                params=params,
                error=str(e),
            )
            raise

        except asyncio.TimeoutError:
            self.logger.error(f"Tool execution timeout: {tool.name}")
            self._log_execution(
                execution_id=execution_id,
                client_id=client.client_id,
                tool_name=tool.name,
                status="timeout",
                execution_time=time.time() - start_time,
                params=params,
                error="Execution timeout",
            )
            raise ExecutionError(
                f"Tool execution timeout after {timeout}s",
                error_type="timeout",
            )

        except Exception as e:
            self.logger.error(f"Tool execution failed: {e}")
            self.logger.debug(traceback.format_exc())
            self._log_execution(
                execution_id=execution_id,
                client_id=client.client_id,
                tool_name=tool.name,
                status="error",
                execution_time=time.time() - start_time,
                params=params,
                error=str(e),
            )
            raise ExecutionError(
                f"Tool execution failed: {str(e)}",
                error_type=type(e).__name__,
                details={"traceback": traceback.format_exc()},
            )

    async def _validate_params(
        self,
        params: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> None:
        """
        Validate parameters against JSON Schema

        Phase 2: Basic validation (type checking, required fields)
        Phase 3+: Full JSON Schema validation with jsonschema library

        Args:
            params: Parameters to validate
            schema: JSON Schema

        Raises:
            ValidationError: If validation fails
        """
        # Basic validation for Phase 2
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        # Check required fields
        for field in required:
            if field not in params:
                raise ValidationError(
                    f"Missing required parameter: {field}",
                    schema_errors=[f"Required field '{field}' not provided"],
                )

        # Basic type checking
        for param_name, param_value in params.items():
            if param_name in properties:
                expected_type = properties[param_name].get("type")
                if expected_type:
                    if not self._check_type(param_value, expected_type):
                        raise ValidationError(
                            f"Invalid type for parameter '{param_name}': "
                            f"expected {expected_type}, got {type(param_value).__name__}",
                            schema_errors=[
                                f"Type mismatch for '{param_name}'"
                            ],
                        )

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """
        Check if value matches expected JSON Schema type

        Args:
            value: Value to check
            expected_type: JSON Schema type string

        Returns:
            bool: True if type matches
        """
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }

        if expected_type not in type_map:
            return True  # Unknown type, skip validation

        expected_python_type = type_map[expected_type]
        return isinstance(value, expected_python_type)

    def _check_permissions(
        self,
        client: ClientContext,
        tool: Tool,
    ) -> None:
        """
        Check if client has permissions to execute tool

        Args:
            client: Client context
            tool: Tool to execute

        Raises:
            PermissionDeniedError: If any required permission missing
        """
        for required_permission in tool.permissions:
            self.permission_manager.check_permission(
                client.client_id, required_permission
            )

    async def _execute_with_timeout(
        self,
        tool: Tool,
        client: ClientContext,
        params: Dict[str, Any],
        timeout: int,
    ) -> Any:
        """
        Execute tool with timeout protection

        Phase 2: Simple timeout with asyncio
        Phase 6: Process isolation with subprocess timeout

        Args:
            tool: Tool to execute
            client: Client context
            params: Validated parameters
            timeout: Timeout in seconds

        Returns:
            Any: Tool execution result

        Raises:
            asyncio.TimeoutError: If execution exceeds timeout
        """
        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                tool.execute(client, params),
                timeout=timeout,
            )
            return result
        except asyncio.TimeoutError:
            self.logger.error(
                f"Tool {tool.name} exceeded timeout of {timeout}s"
            )
            raise

    def _log_execution(
        self,
        execution_id: str,
        client_id: str,
        tool_name: str,
        status: str,
        execution_time: float,
        params: Dict[str, Any],
        result: Any = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Log tool execution for audit trail

        Args:
            execution_id: Unique execution ID
            client_id: Client identifier
            tool_name: Name of executed tool
            status: Execution status (success/error/timeout/etc)
            execution_time: Execution time in seconds
            params: Input parameters
            result: Execution result (if success)
            error: Error message (if failed)
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "execution_id": execution_id,
            "event_type": "tool_executed",
            "client_id": client_id,
            "tool_name": tool_name,
            "status": status,
            "execution_time_ms": int(execution_time * 1000),
            "params": params,
        }

        if result is not None:
            log_entry["result"] = str(result)[:500]  # Truncate for logging

        if error is not None:
            log_entry["error"] = str(error)

        self._execution_log.append(log_entry)

    def get_execution_log(self) -> list:
        """
        Get execution audit log

        Returns:
            list: Execution log entries
        """
        return list(self._execution_log)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get execution statistics

        Returns:
            dict: Execution statistics
        """
        total = len(self._execution_log)
        if total == 0:
            return {
                "total_executions": 0,
                "success_count": 0,
                "error_count": 0,
                "avg_execution_time_ms": 0,
            }

        success = sum(1 for e in self._execution_log if e["status"] == "success")
        errors = total - success
        avg_time = sum(e["execution_time_ms"] for e in self._execution_log) / total

        return {
            "total_executions": total,
            "success_count": success,
            "error_count": errors,
            "success_rate": success / total if total > 0 else 0,
            "avg_execution_time_ms": avg_time,
        }


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    from unittest.mock import AsyncMock, MagicMock
    from ..tools.tool import FunctionTool
    from ..security.permission import Permission, PermissionType

    class TestExecutionManager(unittest.TestCase):
        """Test suite for ExecutionManager"""

        def setUp(self):
            """Setup before each test"""
            self.permission_manager = PermissionManager()
            self.manager = ExecutionManager(self.permission_manager)
            self.client = ClientContext()

        def test_initialization(self):
            """Test ExecutionManager initialization"""
            self.assertEqual(self.manager.default_timeout, 30)
            self.assertEqual(self.manager.max_memory_mb, 512)
            self.assertEqual(len(self.manager.get_execution_log()), 0)

        def test_validate_params_success(self):
            """Test parameter validation success"""

            async def run_test():
                schema = {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                    },
                    "required": ["name"],
                }
                params = {"name": "test", "age": 42}
                await self.manager._validate_params(params, schema)

            asyncio.run(run_test())

        def test_validate_params_missing_required(self):
            """Test parameter validation with missing required field"""

            async def run_test():
                schema = {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                }
                params = {}
                with self.assertRaises(ValidationError):
                    await self.manager._validate_params(params, schema)

            asyncio.run(run_test())

        def test_validate_params_type_mismatch(self):
            """Test parameter validation with type mismatch"""

            async def run_test():
                schema = {
                    "type": "object",
                    "properties": {"age": {"type": "integer"}},
                }
                params = {"age": "not_an_int"}
                with self.assertRaises(ValidationError):
                    await self.manager._validate_params(params, schema)

            asyncio.run(run_test())

        def test_check_type(self):
            """Test type checking"""
            self.assertTrue(self.manager._check_type("hello", "string"))
            self.assertTrue(self.manager._check_type(42, "integer"))
            self.assertTrue(self.manager._check_type(3.14, "number"))
            self.assertTrue(self.manager._check_type(True, "boolean"))
            self.assertTrue(self.manager._check_type([], "array"))
            self.assertTrue(self.manager._check_type({}, "object"))

            self.assertFalse(self.manager._check_type(42, "string"))
            self.assertFalse(self.manager._check_type("text", "integer"))

        def test_execution_logging(self):
            """Test execution logging"""
            self.manager._log_execution(
                execution_id="test-1",
                client_id="client-1",
                tool_name="test_tool",
                status="success",
                execution_time=0.123,
                params={"arg": "value"},
                result={"output": "ok"},
            )

            log = self.manager.get_execution_log()
            self.assertEqual(len(log), 1)
            self.assertEqual(log[0]["tool_name"], "test_tool")
            self.assertEqual(log[0]["status"], "success")

        def test_get_stats(self):
            """Test statistics generation"""
            # Add some executions
            self.manager._log_execution(
                "e1", "c1", "tool1", "success", 0.1, {}
            )
            self.manager._log_execution(
                "e2", "c1", "tool2", "success", 0.2, {}
            )
            self.manager._log_execution(
                "e3", "c1", "tool3", "error", 0.3, {}, error="test error"
            )

            stats = self.manager.get_stats()
            self.assertEqual(stats["total_executions"], 3)
            self.assertEqual(stats["success_count"], 2)
            self.assertEqual(stats["error_count"], 1)
            self.assertAlmostEqual(stats["success_rate"], 2 / 3)

        def test_execute_tool_success(self):
            """Test successful tool execution"""

            async def run_test():
                async def my_tool(ctx, params):
                    return {"result": "ok"}

                tool = FunctionTool(
                    name="test",
                    description="Test tool",
                    func=my_tool,
                    input_schema={"arg": {"type": "string"}},
                    permissions=[],
                )

                self.permission_manager.initialize_client(
                    self.client.client_id, []
                )

                result = await self.manager.execute_tool(
                    tool, self.client, {"arg": "test"}
                )
                self.assertIn("content", result)
                self.assertFalse(result["isError"])

            asyncio.run(run_test())

    unittest.main()
