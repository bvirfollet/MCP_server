"""
Audit Logger - Append-only audit trail

Module: persistence.audit_store
Date: 2025-11-23
Version: 0.3.0-alpha

CHANGELOG:
[2025-11-23 v0.3.0-alpha] Initial implementation
  - Append-only audit logging
  - Event type tracking
  - Timestamped entries
  - Query support

ARCHITECTURE:
AuditLogger provides:
  - Immutable audit trail
  - Structured event logging
  - Filtering and querying
  - Automatic timestamp management
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum

from .json_store import JSONStore


class EventType(Enum):
    """Audit event types"""
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILED = "auth_failed"
    AUTH_TOKEN_REFRESH = "auth_token_refresh"
    AUTH_TOKEN_REVOKED = "auth_token_revoked"
    TOOL_EXECUTED = "tool_executed"
    PERMISSION_DENIED = "permission_denied"
    CLIENT_CREATED = "client_created"
    CLIENT_DELETED = "client_deleted"
    CLIENT_DISABLED = "client_disabled"
    ERROR = "error"


class AuditEntry:
    """Represents an audit log entry"""

    def __init__(
        self,
        timestamp: datetime,
        event_type: str,
        client_id: Optional[str] = None,
        username: Optional[str] = None,
        status: str = "success",
        message: Optional[str] = None,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.timestamp = timestamp
        self.event_type = event_type
        self.client_id = client_id
        self.username = username
        self.status = status
        self.message = message
        self.error = error
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "client_id": self.client_id,
            "username": self.username,
            "status": self.status,
            "message": self.message,
            "error": self.error,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEntry":
        """Create from dictionary (from JSON)"""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_type=data["event_type"],
            client_id=data.get("client_id"),
            username=data.get("username"),
            status=data.get("status", "success"),
            message=data.get("message"),
            error=data.get("error"),
            details=data.get("details", {}),
        )


class AuditLogger:
    """
    Append-only audit trail logger.

    Logs all significant events to audit.json.
    Supports filtering and querying.
    """

    def __init__(self, data_dir: str = "./data"):
        """
        Initialize audit logger

        Args:
            data_dir: Directory for audit file
        """
        self.logger = logging.getLogger("persistence.audit_logger")
        self.data_dir = Path(data_dir)
        self.audit_file = self.data_dir / "audit.json"

        # Initialize store with default structure
        default_data = {
            "entries": [],
        }
        self.store = JSONStore(str(self.audit_file), default_data)
        self.logger.info(f"AuditLogger initialized (file={self.audit_file})")

    def log_event(
        self,
        event_type: str,
        client_id: Optional[str] = None,
        username: Optional[str] = None,
        status: str = "success",
        message: Optional[str] = None,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """
        Log an audit event (append-only)

        Args:
            event_type: Type of event
            client_id: Client identifier
            username: Username
            status: Event status (success, failure, etc)
            message: Human-readable message
            error: Error message if applicable
            details: Event details

        Returns:
            AuditEntry that was logged
        """
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            client_id=client_id,
            username=username,
            status=status,
            message=message,
            error=error,
            details=details,
        )

        # Append to store
        self.store.append_entry("entries", entry.to_dict())

        return entry

    def log_auth_success(
        self,
        client_id: str,
        username: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log successful authentication"""
        return self.log_event(
            event_type=EventType.AUTH_SUCCESS.value,
            client_id=client_id,
            username=username,
            status="success",
            message=f"Client {username} authenticated",
            details=details,
        )

    def log_auth_failed(
        self,
        username: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log failed authentication"""
        return self.log_event(
            event_type=EventType.AUTH_FAILED.value,
            username=username,
            status="failure",
            message=f"Authentication failed for {username}: {reason}",
            error=reason,
            details=details,
        )

    def log_tool_execution(
        self,
        client_id: str,
        username: str,
        tool_name: str,
        status: str,
        duration_ms: int,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log tool execution"""
        exec_details = {
            "tool_name": tool_name,
            "duration_ms": duration_ms,
        }
        if details:
            exec_details.update(details)

        return self.log_event(
            event_type=EventType.TOOL_EXECUTED.value,
            client_id=client_id,
            username=username,
            status=status,
            message=f"Tool executed: {tool_name} ({status})",
            details=exec_details,
        )

    def log_permission_denied(
        self,
        client_id: str,
        username: str,
        resource: str,
        required_permission: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log permission denial"""
        exec_details = {
            "resource": resource,
            "required_permission": required_permission,
        }
        if details:
            exec_details.update(details)

        return self.log_event(
            event_type=EventType.PERMISSION_DENIED.value,
            client_id=client_id,
            username=username,
            status="denied",
            message=f"Permission denied: {required_permission}",
            details=exec_details,
        )

    def log_client_created(
        self,
        client_id: str,
        username: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log client creation"""
        return self.log_event(
            event_type=EventType.CLIENT_CREATED.value,
            client_id=client_id,
            username=username,
            status="success",
            message=f"Client created: {username}",
            details=details,
        )

    def log_client_deleted(
        self,
        client_id: str,
        username: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log client deletion"""
        return self.log_event(
            event_type=EventType.CLIENT_DELETED.value,
            client_id=client_id,
            username=username,
            status="success",
            message=f"Client deleted: {username}",
            details=details,
        )

    def query_by_client(
        self,
        client_id: str,
        limit: Optional[int] = None,
    ) -> List[AuditEntry]:
        """
        Query audit entries by client_id

        Args:
            client_id: Client identifier
            limit: Max results

        Returns:
            List of matching AuditEntry objects
        """
        data = self.store.load()
        entries = [
            AuditEntry.from_dict(e)
            for e in data["entries"]
            if e.get("client_id") == client_id
        ]

        if limit:
            return entries[-limit:]
        return entries

    def query_by_event_type(
        self,
        event_type: str,
        limit: Optional[int] = None,
    ) -> List[AuditEntry]:
        """
        Query audit entries by event_type

        Args:
            event_type: Event type
            limit: Max results

        Returns:
            List of matching AuditEntry objects
        """
        data = self.store.load()
        entries = [
            AuditEntry.from_dict(e)
            for e in data["entries"]
            if e.get("event_type") == event_type
        ]

        if limit:
            return entries[-limit:]
        return entries

    def query_by_username(
        self,
        username: str,
        limit: Optional[int] = None,
    ) -> List[AuditEntry]:
        """
        Query audit entries by username

        Args:
            username: Username
            limit: Max results

        Returns:
            List of matching AuditEntry objects
        """
        data = self.store.load()
        entries = [
            AuditEntry.from_dict(e)
            for e in data["entries"]
            if e.get("username") == username
        ]

        if limit:
            return entries[-limit:]
        return entries

    def query_by_date_range(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> List[AuditEntry]:
        """
        Query audit entries by date range

        Args:
            start_time: Start time (inclusive)
            end_time: End time (inclusive)

        Returns:
            List of matching AuditEntry objects
        """
        data = self.store.load()
        entries = [
            AuditEntry.from_dict(e)
            for e in data["entries"]
            if start_time <= datetime.fromisoformat(e["timestamp"]) <= end_time
        ]
        return entries

    def get_recent_entries(self, limit: int = 100) -> List[AuditEntry]:
        """
        Get most recent audit entries

        Args:
            limit: Number of recent entries to return

        Returns:
            List of AuditEntry objects (newest first)
        """
        data = self.store.load()
        all_entries = [AuditEntry.from_dict(e) for e in data["entries"]]
        return all_entries[-limit:][::-1]

    def get_entry_count(self) -> int:
        """Get total audit entries"""
        data = self.store.load()
        return len(data["entries"])


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    import tempfile
    import shutil
    import os

    class TestAuditLogger(unittest.TestCase):
        """Test suite for AuditLogger"""

        def setUp(self):
            """Setup before each test"""
            self.test_dir = tempfile.mkdtemp()
            self.logger = AuditLogger(self.test_dir)

        def tearDown(self):
            """Cleanup after each test"""
            if os.path.exists(self.test_dir):
                shutil.rmtree(self.test_dir)

        def test_initialization(self):
            """Test logger initialization"""
            self.assertTrue(self.logger.audit_file.exists())

        def test_log_event(self):
            """Test logging a generic event"""
            entry = self.logger.log_event(
                event_type="test_event",
                client_id="client-123",
                username="alice",
                status="success",
                message="Test message",
            )

            self.assertEqual(entry.event_type, "test_event")
            self.assertEqual(entry.client_id, "client-123")
            self.assertEqual(entry.username, "alice")

        def test_log_auth_success(self):
            """Test logging successful auth"""
            entry = self.logger.log_auth_success("client-123", "alice")

            self.assertEqual(entry.event_type, EventType.AUTH_SUCCESS.value)
            self.assertEqual(entry.client_id, "client-123")
            self.assertEqual(entry.username, "alice")

        def test_log_auth_failed(self):
            """Test logging failed auth"""
            entry = self.logger.log_auth_failed("alice", "invalid_credentials")

            self.assertEqual(entry.event_type, EventType.AUTH_FAILED.value)
            self.assertEqual(entry.username, "alice")
            self.assertEqual(entry.status, "failure")

        def test_log_tool_execution(self):
            """Test logging tool execution"""
            entry = self.logger.log_tool_execution(
                client_id="client-123",
                username="alice",
                tool_name="greet",
                status="success",
                duration_ms=42,
            )

            self.assertEqual(entry.event_type, EventType.TOOL_EXECUTED.value)
            self.assertEqual(entry.details["tool_name"], "greet")
            self.assertEqual(entry.details["duration_ms"], 42)

        def test_log_permission_denied(self):
            """Test logging permission denial"""
            entry = self.logger.log_permission_denied(
                client_id="client-123",
                username="alice",
                resource="tool:admin_tool",
                required_permission="ADMIN",
            )

            self.assertEqual(entry.event_type, EventType.PERMISSION_DENIED.value)
            self.assertEqual(entry.status, "denied")

        def test_log_client_created(self):
            """Test logging client creation"""
            entry = self.logger.log_client_created("client-id", "alice")

            self.assertEqual(entry.event_type, EventType.CLIENT_CREATED.value)
            self.assertEqual(entry.status, "success")

        def test_query_by_client(self):
            """Test querying by client_id"""
            self.logger.log_auth_success("client-1", "alice")
            self.logger.log_auth_success("client-2", "bob")
            self.logger.log_auth_success("client-1", "alice")

            results = self.logger.query_by_client("client-1")
            self.assertEqual(len(results), 2)

        def test_query_by_event_type(self):
            """Test querying by event type"""
            self.logger.log_auth_success("client-1", "alice")
            self.logger.log_auth_failed("alice", "reason")
            self.logger.log_auth_success("client-2", "bob")

            results = self.logger.query_by_event_type(EventType.AUTH_SUCCESS.value)
            self.assertEqual(len(results), 2)

        def test_query_by_username(self):
            """Test querying by username"""
            self.logger.log_auth_success("client-1", "alice")
            self.logger.log_auth_success("client-2", "bob")
            self.logger.log_tool_execution("client-1", "alice", "greet", "success", 10)

            results = self.logger.query_by_username("alice")
            self.assertEqual(len(results), 2)

        def test_query_by_date_range(self):
            """Test querying by date range"""
            now = datetime.now(timezone.utc)
            self.logger.log_auth_success("client-1", "alice")

            # Query with wide range
            results = self.logger.query_by_date_range(
                now.replace(hour=0, minute=0, second=0),
                now.replace(hour=23, minute=59, second=59),
            )
            self.assertGreater(len(results), 0)

        def test_get_recent_entries(self):
            """Test getting recent entries"""
            for i in range(5):
                self.logger.log_auth_success(f"client-{i}", f"user-{i}")

            recent = self.logger.get_recent_entries(limit=3)
            self.assertEqual(len(recent), 3)

        def test_get_entry_count(self):
            """Test getting total entry count"""
            self.logger.log_auth_success("client-1", "alice")
            self.logger.log_auth_success("client-2", "bob")
            self.logger.log_auth_failed("alice", "reason")

            count = self.logger.get_entry_count()
            self.assertEqual(count, 3)

        def test_append_only_behavior(self):
            """Test that entries are append-only"""
            entry1 = self.logger.log_auth_success("client-1", "alice")
            entry2 = self.logger.log_auth_success("client-2", "bob")

            # Query all entries
            all_entries = self.logger.get_recent_entries(limit=100)
            self.assertEqual(len(all_entries), 2)

            # Timestamps should be monotonically increasing
            self.assertLessEqual(entry1.timestamp, entry2.timestamp)

    unittest.main()
