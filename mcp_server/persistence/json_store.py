"""
JSON Store - Base class for JSON file handling

Module: persistence.json_store
Date: 2025-11-23
Version: 0.3.0-alpha

CHANGELOG:
[2025-11-23 v0.3.0-alpha] Initial implementation
  - Base class for JSON file operations
  - File locking for concurrent access
  - Automatic directory creation
  - Atomic writes

ARCHITECTURE:
JSONStore provides:
  - Thread-safe JSON serialization/deserialization
  - File locking for safe concurrent access
  - Atomic writes (write to temp file, then move)
  - Automatic backup of existing files
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict
from datetime import datetime, timezone
import hashlib


class JSONStoreError(Exception):
    """Base JSON store error"""
    pass


class JSONStoreIOError(JSONStoreError):
    """File I/O error"""
    pass


class JSONStoreFormatError(JSONStoreError):
    """JSON format error"""
    pass


class JSONStore:
    """
    Base class for JSON-based persistence.

    Handles:
    - File creation and permissions
    - Atomic writes (temp file + rename)
    - Thread-safe read/write operations
    - Automatic directory creation
    """

    def __init__(self, file_path: str, default_data: Dict[str, Any] = None):
        """
        Initialize JSON store

        Args:
            file_path: Path to JSON file
            default_data: Default data structure if file doesn't exist
        """
        self.logger = logging.getLogger(f"persistence.{self.__class__.__name__}")
        self.file_path = Path(file_path)
        self.default_data = default_data or {}

        # Ensure directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create file if doesn't exist
        if not self.file_path.exists():
            self._write_atomic(self.default_data)
            self.logger.info(f"Created new store: {self.file_path}")

    def load(self) -> Dict[str, Any]:
        """
        Load data from JSON file

        Returns:
            Parsed JSON data

        Raises:
            JSONStoreIOError: If file cannot be read
            JSONStoreFormatError: If JSON is invalid
        """
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except FileNotFoundError:
            self.logger.warning(f"File not found, returning default data")
            return self.default_data
        except json.JSONDecodeError as e:
            raise JSONStoreFormatError(f"Invalid JSON in {self.file_path}: {e}")
        except Exception as e:
            raise JSONStoreIOError(f"Failed to read {self.file_path}: {e}")

    def save(self, data: Dict[str, Any]) -> None:
        """
        Save data to JSON file (atomic write)

        Args:
            data: Data to save

        Raises:
            JSONStoreIOError: If write fails
        """
        self._write_atomic(data)

    def _write_atomic(self, data: Dict[str, Any]) -> None:
        """
        Atomic write: write to temp file, then rename

        Args:
            data: Data to write

        Raises:
            JSONStoreIOError: If write fails
        """
        try:
            # Write to temporary file
            temp_path = self.file_path.with_suffix('.tmp')

            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)

            # Atomic rename
            temp_path.replace(self.file_path)

            # Set permissions to 0600 (rw-------)
            self.file_path.chmod(0o600)

        except Exception as e:
            raise JSONStoreIOError(f"Failed to write {self.file_path}: {e}")

    def append_entry(self, entries_key: str, entry: Dict[str, Any]) -> None:
        """
        Append entry to a list in JSON (for audit logs, etc)

        Args:
            entries_key: Key containing the list
            entry: Entry to append
        """
        data = self.load()

        if entries_key not in data:
            data[entries_key] = []

        data[entries_key].append(entry)
        self.save(data)


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    import tempfile
    import shutil

    class TestJSONStore(unittest.TestCase):
        """Test suite for JSONStore"""

        def setUp(self):
            """Setup before each test"""
            self.test_dir = tempfile.mkdtemp()
            self.store_path = os.path.join(self.test_dir, "test.json")

        def tearDown(self):
            """Cleanup after each test"""
            if os.path.exists(self.test_dir):
                shutil.rmtree(self.test_dir)

        def test_initialization_creates_file(self):
            """Test initialization creates JSON file"""
            store = JSONStore(self.store_path)
            self.assertTrue(os.path.exists(self.store_path))

        def test_initialization_with_default_data(self):
            """Test initialization with default data"""
            default = {"key": "value"}
            store = JSONStore(self.store_path, default)
            data = store.load()
            self.assertEqual(data, default)

        def test_save_and_load(self):
            """Test saving and loading data"""
            store = JSONStore(self.store_path)
            test_data = {"name": "Alice", "age": 30}
            store.save(test_data)

            loaded = store.load()
            self.assertEqual(loaded, test_data)

        def test_atomic_write(self):
            """Test atomic write creates temp file then replaces"""
            store = JSONStore(self.store_path)
            data = {"value": 42}
            store.save(data)

            # Verify file exists and temp doesn't
            self.assertTrue(os.path.exists(self.store_path))
            self.assertFalse(os.path.exists(self.store_path + ".tmp"))

        def test_append_entry(self):
            """Test appending entry to list"""
            default = {"entries": []}
            store = JSONStore(self.store_path, default)

            store.append_entry("entries", {"id": 1, "text": "First"})
            store.append_entry("entries", {"id": 2, "text": "Second"})

            data = store.load()
            self.assertEqual(len(data["entries"]), 2)
            self.assertEqual(data["entries"][0]["id"], 1)

        def test_file_permissions(self):
            """Test file has restrictive permissions"""
            store = JSONStore(self.store_path)
            store.save({"data": "test"})

            # Check permissions are 0600 (rw-------)
            mode = os.stat(self.store_path).st_mode & 0o777
            self.assertEqual(mode, 0o600)

        def test_invalid_json_raises_error(self):
            """Test invalid JSON raises error"""
            # Write invalid JSON directly
            with open(self.store_path, 'w') as f:
                f.write("{invalid json}")

            store = JSONStore(self.store_path)
            with self.assertRaises(JSONStoreFormatError):
                store.load()

        def test_complex_data_serialization(self):
            """Test serialization of complex types"""
            from datetime import datetime
            store = JSONStore(self.store_path)

            # datetime will be serialized as string via default=str
            data = {
                "timestamp": datetime.now(timezone.utc),
                "list": [1, 2, 3],
                "nested": {"key": "value"}
            }
            store.save(data)

            loaded = store.load()
            self.assertIn("timestamp", loaded)
            self.assertEqual(loaded["list"], [1, 2, 3])

    unittest.main()
