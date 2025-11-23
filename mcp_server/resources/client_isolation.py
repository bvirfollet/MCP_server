#!/usr/bin/env python3
"""
Client Isolation Manager for Phase 6 - Directory Isolation

Module: resources.client_isolation
Date: 2025-11-23
Version: 0.1.0-alpha (Phase 6)

CHANGELOG:
[2025-11-23 v0.1.0-alpha] Client Isolation Manager Implementation
  - Create isolated directory per client
  - Map relative paths to client directories
  - Validate access to files (same client vs cross-client)
  - Support FILE_READ_CROSS_CLIENT and FILE_WRITE_CROSS_CLIENT permissions
  - Block path traversal attacks
  - List and clear client files

ARCHITECTURE:
ClientIsolationManager ensures each client operates in its own directory.
- Each client has: data/clients/{client_id}/
- Relative paths are mapped to client's directory
- Absolute paths blocked unless cross-client permission
- Path traversal (../) blocked with strict validation
- Compatible with SubprocessExecutor for working_dir isolation

SECURITY NOTES:
- Paths normalized and validated to prevent escape attempts
- Cross-client access requires specific permission
- Audit trail for cross-client access
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, Set


logger = logging.getLogger(__name__)


class ClientIsolationManager:
    """
    Manages client directory isolation and path validation.

    Each client gets an isolated directory where they can read/write files.
    Cross-client access is blocked by default but can be enabled with permissions.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize ClientIsolationManager.

        Args:
            base_dir: Base directory for client isolation (default: data/clients)
        """
        self.base_dir = Path(base_dir) if base_dir else Path("data/clients")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("resources.client_isolation")
        self.logger.info(f"Client isolation directory: {self.base_dir}")

    def get_client_directory(self, client_id: str) -> Path:
        """
        Get isolated directory for a client.

        Args:
            client_id: ID of the client

        Returns:
            Path: Absolute path to client's directory (data/clients/{client_id}/)

        Note: Creates directory if it doesn't exist
        """
        client_dir = self.base_dir / client_id
        client_dir.mkdir(parents=True, exist_ok=True)
        self.logger.debug(f"Client directory for {client_id}: {client_dir}")
        return client_dir

    def resolve_path(
        self,
        client_id: str,
        relative_path: str
    ) -> Path:
        """
        Resolve a relative path to absolute within client's directory.

        Args:
            client_id: ID of the client
            relative_path: Relative path requested (e.g., "data.txt", "files/doc.pdf")

        Returns:
            Path: Absolute path within client's directory

        Raises:
            ValueError: If path is absolute or attempts escape (../)
        """
        # Get client directory
        client_dir = self.get_client_directory(client_id)

        # Check if path is absolute
        if Path(relative_path).is_absolute():
            raise ValueError(
                f"Absolute paths not allowed: {relative_path}. "
                f"Must be relative path within client directory."
            )

        # Normalize path (remove ., .., etc.)
        # Convert to string for normalization
        path_str = str(Path(relative_path))

        # Check for directory traversal attempts
        if ".." in path_str or path_str.startswith("/"):
            raise ValueError(
                f"Path traversal not allowed: {relative_path}. "
                f"Cannot use .. or absolute paths."
            )

        # Resolve within client directory
        resolved = (client_dir / relative_path).resolve()

        # Verify resolved path is still within client directory
        try:
            resolved.relative_to(client_dir)
        except ValueError:
            raise ValueError(
                f"Path escape detected: {relative_path} resolves outside "
                f"client directory {client_dir}"
            )

        self.logger.debug(
            f"Resolved path for {client_id}: {relative_path} → {resolved}"
        )
        return resolved

    def validate_access(
        self,
        client_id: str,
        target_path: Path,
        action: str = "read",
        cross_client_permission: bool = False
    ) -> bool:
        """
        Validate if client can access a file.

        Args:
            client_id: ID of the client requesting access
            target_path: Absolute path to the file
            action: "read" or "write"
            cross_client_permission: Whether client has FILE_READ/WRITE_CROSS_CLIENT perm

        Returns:
            bool: True if access allowed

        Logic:
        - If target in client's directory: always allow (with read/write permission)
        - If target NOT in client's directory:
          - Require cross_client_permission flag
          - Still log for audit trail
        """
        client_dir = self.get_client_directory(client_id)
        target_path = Path(target_path).resolve()

        # Check if target is within client's directory
        try:
            target_path.relative_to(client_dir)
            # Inside client directory - access allowed
            self.logger.info(
                f"Access allowed: {client_id} → {target_path} (own directory)"
            )
            return True
        except ValueError:
            # Outside client directory - need cross-client permission
            if not cross_client_permission:
                self.logger.warning(
                    f"Access denied: {client_id} → {target_path} "
                    f"(no cross-client permission)"
                )
                return False

            # Cross-client permission granted - allow but audit
            self.logger.warning(
                f"Cross-client access: {client_id} → {target_path} "
                f"(CROSS_CLIENT permission granted)"
            )
            return True

    def list_client_files(self, client_id: str) -> list:
        """
        List all files in a client's directory.

        Args:
            client_id: ID of the client

        Returns:
            List[Path]: All files and directories in client's directory
        """
        client_dir = self.get_client_directory(client_id)
        if not client_dir.exists():
            return []

        files = []
        for item in client_dir.rglob("*"):
            if item.is_file():
                files.append(item)

        self.logger.debug(f"Listed {len(files)} files for {client_id}")
        return files

    def clear_client_directory(self, client_id: str) -> None:
        """
        Clear all files in a client's directory.

        Args:
            client_id: ID of the client

        Note: Called on client logout or reset
        """
        client_dir = self.get_client_directory(client_id)

        if not client_dir.exists():
            self.logger.info(f"Client directory doesn't exist: {client_dir}")
            return

        # Remove all files
        import shutil
        try:
            shutil.rmtree(client_dir)
            self.logger.info(f"Cleared client directory: {client_dir}")
        except Exception as e:
            self.logger.error(f"Failed to clear client directory: {e}")

    @staticmethod
    def validate_path_safety(path_str: str) -> bool:
        """
        Quick validation that a path is safe (no traversal).

        Args:
            path_str: Path string to validate

        Returns:
            bool: True if path is safe
        """
        dangerous_patterns = ["..", "//", "\\\\", "\x00"]
        for pattern in dangerous_patterns:
            if pattern in path_str:
                return False
        return True


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    import tempfile
    import shutil

    class TestClientIsolationManager(unittest.TestCase):
        """Test suite for ClientIsolationManager"""

        def setUp(self):
            """Setup test fixtures"""
            self.temp_dir = tempfile.TemporaryDirectory()
            self.manager = ClientIsolationManager(Path(self.temp_dir.name))

        def tearDown(self):
            """Cleanup test fixtures"""
            self.temp_dir.cleanup()

        def test_initialization(self):
            """Test manager initialization"""
            manager = ClientIsolationManager(Path(self.temp_dir.name))
            self.assertTrue(manager.base_dir.exists())

        def test_create_client_directory(self):
            """Test client directory creation"""
            client_dir = self.manager.get_client_directory("alice_123")
            self.assertTrue(client_dir.exists())
            self.assertEqual(client_dir.name, "alice_123")

        def test_resolve_path_simple(self):
            """Test simple path resolution"""
            resolved = self.manager.resolve_path("alice_123", "data.txt")
            expected = self.manager.base_dir / "alice_123" / "data.txt"
            self.assertEqual(resolved, expected)

        def test_resolve_path_nested(self):
            """Test nested path resolution"""
            resolved = self.manager.resolve_path("alice_123", "files/subfolder/doc.pdf")
            expected = self.manager.base_dir / "alice_123" / "files/subfolder/doc.pdf"
            self.assertEqual(resolved, expected)

        def test_resolve_path_absolute_rejected(self):
            """Test that absolute paths are rejected"""
            with self.assertRaises(ValueError):
                self.manager.resolve_path("alice_123", "/etc/passwd")

        def test_resolve_path_traversal_rejected(self):
            """Test that path traversal is rejected"""
            with self.assertRaises(ValueError):
                self.manager.resolve_path("alice_123", "../../etc/passwd")

        def test_validate_access_own_file(self):
            """Test access to own file is allowed"""
            own_path = self.manager.resolve_path("alice_123", "data.txt")
            allowed = self.manager.validate_access(
                "alice_123",
                own_path,
                action="read",
                cross_client_permission=False
            )
            self.assertTrue(allowed)

        def test_validate_access_other_file_denied(self):
            """Test access to other client's file is denied"""
            bob_path = self.manager.resolve_path("bob_456", "secret.txt")
            allowed = self.manager.validate_access(
                "alice_123",
                bob_path,
                action="read",
                cross_client_permission=False
            )
            self.assertFalse(allowed)

        def test_validate_access_cross_client_allowed(self):
            """Test cross-client access with permission is allowed"""
            bob_path = self.manager.resolve_path("bob_456", "secret.txt")
            allowed = self.manager.validate_access(
                "alice_123",
                bob_path,
                action="read",
                cross_client_permission=True
            )
            self.assertTrue(allowed)

        def test_list_client_files(self):
            """Test listing client files"""
            # Create some files
            client_dir = self.manager.get_client_directory("alice_123")
            (client_dir / "file1.txt").touch()
            (client_dir / "file2.txt").touch()

            files = self.manager.list_client_files("alice_123")
            self.assertEqual(len(files), 2)

    # Run tests
    unittest.main()
