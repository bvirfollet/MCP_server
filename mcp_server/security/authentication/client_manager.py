"""
Client Manager - Client credentials and authentication

Module: security.authentication.client_manager
Date: 2025-11-23
Version: 0.3.0-alpha

CHANGELOG:
[2025-11-23 v0.3.0-alpha] Initial implementation
  - Client registration with bcrypt password hashing
  - Client authentication (credentials validation)
  - Client metadata management
  - Persistent storage in clients.json

ARCHITECTURE:
ClientManager provides:
  - Secure password hashing with bcrypt
  - Client credential verification
  - Client metadata (roles, email, etc)
  - Persistent client registry
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import uuid

import bcrypt

from ...persistence.json_store import JSONStore, JSONStoreError


class ClientError(Exception):
    """Base client error"""
    pass


class ClientNotFoundError(ClientError):
    """Client not found"""
    pass


class ClientExistsError(ClientError):
    """Client already exists"""
    pass


class AuthenticationError(ClientError):
    """Authentication failed"""
    pass


class ClientRecord:
    """Represents a stored client record"""

    def __init__(
        self,
        client_id: str,
        username: str,
        password_hash: str,
        email: Optional[str] = None,
        roles: Optional[List[str]] = None,
        created_at: Optional[datetime] = None,
        last_login: Optional[datetime] = None,
        enabled: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.client_id = client_id
        self.username = username
        self.password_hash = password_hash
        self.email = email
        self.roles = roles or []
        self.created_at = created_at or datetime.now(timezone.utc)
        self.last_login = last_login
        self.enabled = enabled
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage"""
        return {
            "client_id": self.client_id,
            "username": self.username,
            "password_hash": self.password_hash,
            "email": self.email,
            "roles": self.roles,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClientRecord":
        """Create from dictionary (from JSON)"""
        return cls(
            client_id=data["client_id"],
            username=data["username"],
            password_hash=data["password_hash"],
            email=data.get("email"),
            roles=data.get("roles", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_login=datetime.fromisoformat(data["last_login"]) if data.get("last_login") else None,
            enabled=data.get("enabled", True),
            metadata=data.get("metadata", {}),
        )


class ClientManager:
    """
    Manages client credentials and authentication.

    Stores clients in clients.json with bcrypt-hashed passwords.
    Supports authentication, registration, and metadata management.
    """

    def __init__(self, data_dir: str = "./data", bcrypt_rounds: int = 10):
        """
        Initialize client manager

        Args:
            data_dir: Directory for data files
            bcrypt_rounds: Cost factor for bcrypt (10-12 recommended)
        """
        self.logger = logging.getLogger("security.client_manager")
        self.data_dir = Path(data_dir)
        self.clients_file = self.data_dir / "clients.json"
        self.bcrypt_rounds = bcrypt_rounds

        # Initialize store with default structure
        default_data = {
            "clients": [],
        }
        self.store = JSONStore(str(self.clients_file), default_data)
        self.logger.info(f"ClientManager initialized (file={self.clients_file})")

    def create_client(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        roles: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ClientRecord:
        """
        Create a new client with hashed password

        Args:
            username: Username (must be unique)
            password: Plaintext password (will be hashed)
            email: Client email
            roles: List of roles
            metadata: Client metadata

        Returns:
            ClientRecord with stored data

        Raises:
            ClientExistsError: If username already exists
        """
        # Check if client exists
        if self._find_by_username(username) is not None:
            raise ClientExistsError(f"Client '{username}' already exists")

        # Hash password
        password_hash = self._hash_password(password)

        # Create client
        client_id = str(uuid.uuid4())
        record = ClientRecord(
            client_id=client_id,
            username=username,
            password_hash=password_hash,
            email=email,
            roles=roles or [],
            created_at=datetime.now(timezone.utc),
            metadata=metadata,
        )

        # Store to file
        data = self.store.load()
        data["clients"].append(record.to_dict())
        self.store.save(data)

        self.logger.info(f"Client created: {username} ({client_id})")
        return record

    def authenticate(self, username: str, password: str) -> ClientRecord:
        """
        Authenticate client with username and password

        Args:
            username: Username
            password: Plaintext password

        Returns:
            ClientRecord if authentication succeeds

        Raises:
            ClientNotFoundError: If client doesn't exist
            AuthenticationError: If password is incorrect or client disabled
        """
        client = self._find_by_username(username)
        if client is None:
            raise ClientNotFoundError(f"Client '{username}' not found")

        if not client.enabled:
            raise AuthenticationError(f"Client '{username}' is disabled")

        # Verify password
        if not self._verify_password(password, client.password_hash):
            self.logger.warning(f"Authentication failed for {username}")
            raise AuthenticationError("Invalid password")

        # Update last_login
        self._update_last_login(client.client_id)

        self.logger.info(f"Client authenticated: {username}")
        return client

    def get_client(self, client_id: str) -> Optional[ClientRecord]:
        """
        Get client by client_id

        Args:
            client_id: Client identifier

        Returns:
            ClientRecord if found, None otherwise
        """
        data = self.store.load()
        for client_dict in data["clients"]:
            if client_dict["client_id"] == client_id:
                return ClientRecord.from_dict(client_dict)
        return None

    def get_client_by_username(self, username: str) -> Optional[ClientRecord]:
        """
        Get client by username

        Args:
            username: Username

        Returns:
            ClientRecord if found, None otherwise
        """
        return self._find_by_username(username)

    def update_metadata(self, client_id: str, metadata: Dict[str, Any]) -> ClientRecord:
        """
        Update client metadata

        Args:
            client_id: Client identifier
            metadata: New metadata (merged with existing)

        Returns:
            Updated ClientRecord

        Raises:
            ClientNotFoundError: If client doesn't exist
        """
        data = self.store.load()

        for client_dict in data["clients"]:
            if client_dict["client_id"] == client_id:
                # Merge metadata
                client_dict["metadata"].update(metadata)
                self.store.save(data)
                self.logger.info(f"Client metadata updated: {client_id}")
                return ClientRecord.from_dict(client_dict)

        raise ClientNotFoundError(f"Client {client_id} not found")

    def set_client_enabled(self, client_id: str, enabled: bool) -> ClientRecord:
        """
        Enable or disable a client

        Args:
            client_id: Client identifier
            enabled: True to enable, False to disable

        Returns:
            Updated ClientRecord

        Raises:
            ClientNotFoundError: If client doesn't exist
        """
        data = self.store.load()

        for client_dict in data["clients"]:
            if client_dict["client_id"] == client_id:
                client_dict["enabled"] = enabled
                self.store.save(data)
                status = "enabled" if enabled else "disabled"
                self.logger.info(f"Client {status}: {client_id}")
                return ClientRecord.from_dict(client_dict)

        raise ClientNotFoundError(f"Client {client_id} not found")

    def add_role(self, client_id: str, role: str) -> ClientRecord:
        """
        Add a role to client

        Args:
            client_id: Client identifier
            role: Role name

        Returns:
            Updated ClientRecord

        Raises:
            ClientNotFoundError: If client doesn't exist
        """
        data = self.store.load()

        for client_dict in data["clients"]:
            if client_dict["client_id"] == client_id:
                if role not in client_dict["roles"]:
                    client_dict["roles"].append(role)
                    self.store.save(data)
                    self.logger.info(f"Role added to {client_id}: {role}")
                return ClientRecord.from_dict(client_dict)

        raise ClientNotFoundError(f"Client {client_id} not found")

    def remove_role(self, client_id: str, role: str) -> ClientRecord:
        """
        Remove a role from client

        Args:
            client_id: Client identifier
            role: Role name

        Returns:
            Updated ClientRecord

        Raises:
            ClientNotFoundError: If client doesn't exist
        """
        data = self.store.load()

        for client_dict in data["clients"]:
            if client_dict["client_id"] == client_id:
                if role in client_dict["roles"]:
                    client_dict["roles"].remove(role)
                    self.store.save(data)
                    self.logger.info(f"Role removed from {client_id}: {role}")
                return ClientRecord.from_dict(client_dict)

        raise ClientNotFoundError(f"Client {client_id} not found")

    def list_clients(self) -> List[ClientRecord]:
        """
        List all clients

        Returns:
            List of ClientRecord objects
        """
        data = self.store.load()
        return [ClientRecord.from_dict(c) for c in data["clients"]]

    def delete_client(self, client_id: str) -> None:
        """
        Delete a client

        Args:
            client_id: Client identifier

        Raises:
            ClientNotFoundError: If client doesn't exist
        """
        data = self.store.load()

        for i, client_dict in enumerate(data["clients"]):
            if client_dict["client_id"] == client_id:
                username = client_dict["username"]
                data["clients"].pop(i)
                self.store.save(data)
                self.logger.info(f"Client deleted: {username} ({client_id})")
                return

        raise ClientNotFoundError(f"Client {client_id} not found")

    def _find_by_username(self, username: str) -> Optional[ClientRecord]:
        """Find client by username"""
        data = self.store.load()
        for client_dict in data["clients"]:
            if client_dict["username"] == username:
                return ClientRecord.from_dict(client_dict)
        return None

    def _update_last_login(self, client_id: str) -> None:
        """Update last_login timestamp"""
        data = self.store.load()
        for client_dict in data["clients"]:
            if client_dict["client_id"] == client_id:
                client_dict["last_login"] = datetime.now(timezone.utc).isoformat()
                self.store.save(data)
                break

    @staticmethod
    def _hash_password(password: str) -> str:
        """
        Hash password using bcrypt

        Args:
            password: Plaintext password

        Returns:
            bcrypt hash (bytes decoded to string)
        """
        salt = bcrypt.gensalt(rounds=10)
        hashed = bcrypt.hashpw(password.encode(), salt)
        return hashed.decode()

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        """
        Verify password against hash

        Args:
            password: Plaintext password
            password_hash: bcrypt hash

        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        except Exception:
            return False


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    import tempfile
    import shutil
    import os

    class TestClientManager(unittest.TestCase):
        """Test suite for ClientManager"""

        def setUp(self):
            """Setup before each test"""
            self.test_dir = tempfile.mkdtemp()
            self.manager = ClientManager(self.test_dir)

        def tearDown(self):
            """Cleanup after each test"""
            if os.path.exists(self.test_dir):
                shutil.rmtree(self.test_dir)

        def test_initialization(self):
            """Test manager initialization"""
            self.assertTrue(self.manager.clients_file.exists())

        def test_create_client(self):
            """Test creating a client"""
            client = self.manager.create_client(
                username="alice",
                password="secret123",
                email="alice@example.com",
                roles=["user"],
            )

            self.assertEqual(client.username, "alice")
            self.assertEqual(client.email, "alice@example.com")
            self.assertIn("user", client.roles)
            self.assertIsNotNone(client.client_id)

        def test_create_duplicate_client_raises(self):
            """Test creating duplicate client raises error"""
            self.manager.create_client("alice", "password")

            with self.assertRaises(ClientExistsError):
                self.manager.create_client("alice", "different")

        def test_authenticate_valid_credentials(self):
            """Test authentication with valid credentials"""
            self.manager.create_client("alice", "secret123")

            client = self.manager.authenticate("alice", "secret123")
            self.assertEqual(client.username, "alice")

        def test_authenticate_invalid_password(self):
            """Test authentication with wrong password"""
            self.manager.create_client("alice", "secret123")

            with self.assertRaises(AuthenticationError):
                self.manager.authenticate("alice", "wrongpassword")

        def test_authenticate_nonexistent_client(self):
            """Test authentication of non-existent client"""
            with self.assertRaises(ClientNotFoundError):
                self.manager.authenticate("nonexistent", "password")

        def test_get_client(self):
            """Test retrieving client by ID"""
            created = self.manager.create_client("alice", "password")

            client = self.manager.get_client(created.client_id)
            self.assertIsNotNone(client)
            self.assertEqual(client.username, "alice")

        def test_get_client_not_found(self):
            """Test retrieving non-existent client"""
            client = self.manager.get_client("nonexistent-id")
            self.assertIsNone(client)

        def test_get_client_by_username(self):
            """Test retrieving client by username"""
            self.manager.create_client("alice", "password")

            client = self.manager.get_client_by_username("alice")
            self.assertIsNotNone(client)
            self.assertEqual(client.username, "alice")

        def test_update_metadata(self):
            """Test updating client metadata"""
            created = self.manager.create_client("alice", "password")

            updated = self.manager.update_metadata(
                created.client_id,
                {"department": "engineering", "level": "senior"}
            )

            self.assertEqual(updated.metadata["department"], "engineering")
            self.assertEqual(updated.metadata["level"], "senior")

        def test_set_client_enabled_disabled(self):
            """Test disabling and enabling client"""
            created = self.manager.create_client("alice", "password")

            # Disable
            disabled = self.manager.set_client_enabled(created.client_id, False)
            self.assertFalse(disabled.enabled)

            # Try to authenticate disabled client
            with self.assertRaises(AuthenticationError):
                self.manager.authenticate("alice", "password")

            # Enable
            enabled = self.manager.set_client_enabled(created.client_id, True)
            self.assertTrue(enabled.enabled)

        def test_add_role(self):
            """Test adding role to client"""
            created = self.manager.create_client("alice", "password", roles=["user"])

            updated = self.manager.add_role(created.client_id, "admin")
            self.assertIn("admin", updated.roles)
            self.assertIn("user", updated.roles)

        def test_remove_role(self):
            """Test removing role from client"""
            created = self.manager.create_client(
                "alice", "password", roles=["user", "admin"]
            )

            updated = self.manager.remove_role(created.client_id, "admin")
            self.assertNotIn("admin", updated.roles)
            self.assertIn("user", updated.roles)

        def test_list_clients(self):
            """Test listing all clients"""
            self.manager.create_client("alice", "pass1")
            self.manager.create_client("bob", "pass2")
            self.manager.create_client("charlie", "pass3")

            clients = self.manager.list_clients()
            self.assertEqual(len(clients), 3)

        def test_delete_client(self):
            """Test deleting a client"""
            created = self.manager.create_client("alice", "password")

            self.manager.delete_client(created.client_id)

            client = self.manager.get_client(created.client_id)
            self.assertIsNone(client)

        def test_delete_nonexistent_client(self):
            """Test deleting non-existent client"""
            with self.assertRaises(ClientNotFoundError):
                self.manager.delete_client("nonexistent-id")

        def test_password_hashing_is_bcrypt(self):
            """Test that passwords are properly hashed"""
            client = self.manager.create_client("alice", "secret")

            # Hash should be bcrypt format (starts with $2a$, $2b$, or $2y$)
            self.assertTrue(
                client.password_hash.startswith(("$2a$", "$2b$", "$2y$"))
            )

        def test_last_login_updated_on_auth(self):
            """Test that last_login is updated after authentication"""
            created = self.manager.create_client("alice", "password")
            self.assertIsNone(created.last_login)

            self.manager.authenticate("alice", "password")

            updated = self.manager.get_client(created.client_id)
            self.assertIsNotNone(updated.last_login)

    unittest.main()
