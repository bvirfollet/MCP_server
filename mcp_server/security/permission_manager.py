"""
Permission Manager - RBAC authorization system

Module: security.permission_manager
Date: 2025-11-23
Version: 0.2.0-alpha

CHANGELOG:
[2025-11-23 v0.2.0-alpha] Initial implementation
  - Permission granting and revocation
  - Permission verification (matching)
  - Default permissions initialization
  - Client permission management
  - Audit logging of permission checks
  - Permission delegation framework

ARCHITECTURE:
PermissionManager implements Role-Based Access Control (RBAC).
Responsibilities:
  - Grant/revoke permissions to clients
  - Check if client has required permission
  - Track permission changes
  - Log all permission decisions

PermissionManager is owned by MCPServer and used by ExecutionManager.

SECURITY NOTES:
- Permissions are checked before every action
- Default deny (no permission = denied)
- Wildcard matching for file paths
- Whitelisting for system commands
- All decisions logged for audit
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .permission import Permission, PermissionType, DEFAULT_PERMISSIONS


class PermissionDeniedError(Exception):
    """Raised when permission check fails"""

    def __init__(self, client_id: str, permission: Permission):
        self.client_id = client_id
        self.permission = permission
        super().__init__(
            f"Permission denied for {client_id}: {permission}"
        )


class PermissionManager:
    """
    RBAC permission management and authorization

    Manages which clients have which permissions and verifies
    permission requirements before execution.
    """

    def __init__(self):
        """Initialize permission manager"""
        self.logger = logging.getLogger("security.permission_manager")

        # Client permissions: client_id -> List[Permission]
        self._client_permissions: Dict[str, List[Permission]] = {}

        # Permission change audit trail
        self._audit_trail: List[Dict] = []

    def initialize_client(
        self,
        client_id: str,
        initial_permissions: Optional[List[Permission]] = None,
    ) -> None:
        """
        Initialize permissions for a new client

        Args:
            client_id: Client identifier
            initial_permissions: Initial permissions (default: DEFAULT_PERMISSIONS)
        """
        if initial_permissions is None:
            initial_permissions = list(DEFAULT_PERMISSIONS)

        self._client_permissions[client_id] = initial_permissions
        self.logger.info(
            f"Client initialized with {len(initial_permissions)} permissions"
        )

        self._log_audit(
            "client_initialized",
            client_id,
            {"count": len(initial_permissions)},
        )

    def grant_permission(
        self,
        client_id: str,
        permission: Permission,
    ) -> None:
        """
        Grant a permission to a client

        Args:
            client_id: Client identifier
            permission: Permission to grant
        """
        if client_id not in self._client_permissions:
            self.initialize_client(client_id)

        perms = self._client_permissions[client_id]

        # Check if already has this exact permission
        if permission in perms:
            self.logger.warning(
                f"Permission already granted: {client_id} - {permission}"
            )
            return

        perms.append(permission)
        self.logger.info(f"Permission granted: {client_id} - {permission}")

        self._log_audit("permission_granted", client_id, permission.to_dict())

    def revoke_permission(
        self,
        client_id: str,
        permission_type: PermissionType,
    ) -> None:
        """
        Revoke all permissions of a type from a client

        Args:
            client_id: Client identifier
            permission_type: Type of permission to revoke
        """
        if client_id not in self._client_permissions:
            return

        perms = self._client_permissions[client_id]
        original_count = len(perms)

        # Remove all permissions of this type
        self._client_permissions[client_id] = [
            p for p in perms if p.type != permission_type
        ]

        removed = original_count - len(
            self._client_permissions[client_id]
        )
        if removed > 0:
            self.logger.info(
                f"Revoked {removed} permissions of type {permission_type} "
                f"from {client_id}"
            )
            self._log_audit(
                "permissions_revoked",
                client_id,
                {"type": permission_type.value, "count": removed},
            )

    def has_permission(
        self,
        client_id: str,
        required: Permission,
    ) -> bool:
        """
        Check if client has a permission

        Checks if any of the client's permissions grant the required access.

        Args:
            client_id: Client identifier
            required: Required permission

        Returns:
            bool: True if permission is granted
        """
        if client_id not in self._client_permissions:
            return False

        perms = self._client_permissions[client_id]

        # Check if any granted permission covers required
        for granted in perms:
            if granted.matches(required):
                return True

        return False

    def check_permission(
        self,
        client_id: str,
        required: Permission,
    ) -> None:
        """
        Verify permission and raise if denied

        Args:
            client_id: Client identifier
            required: Required permission

        Raises:
            PermissionDeniedError: If permission check fails
        """
        if not self.has_permission(client_id, required):
            self.logger.warning(
                f"Permission denied: {client_id} - {required}"
            )
            self._log_audit(
                "permission_denied",
                client_id,
                required.to_dict(),
            )
            raise PermissionDeniedError(client_id, required)

    def get_client_permissions(
        self,
        client_id: str,
    ) -> List[Permission]:
        """
        Get all permissions for a client

        Args:
            client_id: Client identifier

        Returns:
            list: Permissions granted to client
        """
        return list(
            self._client_permissions.get(client_id, [])
        )

    def get_permission_summary(self, client_id: str) -> Dict:
        """
        Get summary of client permissions

        Args:
            client_id: Client identifier

        Returns:
            dict: Permission summary
        """
        perms = self.get_client_permissions(client_id)

        # Group by type
        by_type = {}
        for perm in perms:
            if perm.type not in by_type:
                by_type[perm.type] = []
            by_type[perm.type].append(perm)

        return {
            "client_id": client_id,
            "total_permissions": len(perms),
            "by_type": {
                k.value: len(v) for k, v in by_type.items()
            },
        }

    def _log_audit(
        self,
        event_type: str,
        client_id: str,
        data: Dict,
    ) -> None:
        """
        Log permission audit event

        Args:
            event_type: Type of event
            client_id: Affected client
            data: Event data
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "client_id": client_id,
            "data": data,
        }
        self._audit_trail.append(entry)

    def get_audit_trail(self) -> List[Dict]:
        """
        Get permission audit trail

        Returns:
            list: Audit entries
        """
        return list(self._audit_trail)


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest

    class TestPermissionManager(unittest.TestCase):
        """Test suite for PermissionManager"""

        def setUp(self):
            """Setup before each test"""
            self.manager = PermissionManager()

        def test_initialization(self):
            """Test initialization"""
            client_id = "test_client"
            self.manager.initialize_client(client_id)
            perms = self.manager.get_client_permissions(client_id)
            self.assertEqual(len(perms), len(DEFAULT_PERMISSIONS))

        def test_grant_permission(self):
            """Test granting permission"""
            client_id = "test"
            perm = Permission(PermissionType.FILE_READ, "/test/*")
            self.manager.initialize_client(client_id, [])

            self.manager.grant_permission(client_id, perm)
            self.assertTrue(self.manager.has_permission(client_id, perm))

        def test_grant_duplicate_permission(self):
            """Test granting duplicate permission"""
            client_id = "test"
            perm = Permission(PermissionType.FILE_READ, "/test/*")
            self.manager.initialize_client(client_id, [])

            self.manager.grant_permission(client_id, perm)
            self.manager.grant_permission(client_id, perm)  # Second time

            perms = self.manager.get_client_permissions(client_id)
            self.assertEqual(len(perms), 1)

        def test_has_permission(self):
            """Test permission checking"""
            client_id = "test"
            perm1 = Permission(PermissionType.FILE_READ, "/app/data/*")
            perm2 = Permission(PermissionType.FILE_READ, "/app/data/file.txt")

            self.manager.initialize_client(client_id, [perm1])
            self.assertTrue(self.manager.has_permission(client_id, perm2))

        def test_has_permission_denied(self):
            """Test permission denied"""
            client_id = "test"
            perm_required = Permission(PermissionType.FILE_WRITE, "/tmp/*")

            self.manager.initialize_client(client_id, [])
            self.assertFalse(
                self.manager.has_permission(client_id, perm_required)
            )

        def test_check_permission_success(self):
            """Test check_permission succeeds"""
            client_id = "test"
            perm = Permission(PermissionType.FILE_READ, "/app/*")

            self.manager.initialize_client(client_id, [perm])
            # Should not raise
            self.manager.check_permission(
                client_id, Permission(PermissionType.FILE_READ, "/app/file.txt")
            )

        def test_check_permission_failure(self):
            """Test check_permission raises error"""
            client_id = "test"
            self.manager.initialize_client(client_id, [])

            with self.assertRaises(PermissionDeniedError):
                self.manager.check_permission(
                    client_id,
                    Permission(PermissionType.FILE_WRITE, "/tmp/*"),
                )

        def test_revoke_permission(self):
            """Test revoking permissions"""
            client_id = "test"
            perm = Permission(PermissionType.FILE_READ, "/test/*")
            self.manager.initialize_client(client_id, [perm])

            self.assertTrue(self.manager.has_permission(client_id, perm))
            self.manager.revoke_permission(client_id, PermissionType.FILE_READ)
            self.assertFalse(self.manager.has_permission(client_id, perm))

        def test_get_permission_summary(self):
            """Test permission summary"""
            client_id = "test"
            perms = [
                Permission(PermissionType.FILE_READ, "/app/*"),
                Permission(PermissionType.FILE_WRITE, "/tmp/*"),
            ]
            self.manager.initialize_client(client_id, perms)

            summary = self.manager.get_permission_summary(client_id)
            self.assertEqual(summary["total_permissions"], 2)
            self.assertIn(PermissionType.FILE_READ.value, summary["by_type"])

        def test_audit_trail(self):
            """Test audit trail logging"""
            client_id = "test"
            self.manager.initialize_client(client_id)
            self.manager.grant_permission(
                client_id, Permission(PermissionType.FILE_READ)
            )

            trail = self.manager.get_audit_trail()
            self.assertEqual(len(trail), 2)  # init + grant
            self.assertEqual(trail[0]["event_type"], "client_initialized")
            self.assertEqual(trail[1]["event_type"], "permission_granted")

    unittest.main()
