"""
Safe Namespace - Restricted execution environment

Module: resources.safe_namespace
Date: 2025-11-23
Version: 0.2.0-alpha

CHANGELOG:
[2025-11-23 v0.2.0-alpha] Initial implementation
  - Whitelist of safe modules
  - Restricted builtins
  - AST-based code analysis (Phase 6)
  - Namespace creation utilities

ARCHITECTURE:
safe_namespace defines the restricted execution environment:
  - SAFE_MODULES: Allowed imports (json, math, re, etc.)
  - SAFE_BUILTINS: Allowed built-in functions
  - BLOCKED_PATTERNS: Dangerous code patterns to detect

Phase 2: Documentation and basic restrictions
Phase 6: Full enforcement with AST parsing and subprocess isolation

SECURITY NOTES:
- No dangerous modules (os, sys, subprocess)
- Limited builtins (no exec, eval, __import__)
- File operations restricted by permissions
- Network operations restricted by permissions
"""

import logging
from typing import Dict, Any, Set
import json
import math
import re
import datetime
import collections
import functools
import itertools

# ============================================================================
# Safe Modules
# ============================================================================

SAFE_MODULES = {
    "json": json,
    "math": math,
    "re": re,
    "datetime": datetime,
    "collections": collections,
    "functools": functools,
    "itertools": itertools,
}

# ============================================================================
# Safe Builtins
# ============================================================================

SAFE_BUILTINS = {
    # Type constructors
    "str",
    "int",
    "float",
    "bool",
    "list",
    "dict",
    "set",
    "tuple",
    "frozenset",
    "bytes",
    "bytearray",
    # Type checking
    "isinstance",
    "issubclass",
    "type",
    "hasattr",
    "getattr",
    "setattr",
    # Iteration
    "range",
    "enumerate",
    "zip",
    "map",
    "filter",
    "iter",
    "next",
    "reversed",
    # Aggregation
    "len",
    "sum",
    "min",
    "max",
    "any",
    "all",
    "sorted",
    # Math
    "abs",
    "round",
    "pow",
    "divmod",
    # Utilities
    "print",  # Captured for output
    "repr",
    "str",
    "format",
    "ord",
    "chr",
    "bin",
    "hex",
    "oct",
}

# ============================================================================
# Blocked Patterns
# ============================================================================

BLOCKED_IMPORTS = {
    "os",
    "sys",
    "subprocess",
    "shutil",
    "importlib",
    "pickle",
    "shelve",
    "socket",
    "urllib",
    "requests",
    "http",
    "ftplib",
    "smtplib",
    "telnetlib",
    "ctypes",
    "multiprocessing",
    "threading",
    "__builtin__",
    "__builtins__",
}

BLOCKED_BUILTINS = {
    "exec",
    "eval",
    "compile",
    "__import__",
    "open",  # Replaced with restricted version
    "input",  # No user input in tools
    "breakpoint",
    "globals",
    "locals",
    "vars",
    "dir",
}

BLOCKED_ATTRIBUTES = {
    "__dict__",
    "__class__",
    "__bases__",
    "__subclasses__",
    "__import__",
    "__loader__",
    "__spec__",
    "func_globals",
    "f_globals",
    "gi_frame",
    "cr_frame",
}

# ============================================================================
# Namespace Creation
# ============================================================================

def create_safe_namespace() -> Dict[str, Any]:
    """
    Create a safe execution namespace

    Returns a dictionary with:
    - Safe builtins
    - Safe modules available as imports
    - No access to dangerous functions

    Phase 2: Basic namespace with safe modules
    Phase 6: Full enforcement with restricted __import__

    Returns:
        dict: Safe namespace for code execution
    """
    # Build safe builtins dict
    import builtins

    safe_builtins_dict = {}
    for name in SAFE_BUILTINS:
        if hasattr(builtins, name):
            safe_builtins_dict[name] = getattr(builtins, name)

    # Create namespace
    namespace = {
        "__builtins__": safe_builtins_dict,
        # Pre-import safe modules
        "json": json,
        "math": math,
        "re": re,
        "datetime": datetime,
        "collections": collections,
        "functools": functools,
        "itertools": itertools,
    }

    return namespace


def is_safe_module(module_name: str) -> bool:
    """
    Check if module is in safe list

    Args:
        module_name: Name of module to check

    Returns:
        bool: True if module is safe to import
    """
    return module_name in SAFE_MODULES


def is_blocked_import(module_name: str) -> bool:
    """
    Check if module is blocked

    Args:
        module_name: Name of module to check

    Returns:
        bool: True if module is blocked
    """
    # Check exact match
    if module_name in BLOCKED_IMPORTS:
        return True

    # Check if starts with blocked module (e.g., os.path)
    for blocked in BLOCKED_IMPORTS:
        if module_name.startswith(f"{blocked}."):
            return True

    return False


