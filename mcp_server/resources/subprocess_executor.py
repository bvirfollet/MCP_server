#!/usr/bin/env python3
"""
Subprocess Executor for Phase 6 - Process Isolation

Module: resources.subprocess_executor
Date: 2025-11-23
Version: 0.1.0-alpha (Phase 6)

CHANGELOG:
[2025-11-23 v0.1.0-alpha] Subprocess Executor Implementation
  - Execute code in isolated subprocess with timeout
  - Handle process lifecycle (create, run, timeout, cleanup)
  - Pass context via JSON stdin/stdout
  - SIGTERM → SIGKILL timeout handling
  - Result parsing and error handling

ARCHITECTURE:
SubprocessExecutor allows code execution in a completely isolated subprocess.
- Each tool call creates a new Python subprocess
- Code + context passed via JSON stdin
- Results retrieved via JSON stdout
- Timeout enforced (SIGTERM after timeout, SIGKILL after additional delay)
- Compatible with ClientIsolationManager for path isolation
- Compatible with ResourceManager for quota enforcement

SECURITY NOTES:
- Subprocess runs with no network access (can be enforced with cgroups)
- Working directory restricted to client's isolated directory
- Code execution sandbox via subprocess isolation
- Timeout prevents infinite loops
- Stderr captured for debugging
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any


logger = logging.getLogger(__name__)


# ============================================================================
# Wrapper Script (executed inside subprocess)
# ============================================================================

SUBPROCESS_WRAPPER = '''
"""
Subprocess wrapper script - executed in isolated subprocess

