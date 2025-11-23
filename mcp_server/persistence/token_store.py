"""
Token Manager - Token persistence and revocation

Module: persistence.token_store
Date: 2025-11-23
Version: 0.3.0-alpha

CHANGELOG:
[2025-11-23 v0.3.0-alpha] Initial implementation
  - Token storage in tokens.json
  - Token revocation support
  - Expiration handling
  - Blacklist checking

ARCHITECTURE:
TokenManager provides:
  - Persistent token registry
  - Token hashing for comparison
  - Revocation tracking (blacklist)
  - Automatic cleanup of expired tokens
"""

import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pathlib import Path

from .json_store import JSONStore, JSONStoreError


class TokenStoreError(Exception):
    """Base token store error"""
    pass


class TokenNotFoundError(TokenStoreError):
    """Token not found in store"""
    pass


class TokenRevoked(TokenStoreError):
    """Token has been revoked"""
    pass


class TokenRecord:
    """Represents a stored token record"""

    def __init__(
        self,
        jti: str,
        client_id: str,
        username: str,
        access_token_hash: str,
        refresh_token_hash: str,
        created_at: datetime,
        access_expires_at: datetime,
        refresh_expires_at: datetime,
        revoked: bool = False,
        revoked_at: Optional[datetime] = None,
    ):
        self.jti = jti
        self.client_id = client_id
        self.username = username
        self.access_token_hash = access_token_hash
        self.refresh_token_hash = refresh_token_hash
        self.created_at = created_at
        self.access_expires_at = access_expires_at
        self.refresh_expires_at = refresh_expires_at
        self.revoked = revoked
        self.revoked_at = revoked_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage"""
        return {
            "jti": self.jti,
            "client_id": self.client_id,
            "username": self.username,
            "access_token_hash": self.access_token_hash,
            "refresh_token_hash": self.refresh_token_hash,
            "created_at": self.created_at.isoformat(),
            "access_expires_at": self.access_expires_at.isoformat(),
            "refresh_expires_at": self.refresh_expires_at.isoformat(),
            "revoked": self.revoked,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenRecord":
        """Create from dictionary (from JSON)"""
        return cls(
            jti=data["jti"],
            client_id=data["client_id"],
            username=data["username"],
            access_token_hash=data["access_token_hash"],
            refresh_token_hash=data["refresh_token_hash"],
            created_at=datetime.fromisoformat(data["created_at"]),
            access_expires_at=datetime.fromisoformat(data["access_expires_at"]),
            refresh_expires_at=datetime.fromisoformat(data["refresh_expires_at"]),
            revoked=data.get("revoked", False),
            revoked_at=datetime.fromisoformat(data["revoked_at"]) if data.get("revoked_at") else None,
        )


class TokenManager:
    """
    Manages token persistence and revocation.

    Stores tokens in tokens.json with hashed values.
    Supports revocation via blacklist marking.
    """

    def __init__(self, data_dir: str = "./data"):
        """
        Initialize token manager

        Args:
            data_dir: Directory for data files
        """
        self.logger = logging.getLogger("persistence.token_manager")
        self.data_dir = Path(data_dir)
        self.tokens_file = self.data_dir / "tokens.json"

        # Initialize store with default structure
        default_data = {
            "tokens": [],
            "last_cleanup": None,
        }
        self.store = JSONStore(str(self.tokens_file), default_data)
        self.logger.info(f"TokenManager initialized (file={self.tokens_file})")

    def create_token(
        self,
        jti: str,
        client_id: str,
        username: str,
        access_token: str,
        refresh_token: str,
        access_expires_at: datetime,
        refresh_expires_at: datetime,
    ) -> TokenRecord:
        """
        Create and store a new token record

        Args:
            jti: JWT ID (unique identifier)
            client_id: Client identifier
            username: Username
            access_token: Access token string
            refresh_token: Refresh token string
            access_expires_at: Access token expiration time
            refresh_expires_at: Refresh token expiration time

        Returns:
            TokenRecord with stored data
        """
        # Hash tokens for storage (never store plaintext)
        access_hash = self._hash_token(access_token)
        refresh_hash = self._hash_token(refresh_token)

        record = TokenRecord(
            jti=jti,
            client_id=client_id,
            username=username,
            access_token_hash=access_hash,
            refresh_token_hash=refresh_hash,
            created_at=datetime.now(timezone.utc),
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
        )

        # Store to file
        data = self.store.load()
        data["tokens"].append(record.to_dict())
        self.store.save(data)

        self.logger.info(f"Token created: {jti} for {username}")
        return record

    def validate_token(
        self,
        token: str,
        token_type: str = "access",
    ) -> Optional[TokenRecord]:
        """
        Validate token and check if it's in the store and not revoked

        Args:
            token: Token string
            token_type: "access" or "refresh"

        Returns:
            TokenRecord if valid, raises exception otherwise

        Raises:
            TokenNotFoundError: Token not found
            TokenRevoked: Token has been revoked
        """
        token_hash = self._hash_token(token)
        data = self.store.load()

        for token_dict in data["tokens"]:
            record = TokenRecord.from_dict(token_dict)

            # Check matching hash
            if token_type == "access" and record.access_token_hash == token_hash:
                if record.revoked:
                    raise TokenRevoked(f"Token {record.jti} has been revoked")
                return record

            if token_type == "refresh" and record.refresh_token_hash == token_hash:
                if record.revoked:
                    raise TokenRevoked(f"Token {record.jti} has been revoked")
                return record

        raise TokenNotFoundError(f"Token not found in store ({token_type})")

    def revoke_token(self, jti: str) -> None:
        """
        Revoke a token by JTI

        Args:
            jti: JWT ID to revoke

        Raises:
            TokenNotFoundError: JTI not found
        """
        data = self.store.load()

        for token_dict in data["tokens"]:
            if token_dict["jti"] == jti:
                token_dict["revoked"] = True
                token_dict["revoked_at"] = datetime.now(timezone.utc).isoformat()
                self.store.save(data)
                self.logger.info(f"Token revoked: {jti}")
                return

        raise TokenNotFoundError(f"JTI {jti} not found in store")

    def cleanup_expired(self) -> int:
        """
        Remove expired tokens from store

        Returns:
            Number of tokens removed
        """
        data = self.store.load()
        now = datetime.now(timezone.utc)
        original_count = len(data["tokens"])

        # Keep only non-expired tokens
        data["tokens"] = [
            t for t in data["tokens"]
            if datetime.fromisoformat(t["refresh_expires_at"]) > now
        ]

        removed_count = original_count - len(data["tokens"])
        if removed_count > 0:
            data["last_cleanup"] = now.isoformat()
            self.store.save(data)
            self.logger.info(f"Cleanup removed {removed_count} expired tokens")

        return removed_count

    def get_token_by_jti(self, jti: str) -> Optional[TokenRecord]:
        """
        Get token record by JTI

        Args:
            jti: JWT ID

        Returns:
            TokenRecord if found, None otherwise
        """
        data = self.store.load()
        for token_dict in data["tokens"]:
            if token_dict["jti"] == jti:
                return TokenRecord.from_dict(token_dict)
        return None

    def list_client_tokens(self, client_id: str) -> list:
        """
        List all tokens for a client

        Args:
            client_id: Client identifier

        Returns:
            List of TokenRecord objects
        """
        data = self.store.load()
        return [
            TokenRecord.from_dict(t)
            for t in data["tokens"]
            if t["client_id"] == client_id
        ]

    @staticmethod
    def _hash_token(token: str) -> str:
        """
        Hash a token using SHA256

        Args:
            token: Token string

        Returns:
            SHA256 hash (hex)
        """
        return hashlib.sha256(token.encode()).hexdigest()


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    import tempfile
    import shutil

    class TestTokenManager(unittest.TestCase):
        """Test suite for TokenManager"""

        def setUp(self):
            """Setup before each test"""
            self.test_dir = tempfile.mkdtemp()
            self.manager = TokenManager(self.test_dir)

        def tearDown(self):
            """Cleanup after each test"""
            if os.path.exists(self.test_dir):
                shutil.rmtree(self.test_dir)

        def test_initialization(self):
            """Test manager initialization"""
            self.assertTrue(self.manager.tokens_file.exists())

        def test_create_token(self):
            """Test creating a token record"""
            client_id = "client-123"
            username = "alice"
            now = datetime.now(timezone.utc)
            from datetime import timedelta

            record = self.manager.create_token(
                jti="token-jti-1",
                client_id=client_id,
                username=username,
                access_token="access-token-string",
                refresh_token="refresh-token-string",
                access_expires_at=now + timedelta(hours=1),
                refresh_expires_at=now + timedelta(days=7),
            )

            self.assertEqual(record.jti, "token-jti-1")
            self.assertEqual(record.client_id, client_id)
            self.assertEqual(record.username, username)

        def test_validate_token(self):
            """Test validating a stored token"""
            from datetime import timedelta

            access_token = "my-access-token"
            now = datetime.now(timezone.utc)

            self.manager.create_token(
                jti="token-1",
                client_id="client-123",
                username="alice",
                access_token=access_token,
                refresh_token="refresh-token",
                access_expires_at=now + timedelta(hours=1),
                refresh_expires_at=now + timedelta(days=7),
            )

            # Token should be findable
            record = self.manager.validate_token(access_token, "access")
            self.assertEqual(record.jti, "token-1")

        def test_validate_token_not_found(self):
            """Test validating non-existent token"""
            with self.assertRaises(TokenNotFoundError):
                self.manager.validate_token("non-existent-token", "access")

        def test_revoke_token(self):
            """Test revoking a token"""
            from datetime import timedelta

            now = datetime.now(timezone.utc)
            self.manager.create_token(
                jti="token-to-revoke",
                client_id="client-123",
                username="alice",
                access_token="access-token",
                refresh_token="refresh-token",
                access_expires_at=now + timedelta(hours=1),
                refresh_expires_at=now + timedelta(days=7),
            )

            # Revoke the token
            self.manager.revoke_token("token-to-revoke")

            # Trying to validate should raise TokenRevoked
            with self.assertRaises(TokenRevoked):
                self.manager.validate_token("access-token", "access")

        def test_revoke_nonexistent_token(self):
            """Test revoking non-existent token"""
            with self.assertRaises(TokenNotFoundError):
                self.manager.revoke_token("nonexistent-jti")

        def test_cleanup_expired(self):
            """Test cleanup removes expired tokens"""
            from datetime import timedelta

            now = datetime.now(timezone.utc)

            # Create unexpired token
            self.manager.create_token(
                jti="valid-token",
                client_id="client-123",
                username="alice",
                access_token="access-1",
                refresh_token="refresh-1",
                access_expires_at=now + timedelta(hours=1),
                refresh_expires_at=now + timedelta(days=7),
            )

            # Create expired token
            self.manager.create_token(
                jti="expired-token",
                client_id="client-456",
                username="bob",
                access_token="access-2",
                refresh_token="refresh-2",
                access_expires_at=now - timedelta(hours=1),
                refresh_expires_at=now - timedelta(days=1),
            )

            # Cleanup should remove expired
            removed = self.manager.cleanup_expired()
            self.assertEqual(removed, 1)

            # Expired token should not be findable
            with self.assertRaises(TokenNotFoundError):
                self.manager.validate_token("access-2", "access")

        def test_get_token_by_jti(self):
            """Test retrieving token by JTI"""
            from datetime import timedelta

            now = datetime.now(timezone.utc)
            self.manager.create_token(
                jti="specific-jti",
                client_id="client-123",
                username="alice",
                access_token="access-token",
                refresh_token="refresh-token",
                access_expires_at=now + timedelta(hours=1),
                refresh_expires_at=now + timedelta(days=7),
            )

            record = self.manager.get_token_by_jti("specific-jti")
            self.assertIsNotNone(record)
            self.assertEqual(record.jti, "specific-jti")

        def test_get_token_by_jti_not_found(self):
            """Test retrieving non-existent JTI"""
            record = self.manager.get_token_by_jti("nonexistent")
            self.assertIsNone(record)

        def test_list_client_tokens(self):
            """Test listing tokens for a client"""
            from datetime import timedelta

            now = datetime.now(timezone.utc)

            # Create tokens for alice
            for i in range(3):
                self.manager.create_token(
                    jti=f"alice-token-{i}",
                    client_id="alice-id",
                    username="alice",
                    access_token=f"access-{i}",
                    refresh_token=f"refresh-{i}",
                    access_expires_at=now + timedelta(hours=1),
                    refresh_expires_at=now + timedelta(days=7),
                )

            # Create token for bob
            self.manager.create_token(
                jti="bob-token",
                client_id="bob-id",
                username="bob",
                access_token="bob-access",
                refresh_token="bob-refresh",
                access_expires_at=now + timedelta(hours=1),
                refresh_expires_at=now + timedelta(days=7),
            )

            # Should get 3 for alice, 0 for charlie
            alice_tokens = self.manager.list_client_tokens("alice-id")
            self.assertEqual(len(alice_tokens), 3)

            charlie_tokens = self.manager.list_client_tokens("charlie-id")
            self.assertEqual(len(charlie_tokens), 0)

        def test_refresh_token_validation(self):
            """Test validating refresh tokens specifically"""
            from datetime import timedelta

            refresh_token = "my-refresh-token"
            now = datetime.now(timezone.utc)

            self.manager.create_token(
                jti="token-1",
                client_id="client-123",
                username="alice",
                access_token="access-token",
                refresh_token=refresh_token,
                access_expires_at=now + timedelta(hours=1),
                refresh_expires_at=now + timedelta(days=7),
            )

            # Validate refresh token
            record = self.manager.validate_token(refresh_token, "refresh")
            self.assertEqual(record.jti, "token-1")

    import os
    unittest.main()