def validate_code_safety(code: str) -> tuple[bool, list[str]]:
    """
    Validate code for safety (basic check)

    Phase 2: Simple string-based checks
    Phase 6: Full AST parsing and validation

    Args:
        code: Python code to validate

    Returns:
        tuple: (is_safe, list_of_issues)
    """
    issues = []

    # Check for blocked imports (simple string search)
    for blocked in BLOCKED_IMPORTS:
        if f"import {blocked}" in code or f"from {blocked}" in code:
            issues.append(f"Blocked import detected: {blocked}")

    # Check for blocked builtins
    for blocked in BLOCKED_BUILTINS:
        if f"{blocked}(" in code:
            issues.append(f"Blocked builtin detected: {blocked}")

    # Check for attribute access to dangerous attributes
    for blocked_attr in BLOCKED_ATTRIBUTES:
        if blocked_attr in code:
            issues.append(f"Blocked attribute access: {blocked_attr}")

    is_safe = len(issues) == 0
    return is_safe, issues


# ============================================================================
# Resource Limits (Phase 2: Documentation)
# ============================================================================

DEFAULT_LIMITS = {
    "max_execution_time_seconds": 30,
    "max_memory_mb": 512,
    "max_file_size_mb": 10,
    "max_open_files": 10,
    "max_output_size_kb": 100,
}


def get_default_limits() -> Dict[str, int]:
    """
    Get default resource limits

    Returns:
        dict: Resource limits
    """
    return DEFAULT_LIMITS.copy()


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest

    class TestSafeNamespace(unittest.TestCase):
        """Test suite for safe namespace"""

        def test_safe_modules_available(self):
            """Test that safe modules are available"""
            self.assertIn("json", SAFE_MODULES)
            self.assertIn("math", SAFE_MODULES)
            self.assertIn("re", SAFE_MODULES)

        def test_dangerous_modules_blocked(self):
            """Test that dangerous modules are blocked"""
            self.assertIn("os", BLOCKED_IMPORTS)
            self.assertIn("sys", BLOCKED_IMPORTS)
            self.assertIn("subprocess", BLOCKED_IMPORTS)

        def test_safe_builtins_present(self):
            """Test safe builtins are in whitelist"""
            self.assertIn("str", SAFE_BUILTINS)
            self.assertIn("int", SAFE_BUILTINS)
            self.assertIn("len", SAFE_BUILTINS)
            self.assertIn("print", SAFE_BUILTINS)

        def test_dangerous_builtins_blocked(self):
            """Test dangerous builtins are blocked"""
            self.assertIn("exec", BLOCKED_BUILTINS)
            self.assertIn("eval", BLOCKED_BUILTINS)
            self.assertIn("__import__", BLOCKED_BUILTINS)

        def test_create_safe_namespace(self):
            """Test creating safe namespace"""
            namespace = create_safe_namespace()

            self.assertIn("__builtins__", namespace)
            self.assertIn("json", namespace)
            self.assertIn("math", namespace)

            # Check that dangerous functions are not available
            builtins_dict = namespace["__builtins__"]
            self.assertNotIn("exec", builtins_dict)
            self.assertNotIn("eval", builtins_dict)

        def test_is_safe_module(self):
            """Test safe module checking"""
            self.assertTrue(is_safe_module("json"))
            self.assertTrue(is_safe_module("math"))
            self.assertFalse(is_safe_module("os"))
            self.assertFalse(is_safe_module("subprocess"))

        def test_is_blocked_import(self):
            """Test blocked import checking"""
            self.assertTrue(is_blocked_import("os"))
            self.assertTrue(is_blocked_import("os.path"))
            self.assertTrue(is_blocked_import("subprocess"))
            self.assertFalse(is_blocked_import("json"))
            self.assertFalse(is_blocked_import("math"))

        def test_validate_code_safety_safe(self):
            """Test code validation with safe code"""
            safe_code = """
import json
import math

result = json.dumps({"value": math.pi})
print(result)
"""
            is_safe, issues = validate_code_safety(safe_code)
            self.assertTrue(is_safe)
            self.assertEqual(len(issues), 0)

        def test_validate_code_safety_blocked_import(self):
            """Test code validation with blocked import"""
            unsafe_code = "import os\nos.system('ls')"
            is_safe, issues = validate_code_safety(unsafe_code)
            self.assertFalse(is_safe)
            self.assertGreater(len(issues), 0)

        def test_validate_code_safety_blocked_builtin(self):
            """Test code validation with blocked builtin"""
            unsafe_code = "eval('print(1)')"
            is_safe, issues = validate_code_safety(unsafe_code)
            self.assertFalse(is_safe)
            self.assertGreater(len(issues), 0)

        def test_validate_code_safety_blocked_attribute(self):
            """Test code validation with blocked attribute"""
            unsafe_code = "x.__class__.__bases__"
            is_safe, issues = validate_code_safety(unsafe_code)
            self.assertFalse(is_safe)
            self.assertGreater(len(issues), 0)

        def test_get_default_limits(self):
            """Test getting default limits"""
            limits = get_default_limits()
            self.assertIn("max_execution_time_seconds", limits)
            self.assertIn("max_memory_mb", limits)
            self.assertEqual(limits["max_execution_time_seconds"], 30)
            self.assertEqual(limits["max_memory_mb"], 512)

        def test_namespace_isolation(self):
            """Test that created namespaces are isolated"""
            ns1 = create_safe_namespace()
            ns2 = create_safe_namespace()

            ns1["custom_var"] = "value1"
            self.assertNotIn("custom_var", ns2)

    unittest.main()