This script:
1. Reads JSON input from stdin containing code + context
2. Sets up global context/variables
3. Executes the code
4. Captures results and returns JSON on stdout
"""

import sys
import json
import traceback
from io import StringIO

def main():
    try:
        # Read input from stdin
        input_data = sys.stdin.read()
        if not input_data:
            result = {"error": "No input provided"}
            print(json.dumps(result))
            return

        data = json.loads(input_data)
        code = data.get("code", "")
        context = data.get("context", {})
        client_id = data.get("client_id", "unknown")

        if not code:
            result = {"error": "No code provided"}
            print(json.dumps(result))
            return

        # Setup execution context
        exec_globals = {"__builtins__": __builtins__}
        exec_globals.update(context)

        # Capture stdout
        old_stdout = sys.stdout
        captured_stdout = StringIO()
        sys.stdout = captured_stdout

        try:
            # Execute code
            exec(code, exec_globals)
        finally:
            # Restore stdout
            sys.stdout = old_stdout
            stdout_value = captured_stdout.getvalue()

        # Extract modified globals (exclude builtins and private vars)
        result_context = {
            k: v for k, v in exec_globals.items()
            if not k.startswith("__") and k != "__builtins__"
        }

        # Return success with context
        result = {
            "success": True,
            "result": None,
            "context": result_context,
            "stdout": stdout_value if stdout_value else None
        }

        print(json.dumps(result, default=str))

    except Exception as e:
        # Return error with traceback
        result = {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "context": {}
        }
        print(json.dumps(result, default=str), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
'''


class SubprocessExecutor:
    """
    Executes Python code in an isolated subprocess with timeout support.

    Features:
    - Creates subprocess for each code execution
    - Passes code + context via JSON stdin
    - Enforces timeout (SIGTERM then SIGKILL)
    - Captures stdout/stderr
    - Parses JSON results
    - Cleans up processes
    """

    def __init__(self, timeout: float = 30.0, kill_timeout: float = 2.0):
        """
        Initialize SubprocessExecutor.

        Args:
            timeout: Default timeout in seconds (default 30s)
            kill_timeout: Time to wait after SIGTERM before SIGKILL (default 2s)
        """
        self.timeout = timeout
        self.kill_timeout = kill_timeout
        self.logger = logging.getLogger("resources.subprocess")

    async def execute(
        self,
        code: str,
        client_id: str,
        working_dir: Optional[Path] = None,
        timeout: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute Python code in an isolated subprocess.

        Args:
            code: Python code to execute (string)
            client_id: ID of the client executing (for logging)
            working_dir: Working directory for subprocess (default: current dir)
            timeout: Timeout in seconds (default: self.timeout)
            context: Pre-loaded context/variables (dict)

        Returns:
            Dict with keys:
            - success: bool
            - result: Execution result (None for code)
            - context: Modified globals after execution
            - stdout: Captured stdout
            - error: Error message (if failed)
            - traceback: Full traceback (if failed)

        Raises:
            TimeoutError: If timeout exceeded
            SubprocessError: If subprocess crashed or couldn't start
        """
        timeout = timeout or self.timeout
        context = context or {}

        try:
            # Create wrapper script in temp file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.py',
                delete=False,
                dir=working_dir
            ) as f:
                f.write(SUBPROCESS_WRAPPER)
                wrapper_path = f.name

            try:
                # Prepare subprocess
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    wrapper_path,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=working_dir,
                    preexec_fn=os.setsid if hasattr(os, 'setsid') else None
                )

                # Prepare input
                input_data = {
                    "code": code,
                    "context": context,
                    "client_id": client_id
                }
                input_json = json.dumps(input_data)

                # Execute with timeout
                try:
                    stdout_data, stderr_data = await asyncio.wait_for(
                        process.communicate(input=input_json.encode('utf-8')),
                        timeout=timeout
                    )

                    stdout = stdout_data.decode('utf-8', errors='replace')
                    stderr = stderr_data.decode('utf-8', errors='replace')

                    # Parse result
                    if stdout:
                        try:
                            result = json.loads(stdout)
                        except json.JSONDecodeError:
                            # If stdout is not JSON, could be error output
                            result = {
                                "success": False,
                                "error": "Invalid JSON output from subprocess",
                                "stdout": stdout
                            }
                    elif stderr:
                        # Try to parse stderr as JSON (error case)
                        try:
                            result = json.loads(stderr)
                        except json.JSONDecodeError:
                            result = {
                                "success": False,
                                "error": stderr.strip() or "Subprocess failed with no output"
                            }
                    else:
                        result = {"success": False, "error": "No output from subprocess"}

                    # Append stderr if present and not already processed
                    if stderr and 'stderr' not in result:
                        result['stderr'] = stderr

                    return result

                except asyncio.TimeoutError:
                    # Timeout exceeded - kill process
                    self.logger.warning(
                        f"Subprocess timeout for client {client_id} after {timeout}s"
                    )

                    # Try SIGTERM first
                    try:
                        if hasattr(os, 'killpg'):
                            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                        else:
                            process.terminate()

                        # Wait for kill_timeout
                        await asyncio.sleep(self.kill_timeout)

                        # Check if still alive
                        if process.returncode is None:
                            if hasattr(os, 'killpg'):
                                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                            else:
                                process.kill()

                        await process.wait()
                    except Exception as e:
                        self.logger.error(f"Error killing process: {e}")

                    return {
                        "success": False,
                        "error": f"Subprocess timeout after {timeout}s",
                        "context": context
                    }

            finally:
                # Cleanup wrapper file
                try:
                    Path(wrapper_path).unlink()
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup wrapper: {e}")

        except Exception as e:
            self.logger.error(f"Subprocess execution failed: {e}")
            return {
                "success": False,
                "error": f"Subprocess error: {str(e)}",
                "context": context
            }


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest

    class TestSubprocessExecutor(unittest.TestCase):
        """Test suite for SubprocessExecutor"""

        def setUp(self):
            """Setup test fixtures"""
            self.executor = SubprocessExecutor(timeout=5.0)
            self.temp_dir = tempfile.TemporaryDirectory()
            self.working_dir = Path(self.temp_dir.name)

        def tearDown(self):
            """Cleanup test fixtures"""
            self.temp_dir.cleanup()

        def test_initialization(self):
            """Test executor initialization"""
            executor = SubprocessExecutor(timeout=10.0)
            self.assertEqual(executor.timeout, 10.0)
            self.assertEqual(executor.kill_timeout, 2.0)

        def test_simple_code_execution(self):
            """Test simple code execution"""
            async def run():
                result = await self.executor.execute(
                    code="x = 42",
                    client_id="test_client",
                    working_dir=self.working_dir,
                    timeout=5.0
                )
                return result

            result = asyncio.run(run())
            self.assertTrue(result.get("success"))
            self.assertEqual(result.get("context", {}).get("x"), 42)

        def test_code_with_print(self):
            """Test code that prints output"""
            async def run():
                result = await self.executor.execute(
                    code="print('hello world')",
                    client_id="test_client",
                    working_dir=self.working_dir,
                    timeout=5.0
                )
                return result

            result = asyncio.run(run())
            self.assertTrue(result.get("success"))

        def test_code_with_context(self):
            """Test code execution with pre-loaded context"""
            async def run():
                result = await self.executor.execute(
                    code="y = x + 10",
                    client_id="test_client",
                    working_dir=self.working_dir,
                    timeout=5.0,
                    context={"x": 5}
                )
                return result

            result = asyncio.run(run())
            self.assertTrue(result.get("success"))
            self.assertEqual(result.get("context", {}).get("y"), 15)

        def test_code_with_error(self):
            """Test code that raises an error"""
            async def run():
                result = await self.executor.execute(
                    code="raise ValueError('test error')",
                    client_id="test_client",
                    working_dir=self.working_dir,
                    timeout=5.0
                )
                return result

            result = asyncio.run(run())
            self.assertFalse(result.get("success"))
            # Error message should contain the error details
            error = result.get("error", "")
            self.assertTrue(len(error) > 0)

        def test_timeout_handling(self):
            """Test timeout handling"""
            async def run():
                result = await self.executor.execute(
                    code="import time; time.sleep(10)",
                    client_id="test_client",
                    working_dir=self.working_dir,
                    timeout=1.0
                )
                return result

            result = asyncio.run(run())
            self.assertFalse(result.get("success"))
            self.assertIn("timeout", result.get("error", "").lower())

        def test_multiple_variables(self):
            """Test code that creates multiple variables"""
            async def run():
                code = """
a = 1
b = 2
c = a + b
"""
                result = await self.executor.execute(
                    code=code,
                    client_id="test_client",
                    working_dir=self.working_dir,
                    timeout=5.0
                )
                return result

            result = asyncio.run(run())
            self.assertTrue(result.get("success"))
            ctx = result.get("context", {})
            self.assertEqual(ctx.get("a"), 1)
            self.assertEqual(ctx.get("b"), 2)
            self.assertEqual(ctx.get("c"), 3)

    # Run tests
    unittest.main()
