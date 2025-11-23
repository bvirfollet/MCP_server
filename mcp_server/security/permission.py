"""
Permission Module - Represents a permission or access right

Module: security.permission
Date: 2025-11-23
Version: 0.2.0-alpha

CHANGELOG:
[2025-11-23 v0.2.0-alpha] Initial implementation
  - Permission dataclass for RBAC
  - Support for resource-scoped permissions
  - Pattern matching for file paths
  - Serialization for audit logging
  - Comparison operations

ARCHITECTURE:
Permission represents a single access right that can be granted to a client.
Examples:
  - FILE_READ on /app/data/*.txt
  - CODE_EXECUTION with restricted=true
  - SYSTEM_COMMAND with whitelist: ["ls", "grep"]

Used by PermissionManager for authorization checks.

SECURITY NOTES:
- Permissions are validated on creation
- Resource patterns support wildcards and glob
- Comparison operations check type and scope
- Serialization safe for logging/storage
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from enum import Enum
import fnmatch
import logging


class PermissionType(str, Enum):
    """Types de permissions disponibles"""

    # File operations
    FILE_READ = "FILE_READ"
    FILE_WRITE = "FILE_WRITE"
    FILE_DELETE = "FILE_DELETE"
    FILE_WRITE_GLOBAL = "FILE_WRITE_GLOBAL"

    # Code execution
    CODE_EXECUTION = "CODE_EXECUTION"
    CODE_EXECUTION_SUDO = "CODE_EXECUTION_SUDO"

    # System commands
    SYSTEM_COMMAND = "SYSTEM_COMMAND"

    # Network
    NETWORK_OUTBOUND = "NETWORK_OUTBOUND"
    NETWORK_LISTEN = "NETWORK_LISTEN"

    # Process
    PROCESS_SPAWN = "PROCESS_SPAWN"
    PROCESS_KILL = "PROCESS_KILL"


@dataclass
class Permission:
    """
    Represents a single permission/access right

    A permission grants access to a specific resource or capability.
    Supports wildcards for file patterns and whitelisting for commands.

    Attributes:
        type: Type of permission (FILE_READ, CODE_EXECUTION, etc.)
        resource: Optional resource identifier
                  - For FILE_*: file path or pattern (e.g., "/app/data/*.txt")
                  - For SYSTEM_COMMAND: command name (e.g., "ls", "grep")
                  - Can be list of strings for whitelists
        restricted: Whether execution is restricted
                    - For CODE_EXECUTION: if True, restrict imports
                    - For others: reserved for future use
        parameters: Additional parameters
                   - "max_size": max file size in bytes
                   - "timeout": execution timeout in seconds
                   - "commands": whitelist of allowed commands
    """

    type: PermissionType
    resource: Optional[str] = None
    restricted: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)

    logger = logging.getLogger("security.permission")

    def __post_init__(self):
        """Validate permission on creation"""
        self._validate()

    def _validate(self) -> None:
        """
        Validate permission is well-formed

        Raises:
            ValueError: If permission is invalid
        """
        # Ensure type is valid
        if not isinstance(self.type, PermissionType):
            try:
                self.type = PermissionType(self.type)
            except ValueError as e:
                raise ValueError(f"Invalid permission type: {self.type}") from e

        # Validate resource-specific rules
        if self.type.startswith("FILE_") and self.resource:
            if not isinstance(self.resource, str):
                raise ValueError(f"FILE_* permission requires string resource")

        if self.type == PermissionType.SYSTEM_COMMAND:
            if not self.resource:
                raise ValueError("SYSTEM_COMMAND requires resource (command name)")

    def matches(self, other: "Permission") -> bool:
        """
        Check if this permission grants the access required by other

        Supports wildcard matching for file paths.

        Args:
            other: Permission to check against

        Returns:
            bool: True if this permission covers other
        """
        # Type must match
        if self.type != other.type:
            return False

        # If self has no resource, it's wildcard (permits all)
        if self.resource is None:
            return True

        # If other has no resource, it needs unrestricted access
        if other.resource is None:
            return False

        # For file permissions, support wildcard patterns
        if self.type.startswith("FILE_"):
            return fnmatch.fnmatch(other.resource, self.resource)

        # For system commands, check if in whitelist
        if self.type == PermissionType.SYSTEM_COMMAND:
            if isinstance(self.resource, list):
                return other.resource in self.resource
            else:
                return self.resource == other.resource

        # Exact match for other types
        return self.resource == other.resource

    def can_execute(self) -> bool:
        """
        Check if this permission allows execution

        Returns:
            bool: True if this is an executable permission
        """
        executable_types = {
            PermissionType.CODE_EXECUTION,
            PermissionType.CODE_EXECUTION_SUDO,
            PermissionType.SYSTEM_COMMAND,
            PermissionType.PROCESS_SPAWN,
        }
        return self.type in executable_types

    def is_restricted(self) -> bool:
        """
        Check if execution is restricted

        For CODE_EXECUTION: True means imports are restricted
        For others: depends on permission type

        Returns:
            bool: True if restricted
        """
        if self.type == PermissionType.CODE_EXECUTION:
            return self.restricted
        if self.type == PermissionType.CODE_EXECUTION_SUDO:
            return True  # Always restricted

        return self.restricted

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize permission for logging/storage

        Returns:
            dict: Dictionary representation
        """
        return {
            "type": self.type.value,
            "resource": self.resource,
            "restricted": self.restricted,
            "parameters": self.parameters,
        }

    def __repr__(self) -> str:
        """String representation"""
        res_str = f":{self.resource}" if self.resource else ""
        restricted_str = "[RESTRICTED]" if self.restricted else ""
        return f"Permission({self.type.value}{res_str}) {restricted_str}".strip()

    def __eq__(self, other) -> bool:
        """Check equality"""
        if not isinstance(other, Permission):
            return False
        return (
            self.type == other.type
            and self.resource == other.resource
            and self.restricted == other.restricted
        )

    def __hash__(self) -> int:
        """Make hashable for use in sets"""
        return hash((self.type, self.resource, self.restricted))


