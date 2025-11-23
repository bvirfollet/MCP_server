"""
Client Context - Represents the security context of a connected client

Module: security.client_context
Date: 2025-11-23
Version: 0.1.0-alpha

CHANGELOG:
[2025-11-23 v0.1.0-alpha] Initial implementation
  - Basic client context (Phase 1 - minimal)
  - Client ID and metadata
  - Temporary anonymous clients for Phase 1
  - Framework for future authentication

ARCHITECTURE:
ClientContext represents a connected client and maintains:
- Client identity and metadata
- Request count and timestamps
- Future: authentication info, permissions, sandbox info

Phase 1: Minimal context for basic connectivity
Phase 3+: Full auth, permissions, sandbox info

SECURITY NOTES:
- Phase 1: No authentication (messages are not secured)
- Phase 3+: JWT/mTLS authentication will be added
- All clients tracked for audit logging
- Metadata is immutable after creation
"""

import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


@dataclass
class ClientMetadata:
    """
    Metadata about a client

    Attributes:
        client_id: Unique client identifier
        created_at: When client connected
        last_activity: Last message time
        request_count: Number of requests processed
        client_info: Custom client metadata (name, version, etc.)
    """
    client_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    request_count: int = 0
    client_info: Dict[str, Any] = field(default_factory=dict)

    def update_activity(self) -> None:
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()

    def increment_request_count(self) -> None:
        """Increment request counter"""
        self.request_count += 1


class ClientContext:
    """
    Security context for a connected client

    Represents the current session of a client connected to the MCP server.

    In Phase 1:
    - All clients are treated equally
    - No authentication or authorization
    - Used for request tracking and audit logging

    In Phase 3+:
    - Full authentication and authorization
    - Permissions checking
    - Resource quotas and isolation
    """

    def __init__(
        self,
        client_info: Optional[Dict[str, Any]] = None,
        client_id: Optional[str] = None
    ):
        """
        Initialize client context

        Args:
            client_info: Optional client metadata (name, version, etc.)
            client_id: Optional pre-existing client ID (for authenticated clients)
        """
        self.logger = logging.getLogger("security.client_context")

        # Create metadata with optional client_id
        metadata_client_id = client_id if client_id else str(uuid.uuid4())
        self.metadata = ClientMetadata(
            client_id=metadata_client_id,
            client_info=client_info or {}
        )

        # Phase 1: No authentication, so these are always None
        self._authenticated = False
        self._auth_token: Optional[str] = None

        # Phase 3: Authentication fields (JWT)
        self.authenticated: bool = False
        self.user_id: Optional[str] = None
        self.username: Optional[str] = None
        self.roles: List[str] = []
        self.auth_time: Optional[datetime] = None
        self.token_jti: Optional[str] = None

    @property
    def client_id(self) -> str:
        """Get unique client ID"""
        return self.metadata.client_id

    @property
    def is_authenticated(self) -> bool:
        """Check if client is authenticated (Phase 3+)"""
        return self._authenticated

    @property
    def auth_token(self) -> Optional[str]:
        """Get auth token if authenticated (Phase 3+)"""
        return self._auth_token

    @property
    def request_count(self) -> int:
        """Get number of requests from this client"""
        return self.metadata.request_count

    def record_request(self) -> None:
        """Record that a request was received from this client"""
        self.metadata.increment_request_count()
        self.metadata.update_activity()

    def get_info(self) -> Dict[str, Any]:
        """
        Get client information for logging/debugging

        Returns:
            dict: Client information
        """
        return {
            "client_id": self.client_id,
            "created_at": self.metadata.created_at.isoformat(),
            "last_activity": self.metadata.last_activity.isoformat(),
            "request_count": self.request_count,
            "authenticated": self.is_authenticated or self.authenticated,
            "info": self.metadata.client_info,
            # Phase 3: Authentication info
            "user_id": self.user_id,
            "username": self.username,
            "roles": self.roles,
            "auth_time": self.auth_time.isoformat() if self.auth_time else None,
        }

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"ClientContext("
            f"id={self.client_id[:8]}..., "
            f"auth={self.is_authenticated}, "
            f"requests={self.request_count}"
            f")"
        )


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    from unittest.mock import patch

    class TestClientMetadata(unittest.TestCase):
        """Test suite for ClientMetadata"""

        def test_initialization(self):
            """Test metadata initialization"""
            metadata = ClientMetadata()
            self.assertIsNotNone(metadata.client_id)
            self.assertIsNotNone(metadata.created_at)
            self.assertEqual(metadata.request_count, 0)
            self.assertEqual(metadata.client_info, {})

        def test_with_custom_info(self):
            """Test metadata with custom client info"""
            info = {"name": "test-client", "version": "1.0"}
            metadata = ClientMetadata(client_info=info)
            self.assertEqual(metadata.client_info, info)

        def test_client_id_is_unique(self):
            """Test each metadata gets unique client ID"""
            m1 = ClientMetadata()
            m2 = ClientMetadata()
            self.assertNotEqual(m1.client_id, m2.client_id)

        def test_update_activity(self):
            """Test updating activity timestamp"""
            metadata = ClientMetadata()
            original_activity = metadata.last_activity

            # Wait a tiny bit
            import time
            time.sleep(0.01)

            metadata.update_activity()
            self.assertGreater(metadata.last_activity, original_activity)

        def test_increment_request_count(self):
            """Test incrementing request count"""
            metadata = ClientMetadata()
            self.assertEqual(metadata.request_count, 0)

            metadata.increment_request_count()
            self.assertEqual(metadata.request_count, 1)

            metadata.increment_request_count()
            self.assertEqual(metadata.request_count, 2)

    class TestClientContext(unittest.TestCase):
        """Test suite for ClientContext"""

        def test_initialization(self):
            """Test context initialization"""
            context = ClientContext()
            self.assertIsNotNone(context.client_id)
            self.assertFalse(context.is_authenticated)
            self.assertIsNone(context.auth_token)
            self.assertEqual(context.request_count, 0)

        def test_with_custom_info(self):
            """Test context with custom info"""
            info = {"name": "test-ai", "version": "2.0"}
            context = ClientContext(client_info=info)
            self.assertEqual(context.metadata.client_info, info)

        def test_record_request(self):
            """Test recording request"""
            context = ClientContext()
            self.assertEqual(context.request_count, 0)

            context.record_request()
            self.assertEqual(context.request_count, 1)

            context.record_request()
            context.record_request()
            self.assertEqual(context.request_count, 3)

        def test_record_request_updates_activity(self):
            """Test recording request updates activity"""
            context = ClientContext()
            original_activity = context.metadata.last_activity

            import time
            time.sleep(0.01)

            context.record_request()
            self.assertGreater(context.metadata.last_activity, original_activity)

        def test_get_info(self):
            """Test getting client info"""
            context = ClientContext(client_info={"name": "test"})
            info = context.get_info()

            self.assertIn("client_id", info)
            self.assertIn("created_at", info)
            self.assertIn("last_activity", info)
            self.assertIn("request_count", info)
            self.assertIn("authenticated", info)
            self.assertIn("info", info)
            self.assertFalse(info["authenticated"])

        def test_repr(self):
            """Test string representation"""
            context = ClientContext()
            repr_str = repr(context)
            self.assertIn("ClientContext", repr_str)
            self.assertIn("auth=False", repr_str)

        def test_multiple_contexts_different_ids(self):
            """Test multiple contexts have different IDs"""
            c1 = ClientContext()
            c2 = ClientContext()
            self.assertNotEqual(c1.client_id, c2.client_id)

    # Run tests
    unittest.main()
