"""
Sandbox Context - Isolated execution context for clients

Module: resources.sandbox_context
Date: 2025-11-23
Version: 0.2.0-alpha

CHANGELOG:
[2025-11-23 v0.2.0-alpha] Initial implementation
  - Per-client execution context
  - Variable storage and retrieval
  - Working directory management
  - Context cleanup
  - State isolation between clients

ARCHITECTURE:
SandboxContext provides isolated execution environment for each client:
  - Separate variable storage
  - Isolated working directory (Phase 6)
  - State persistence across tool calls
  - Cleanup on client disconnect

Each client gets its own SandboxContext instance.
Variables stored in context persist across tool executions.

SECURITY NOTES:
- Complete isolation between clients
- No shared state between contexts
- Variables scoped to client only
- Working directory restricted (Phase 6)
- Cleanup on context destroy
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime


class SandboxContext:
    """
    Isolated execution context for a client

    Provides:
    - Variable storage per client
    - Working directory isolation
    - State persistence across tool calls
    - Context cleanup
    """

    def __init__(self, client_id: str, working_dir: Optional[str] = None):
        """
        Initialize sandbox context

        Args:
            client_id: Client identifier
            working_dir: Working directory for this context (Phase 6)
        """
        self.logger = logging.getLogger(f"sandbox.{client_id}")
        self.client_id = client_id
        self.working_dir = working_dir or f"/tmp/mcp_sandbox_{client_id}"

        # Execution environment
        self._variables: Dict[str, Any] = {}
        self._execution_count = 0
        self._created_at = datetime.utcnow()
        self._last_activity = datetime.utcnow()

        self.logger.info(f"Sandbox context created for {client_id}")

    def set_variable(self, name: str, value: Any) -> None:
        """
        Store a variable in context

        Variables persist across tool executions for this client.

        Args:
            name: Variable name
            value: Variable value
        """
        self._variables[name] = value
        self._last_activity = datetime.utcnow()
        self.logger.debug(f"Variable set: {name}")

    def get_variable(self, name: str, default: Any = None) -> Any:
        """
        Retrieve a variable from context

        Args:
            name: Variable name
            default: Default value if not found

        Returns:
            Variable value or default
        """
        self._last_activity = datetime.utcnow()
        return self._variables.get(name, default)

    def has_variable(self, name: str) -> bool:
        """
        Check if variable exists

        Args:
            name: Variable name

        Returns:
            bool: True if variable exists
        """
        return name in self._variables

    def delete_variable(self, name: str) -> bool:
        """
        Delete a variable from context

        Args:
            name: Variable name

        Returns:
            bool: True if variable existed and was deleted
        """
        if name in self._variables:
            del self._variables[name]
            self._last_activity = datetime.utcnow()
            self.logger.debug(f"Variable deleted: {name}")
            return True
        return False

    def list_variables(self) -> Dict[str, Any]:
        """
        List all variables in context

        Returns:
            dict: All variables
        """
        return dict(self._variables)

    def clear_variables(self) -> None:
        """
        Clear all variables

        Useful for resetting context without destroying it.
        """
        count = len(self._variables)
        self._variables.clear()
        self._last_activity = datetime.utcnow()
        self.logger.info(f"Cleared {count} variables")

    def increment_execution_count(self) -> int:
        """
        Increment and return execution count

        Called by ExecutionManager on each tool execution.

        Returns:
            int: New execution count
        """
        self._execution_count += 1
        self._last_activity = datetime.utcnow()
        return self._execution_count

    def get_stats(self) -> Dict[str, Any]:
        """
        Get context statistics

        Returns:
            dict: Context stats
        """
        uptime = (datetime.utcnow() - self._created_at).total_seconds()
        idle_time = (datetime.utcnow() - self._last_activity).total_seconds()

        return {
            "client_id": self.client_id,
            "working_dir": self.working_dir,
            "variable_count": len(self._variables),
            "execution_count": self._execution_count,
            "created_at": self._created_at.isoformat(),
            "last_activity": self._last_activity.isoformat(),
            "uptime_seconds": uptime,
            "idle_seconds": idle_time,
        }

    def clear(self) -> None:
        """
        Clear context (cleanup)

        Called when client disconnects or context is destroyed.
        """
        self.logger.info(
            f"Clearing context: {self._execution_count} executions, "
            f"{len(self._variables)} variables"
        )
        self._variables.clear()
        self._execution_count = 0

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"SandboxContext(client={self.client_id}, "
            f"vars={len(self._variables)}, "
            f"execs={self._execution_count})"
        )


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    import time

    class TestSandboxContext(unittest.TestCase):
        """Test suite for SandboxContext"""

        def setUp(self):
            """Setup before each test"""
            self.context = SandboxContext("test_client")

        def test_initialization(self):
            """Test context initialization"""
            self.assertEqual(self.context.client_id, "test_client")
            self.assertEqual(len(self.context._variables), 0)
            self.assertEqual(self.context._execution_count, 0)

        def test_set_and_get_variable(self):
            """Test variable storage and retrieval"""
            self.context.set_variable("name", "value")
            self.assertEqual(self.context.get_variable("name"), "value")

        def test_get_variable_default(self):
            """Test get variable with default"""
            result = self.context.get_variable("nonexistent", "default")
            self.assertEqual(result, "default")

        def test_has_variable(self):
            """Test variable existence check"""
            self.assertFalse(self.context.has_variable("test"))
            self.context.set_variable("test", 123)
            self.assertTrue(self.context.has_variable("test"))

        def test_delete_variable(self):
            """Test variable deletion"""
            self.context.set_variable("test", "value")
            self.assertTrue(self.context.has_variable("test"))

            result = self.context.delete_variable("test")
            self.assertTrue(result)
            self.assertFalse(self.context.has_variable("test"))

        def test_delete_nonexistent_variable(self):
            """Test deleting nonexistent variable"""
            result = self.context.delete_variable("nonexistent")
            self.assertFalse(result)

        def test_list_variables(self):
            """Test listing all variables"""
            self.context.set_variable("var1", "value1")
            self.context.set_variable("var2", "value2")

            variables = self.context.list_variables()
            self.assertEqual(len(variables), 2)
            self.assertIn("var1", variables)
            self.assertIn("var2", variables)

        def test_clear_variables(self):
            """Test clearing all variables"""
            self.context.set_variable("var1", "value1")
            self.context.set_variable("var2", "value2")
            self.assertEqual(len(self.context._variables), 2)

            self.context.clear_variables()
            self.assertEqual(len(self.context._variables), 0)

        def test_increment_execution_count(self):
            """Test execution count increment"""
            self.assertEqual(self.context._execution_count, 0)

            count1 = self.context.increment_execution_count()
            self.assertEqual(count1, 1)

            count2 = self.context.increment_execution_count()
            self.assertEqual(count2, 2)

        def test_get_stats(self):
            """Test getting context statistics"""
            self.context.set_variable("test", "value")
            self.context.increment_execution_count()

            stats = self.context.get_stats()
            self.assertEqual(stats["client_id"], "test_client")
            self.assertEqual(stats["variable_count"], 1)
            self.assertEqual(stats["execution_count"], 1)
            self.assertIn("uptime_seconds", stats)
            self.assertIn("idle_seconds", stats)

        def test_clear_context(self):
            """Test context cleanup"""
            self.context.set_variable("var1", "value1")
            self.context.increment_execution_count()

            self.context.clear()
            self.assertEqual(len(self.context._variables), 0)
            self.assertEqual(self.context._execution_count, 0)

        def test_context_isolation(self):
            """Test that contexts are isolated"""
            context1 = SandboxContext("client1")
            context2 = SandboxContext("client2")

            context1.set_variable("shared", "value1")
            context2.set_variable("shared", "value2")

            self.assertEqual(context1.get_variable("shared"), "value1")
            self.assertEqual(context2.get_variable("shared"), "value2")

        def test_last_activity_updates(self):
            """Test that last_activity is updated"""
            initial_activity = self.context._last_activity
            time.sleep(0.01)

            self.context.set_variable("test", "value")
            self.assertGreater(
                self.context._last_activity, initial_activity
            )

    unittest.main()