# Pre-defined common permissions

# File permissions
READ_ALL_FILES = Permission(PermissionType.FILE_READ, "/*")
READ_APP_DATA = Permission(PermissionType.FILE_READ, "/app/data/*")
WRITE_APP_OUTPUT = Permission(PermissionType.FILE_WRITE, "/app/output/*")

# Code execution
EXECUTE_CODE_RESTRICTED = Permission(
    PermissionType.CODE_EXECUTION, restricted=True
)
EXECUTE_CODE_UNRESTRICTED = Permission(
    PermissionType.CODE_EXECUTION, restricted=False
)

# System commands (safe)
COMMAND_LS = Permission(PermissionType.SYSTEM_COMMAND, "ls")
COMMAND_GREP = Permission(PermissionType.SYSTEM_COMMAND, "grep")
COMMAND_ECHO = Permission(PermissionType.SYSTEM_COMMAND, "echo")

# Default minimal permissions
DEFAULT_PERMISSIONS = [
    READ_APP_DATA,
    COMMAND_LS,
    COMMAND_ECHO,
]


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest

    class TestPermission(unittest.TestCase):
        """Test suite for Permission"""

        def test_creation(self):
            """Test permission creation"""
            perm = Permission(PermissionType.FILE_READ, "/app/data/*.txt")
            self.assertEqual(perm.type, PermissionType.FILE_READ)
            self.assertEqual(perm.resource, "/app/data/*.txt")

        def test_invalid_type(self):
            """Test invalid permission type raises error"""
            with self.assertRaises(ValueError):
                Permission("INVALID_PERMISSION")

        def test_matches_exact(self):
            """Test exact permission matching"""
            perm1 = Permission(PermissionType.FILE_READ, "/app/data/file.txt")
            perm2 = Permission(PermissionType.FILE_READ, "/app/data/file.txt")
            self.assertTrue(perm1.matches(perm2))

        def test_matches_wildcard(self):
            """Test wildcard pattern matching"""
            grantor = Permission(PermissionType.FILE_READ, "/app/data/*.txt")
            required = Permission(PermissionType.FILE_READ, "/app/data/file.txt")
            self.assertTrue(grantor.matches(required))

        def test_matches_wildcard_no_match(self):
            """Test wildcard pattern no match"""
            grantor = Permission(PermissionType.FILE_READ, "/app/data/*.txt")
            required = Permission(PermissionType.FILE_READ, "/app/data/file.json")
            self.assertFalse(grantor.matches(required))

        def test_matches_different_type(self):
            """Test different types don't match"""
            perm1 = Permission(PermissionType.FILE_READ)
            perm2 = Permission(PermissionType.FILE_WRITE)
            self.assertFalse(perm1.matches(perm2))

        def test_matches_no_resource_wildcard(self):
            """Test no resource = wildcard"""
            grantor = Permission(PermissionType.FILE_READ)
            required = Permission(PermissionType.FILE_READ, "/any/path")
            self.assertTrue(grantor.matches(required))

        def test_system_command_whitelist(self):
            """Test system command whitelist matching"""
            perm1 = Permission(
                PermissionType.SYSTEM_COMMAND,
                resource=["ls", "grep", "echo"],
            )
            perm2 = Permission(PermissionType.SYSTEM_COMMAND, resource="ls")
            self.assertTrue(perm1.matches(perm2))

        def test_system_command_not_in_whitelist(self):
            """Test system command not in whitelist"""
            perm1 = Permission(
                PermissionType.SYSTEM_COMMAND,
                resource=["ls", "grep"],
            )
            perm2 = Permission(PermissionType.SYSTEM_COMMAND, resource="rm")
            self.assertFalse(perm1.matches(perm2))

        def test_can_execute(self):
            """Test executable permission detection"""
            self.assertTrue(
                Permission(PermissionType.CODE_EXECUTION).can_execute()
            )
            self.assertTrue(
                Permission(PermissionType.SYSTEM_COMMAND, resource="ls").can_execute()
            )
            self.assertFalse(Permission(PermissionType.FILE_READ).can_execute())

        def test_is_restricted(self):
            """Test restricted check"""
            perm_restricted = Permission(
                PermissionType.CODE_EXECUTION, restricted=True
            )
            perm_unrestricted = Permission(
                PermissionType.CODE_EXECUTION, restricted=False
            )
            self.assertTrue(perm_restricted.is_restricted())
            self.assertFalse(perm_unrestricted.is_restricted())

        def test_to_dict(self):
            """Test serialization"""
            perm = Permission(
                PermissionType.FILE_READ,
                "/app/data/*.txt",
                restricted=False,
                parameters={"max_size": 1024},
            )
            d = perm.to_dict()
            self.assertEqual(d["type"], "FILE_READ")
            self.assertEqual(d["resource"], "/app/data/*.txt")
            self.assertFalse(d["restricted"])
            self.assertEqual(d["parameters"]["max_size"], 1024)

        def test_equality(self):
            """Test permission equality"""
            perm1 = Permission(PermissionType.FILE_READ, "/app/data/*")
            perm2 = Permission(PermissionType.FILE_READ, "/app/data/*")
            perm3 = Permission(PermissionType.FILE_WRITE, "/app/data/*")

            self.assertEqual(perm1, perm2)
            self.assertNotEqual(perm1, perm3)

        def test_hashable(self):
            """Test permission can be used in sets"""
            perm1 = Permission(PermissionType.FILE_READ, "/app/data/*")
            perm2 = Permission(PermissionType.FILE_READ, "/app/data/*")
            perm_set = {perm1, perm2}
            self.assertEqual(len(perm_set), 1)

    unittest.main()
