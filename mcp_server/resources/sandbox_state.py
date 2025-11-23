#!/usr/bin/env python3
"""
Sandbox State Manager for Phase 6 - State Persistence

Module: resources.sandbox_state
Date: 2025-11-23
Version: 0.1.0-alpha (Phase 6)

CHANGELOG:
[2025-11-23 v0.1.0-alpha] Sandbox State Manager Implementation
  - Save and load per-client sandbox state
  - JSON serialization of variables
  - Persist to data/clients/{client_id}/state.json
  - Isolation strictly per client
  - Support for clearing state on logout

ARCHITECTURE:
SandboxStateManager persists variables between tool calls for same client.
- Each client has: data/clients/{client_id}/state.json
- State loaded before subprocess execution
- State saved after subprocess execution
- Only JSON-serializable objects saved
- Isolation: Alice cannot see Bob's state

SECURITY NOTES:
- State persisted only locally, not network accessible
- JSON serialization prevents code object leakage
- Per-client isolation prevents cross-client state access
- State cleared on logout/reset
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional


logger = logging.getLogger(__name__)


class SandboxStateManager:
    """
    Manages persistence of sandbox state per client.

    Features:
    - Save/load state to/from JSON files
    - Per-client isolation
    - JSON serialization for safety
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize SandboxStateManager.

        Args:
            base_dir: Base directory for client isolation (default: data/clients)
        """
        self.base_dir = Path(base_dir) if base_dir else Path("data/clients")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("resources.sandbox_state")

    def _get_state_file(self, client_id: str) -> Path:
        """
        Get path to state file for a client.

        Args:
            client_id: ID of the client

        Returns:
            Path: data/clients/{client_id}/state.json
        """
        client_dir = self.base_dir / client_id
        client_dir.mkdir(parents=True, exist_ok=True)
        return client_dir / "state.json"

    async def load_state(self, client_id: str) -> Dict[str, Any]:
        """
        Load sandbox state for a client.

        Args:
            client_id: ID of the client

        Returns:
            Dict: Loaded state, or {} if file doesn't exist

        Note: Executed in thread pool to avoid blocking
        """
        state_file = self._get_state_file(client_id)

        if not state_file.exists():
            self.logger.debug(f"No state file for {client_id}, starting fresh")
            return {}

        try:
            # Run file read in thread pool (async)
            loop = asyncio.get_event_loop()
            state_json = await loop.run_in_executor(
                None,
                self._read_state_file,
                state_file
            )

            state = json.loads(state_json)
            self.logger.debug(f"Loaded state for {client_id}: {len(state)} variables")
            return state

        except Exception as e:
            self.logger.error(f"Failed to load state for {client_id}: {e}")
            return {}

    async def save_state(
        self,
        client_id: str,
        state: Dict[str, Any]
    ) -> None:
        """
        Save sandbox state for a client.

        Args:
            client_id: ID of the client
            state: Variables to save

        Note: Executed in thread pool to avoid blocking
        """
        state_file = self._get_state_file(client_id)

        try:
            # Run file write in thread pool (async)
            state_json = json.dumps(state, default=str, indent=2)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._write_state_file,
                state_file,
                state_json
            )

            self.logger.debug(
                f"Saved state for {client_id}: {len(state)} variables"
            )

        except Exception as e:
            self.logger.error(f"Failed to save state for {client_id}: {e}")

    async def clear_state(self, client_id: str) -> None:
        """
        Clear sandbox state for a client.

        Args:
            client_id: ID of the client

        Note: Called on client logout or reset
        """
        state_file = self._get_state_file(client_id)

        if not state_file.exists():
            self.logger.debug(f"No state file to clear for {client_id}")
            return

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, state_file.unlink)
            self.logger.info(f"Cleared state for {client_id}")

        except Exception as e:
            self.logger.error(f"Failed to clear state for {client_id}: {e}")

    @staticmethod
    def _read_state_file(path: Path) -> str:
        """Read state file (blocking, for thread pool)"""
        with open(path, 'r') as f:
            return f.read()

    @staticmethod
    def _write_state_file(path: Path, content: str) -> None:
        """Write state file (blocking, for thread pool)"""
        with open(path, 'w') as f:
            f.write(content)

    @staticmethod
    def _serialize_state(state: Dict) -> str:
        """Serialize state dict to JSON string"""
        return json.dumps(state, default=str)

    @staticmethod
    def _deserialize_state(json_str: str) -> Dict:
        """Deserialize JSON string to state dict"""
        return json.loads(json_str)


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest
    import tempfile
    import shutil

    class TestSandboxStateManager(unittest.TestCase):
        """Test suite for SandboxStateManager"""

        def setUp(self):
            """Setup test fixtures"""
            self.temp_dir = tempfile.TemporaryDirectory()
            self.manager = SandboxStateManager(Path(self.temp_dir.name))

        def tearDown(self):
            """Cleanup test fixtures"""
            self.temp_dir.cleanup()

        def test_initialization(self):
            """Test manager initialization"""
            manager = SandboxStateManager(Path(self.temp_dir.name))
            self.assertTrue(manager.base_dir.exists())

        def test_load_nonexistent_state(self):
            """Test loading state that doesn't exist"""
            async def run():
                state = await self.manager.load_state("alice_123")
                return state

            state = asyncio.run(run())
            self.assertEqual(state, {})

        def test_save_and_load_state(self):
            """Test saving and loading state"""
            async def run():
                # Save state
                original_state = {"x": 42, "y": "hello", "z": [1, 2, 3]}
                await self.manager.save_state("alice_123", original_state)

                # Load state
                loaded_state = await self.manager.load_state("alice_123")
                return loaded_state

            loaded = asyncio.run(run())
            self.assertEqual(loaded["x"], 42)
            self.assertEqual(loaded["y"], "hello")
            self.assertEqual(loaded["z"], [1, 2, 3])

        def test_save_overwrites_previous(self):
            """Test that save overwrites previous state"""
            async def run():
                # Save first state
                await self.manager.save_state("alice_123", {"x": 1})

                # Save second state
                await self.manager.save_state("alice_123", {"x": 2, "y": 3})

                # Load and verify
                loaded = await self.manager.load_state("alice_123")
                return loaded

            loaded = asyncio.run(run())
            self.assertEqual(loaded["x"], 2)
            self.assertEqual(loaded["y"], 3)
            self.assertNotIn("z", loaded)

        def test_clear_state(self):
            """Test clearing state"""
            async def run():
                # Save state
                await self.manager.save_state("alice_123", {"x": 42})

                # Clear state
                await self.manager.clear_state("alice_123")

                # Load and verify empty
                loaded = await self.manager.load_state("alice_123")
                return loaded

            loaded = asyncio.run(run())
            self.assertEqual(loaded, {})

        def test_client_isolation(self):
            """Test that state is isolated per client"""
            async def run():
                # Save state for alice
                await self.manager.save_state("alice_123", {"x": 1})

                # Save state for bob
                await self.manager.save_state("bob_456", {"x": 2})

                # Load states
                alice_state = await self.manager.load_state("alice_123")
                bob_state = await self.manager.load_state("bob_456")

                return alice_state, bob_state

            alice, bob = asyncio.run(run())
            self.assertEqual(alice["x"], 1)
            self.assertEqual(bob["x"], 2)

        def test_serialize_complex_types(self):
            """Test serialization of complex types"""
            async def run():
                # Save state with various types
                state = {
                    "int": 42,
                    "float": 3.14,
                    "str": "hello",
                    "list": [1, 2, 3],
                    "dict": {"nested": "value"},
                    "bool": True,
                    "null": None
                }
                await self.manager.save_state("alice_123", state)

                # Load and verify
                loaded = await self.manager.load_state("alice_123")
                return loaded

            loaded = asyncio.run(run())
            self.assertEqual(loaded["int"], 42)
            self.assertEqual(loaded["float"], 3.14)
            self.assertEqual(loaded["str"], "hello")
            self.assertEqual(loaded["list"], [1, 2, 3])
            self.assertEqual(loaded["dict"]["nested"], "value")
            self.assertTrue(loaded["bool"])
            self.assertIsNone(loaded["null"])

    # Run tests
    unittest.main()
