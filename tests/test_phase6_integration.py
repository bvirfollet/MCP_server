#!/usr/bin/env python3
"""
Phase 6 Integration Tests - Process Isolation (Subprocess)

Tests the Phase 6 components:
- SubprocessExecutor: Code execution in isolated processes
- ClientIsolationManager: Directory isolation per client
- ResourceManager: Resource quotas and allocation
- SandboxStateManager: State persistence
- New RBAC Permissions: FILE_READ_CROSS_CLIENT, FILE_WRITE_CROSS_CLIENT, QUOTA_OVERRIDE
"""

import asyncio
import json
import logging
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

# Add mcp_server to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.resources.subprocess_executor import SubprocessExecutor
from mcp_server.resources.client_isolation import ClientIsolationManager
from mcp_server.resources.resource_manager import (
    ResourceManager,
    ClientQuotas,
    ResourceRequirement
)
from mcp_server.resources.sandbox_state import SandboxStateManager

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# ============================================================================
# ISOLATION TESTS
# ============================================================================


async def test_isolation_own_file_access():
    """Test: Client A can read own files"""
    print("TEST 1: Client isolation - own file access...", end=" ")

    with tempfile.TemporaryDirectory() as temp_dir:
        manager = ClientIsolationManager(Path(temp_dir))

        # Alice creates a file
        alice_dir = manager.get_client_directory("alice_123")
        (alice_dir / "data.txt").write_text("secret")

        # Alice can access her file
        alice_path = manager.resolve_path("alice_123", "data.txt")
        allowed = manager.validate_access("alice_123", alice_path)

        if allowed and (alice_path).read_text() == "secret":
            print("✓")
            return True

    print("✗")
    return False


async def test_isolation_cross_client_denied():
    """Test: Client A cannot read Client B files without permission"""
    print("TEST 2: Client isolation - cross-client denied...", end=" ")

    with tempfile.TemporaryDirectory() as temp_dir:
        manager = ClientIsolationManager(Path(temp_dir))

        # Bob creates a file
        bob_dir = manager.get_client_directory("bob_456")
        (bob_dir / "secret.txt").write_text("bob's secret")

        # Alice tries to access Bob's file
        bob_path = manager.resolve_path("bob_456", "secret.txt")
        allowed = manager.validate_access(
            "alice_123",
            bob_path,
            cross_client_permission=False
        )

        if not allowed:
            print("✓")
            return True

    print("✗")
    return False


async def test_isolation_cross_client_allowed():
    """Test: Client A with FILE_READ_CROSS_CLIENT can read Client B files"""
    print("TEST 3: Client isolation - cross-client allowed...", end=" ")

    with tempfile.TemporaryDirectory() as temp_dir:
        manager = ClientIsolationManager(Path(temp_dir))

        # Bob creates a file
        bob_dir = manager.get_client_directory("bob_456")
        (bob_dir / "secret.txt").write_text("bob's secret")

        # Alice accesses Bob's file WITH permission
        bob_path = manager.resolve_path("bob_456", "secret.txt")
        allowed = manager.validate_access(
            "alice_123",
            bob_path,
            cross_client_permission=True
        )

        if allowed:
            print("✓")
            return True

    print("✗")
    return False


async def test_isolation_path_traversal_blocked():
    """Test: Path traversal attacks blocked"""
    print("TEST 4: Client isolation - path traversal blocked...", end=" ")

    with tempfile.TemporaryDirectory() as temp_dir:
        manager = ClientIsolationManager(Path(temp_dir))

        # Try to escape client directory
        try:
            manager.resolve_path("alice_123", "../../etc/passwd")
            # Should have raised ValueError
            print("✗")
            return False
        except ValueError:
            # Expected
            print("✓")
            return True


# ============================================================================
# SUBPROCESS TESTS
# ============================================================================


async def test_subprocess_normal_execution():
    """Test: Normal code execution"""
    print("TEST 5: Subprocess - normal execution...", end=" ")

    with tempfile.TemporaryDirectory() as temp_dir:
        executor = SubprocessExecutor(timeout=5.0)

        result = await executor.execute(
            code="x = 42; y = x + 8",
            client_id="test_client",
            working_dir=Path(temp_dir),
            timeout=5.0
        )

        if result.get("success") and result.get("context", {}).get("x") == 42:
            print("✓")
            return True

    print("✗")
    return False


async def test_subprocess_code_with_error():
    """Test: Code that raises an error"""
    print("TEST 6: Subprocess - error handling...", end=" ")

    with tempfile.TemporaryDirectory() as temp_dir:
        executor = SubprocessExecutor(timeout=5.0)

        result = await executor.execute(
            code="raise ValueError('test error')",
            client_id="test_client",
            working_dir=Path(temp_dir),
            timeout=5.0
        )

        if not result.get("success") and result.get("error"):
            print("✓")
            return True

    print("✗")
    return False


async def test_subprocess_timeout():
    """Test: Code with timeout"""
    print("TEST 7: Subprocess - timeout handling...", end=" ")

    with tempfile.TemporaryDirectory() as temp_dir:
        executor = SubprocessExecutor(timeout=1.0)

        result = await executor.execute(
            code="import time; time.sleep(10)",
            client_id="test_client",
            working_dir=Path(temp_dir),
            timeout=1.0
        )

        if not result.get("success") and "timeout" in result.get("error", "").lower():
            print("✓")
            return True

    print("✗")
    return False


async def test_subprocess_with_context():
    """Test: Code execution with pre-loaded context"""
    print("TEST 8: Subprocess - context persistence...", end=" ")

    with tempfile.TemporaryDirectory() as temp_dir:
        executor = SubprocessExecutor(timeout=5.0)

        result = await executor.execute(
            code="z = x + y",
            client_id="test_client",
            working_dir=Path(temp_dir),
            timeout=5.0,
            context={"x": 10, "y": 20}
        )

        if result.get("success") and result.get("context", {}).get("z") == 30:
            print("✓")
            return True

    print("✗")
    return False


# ============================================================================
# QUOTA TESTS
# ============================================================================


async def test_quota_within_limit():
    """Test: Code within quota executes"""
    print("TEST 9: Quota - within limit...", end=" ")

    manager = ResourceManager()
    required = ResourceRequirement(memory_mb=256)

    allowed, reason = manager.check_availability(
        "alice_123",
        required,
        has_quota_override=False
    )

    if allowed:
        print("✓")
        return True

    print("✗")
    return False


async def test_quota_exceeds_limit():
    """Test: Code exceeds quota rejected"""
    print("TEST 10: Quota - exceeds limit...", end=" ")

    manager = ResourceManager()
    required = ResourceRequirement(memory_mb=1000)

    allowed, reason = manager.check_availability(
        "alice_123",
        required,
        has_quota_override=False
    )

    if not allowed and "memory" in reason.lower():
        print("✓")
        return True

    print("✗")
    return False


async def test_quota_override_allows():
    """Test: QUOTA_OVERRIDE permission allows exceeding quota"""
    print("TEST 11: Quota - override permission...", end=" ")

    manager = ResourceManager()
    required = ResourceRequirement(memory_mb=1000)

    allowed, reason = manager.check_availability(
        "alice_123",
        required,
        has_quota_override=True
    )

    if allowed:
        print("✓")
        return True

    print("✗")
    return False


async def test_quota_allocation_and_release():
    """Test: Resource allocation and release"""
    print("TEST 12: Quota - allocation/release...", end=" ")

    manager = ResourceManager()
    required = ResourceRequirement(memory_mb=256)

    # Allocate
    manager.allocate("alice_123", pid=1234, required=required)
    usage1 = manager.get_client_usage("alice_123")

    if usage1.memory_mb != 256:
        print("✗")
        return False

    # Release
    manager.release("alice_123", pid=1234, used=required)
    usage2 = manager.get_client_usage("alice_123")

    if usage2.memory_mb == 0:
        print("✓")
        return True

    print("✗")
    return False


# ============================================================================
# STATE PERSISTENCE TESTS
# ============================================================================


async def test_state_persistence_same_client():
    """Test: Variables persist between calls for same client"""
    print("TEST 13: State persistence - same client...", end=" ")

    with tempfile.TemporaryDirectory() as temp_dir:
        manager = SandboxStateManager(Path(temp_dir))

        # Save state
        original = {"x": 42, "y": "hello"}
        await manager.save_state("alice_123", original)

        # Load state
        loaded = await manager.load_state("alice_123")

        if loaded == original:
            print("✓")
            return True

    print("✗")
    return False


async def test_state_isolation():
    """Test: Different clients have different state"""
    print("TEST 14: State persistence - client isolation...", end=" ")

    with tempfile.TemporaryDirectory() as temp_dir:
        manager = SandboxStateManager(Path(temp_dir))

        # Save different states
        await manager.save_state("alice_123", {"x": 1})
        await manager.save_state("bob_456", {"x": 2})

        # Load states
        alice_state = await manager.load_state("alice_123")
        bob_state = await manager.load_state("bob_456")

        if alice_state["x"] == 1 and bob_state["x"] == 2:
            print("✓")
            return True

    print("✗")
    return False


async def test_state_clear():
    """Test: State cleared on logout"""
    print("TEST 15: State persistence - clear on logout...", end=" ")

    with tempfile.TemporaryDirectory() as temp_dir:
        manager = SandboxStateManager(Path(temp_dir))

        # Save state
        await manager.save_state("alice_123", {"x": 42})

        # Clear state
        await manager.clear_state("alice_123")

        # Load state (should be empty)
        loaded = await manager.load_state("alice_123")

        if loaded == {}:
            print("✓")
            return True

    print("✗")
    return False


# ============================================================================
# PERMISSION TESTS
# ============================================================================


async def test_permission_file_read_cross_client():
    """Test: FILE_READ_CROSS_CLIENT permission enforced"""
    print("TEST 16: Permission - FILE_READ_CROSS_CLIENT...", end=" ")

    with tempfile.TemporaryDirectory() as temp_dir:
        manager = ClientIsolationManager(Path(temp_dir))

        # Bob's file
        bob_path = manager.resolve_path("bob_456", "secret.txt")
        (bob_path.parent / "secret.txt").write_text("secret")

        # Alice without permission
        denied = not manager.validate_access(
            "alice_123",
            bob_path,
            cross_client_permission=False
        )

        # Alice with permission
        allowed = manager.validate_access(
            "alice_123",
            bob_path,
            cross_client_permission=True
        )

        if denied and allowed:
            print("✓")
            return True

    print("✗")
    return False


async def test_permission_quota_override():
    """Test: QUOTA_OVERRIDE permission enforced"""
    print("TEST 17: Permission - QUOTA_OVERRIDE...", end=" ")

    manager = ResourceManager()
    large_req = ResourceRequirement(memory_mb=1000)

    # Without permission
    denied, _ = manager.check_availability(
        "alice_123",
        large_req,
        has_quota_override=False
    )

    # With permission
    allowed, _ = manager.check_availability(
        "alice_123",
        large_req,
        has_quota_override=True
    )

    if not denied and allowed:
        print("✓")
        return True

    print("✗")
    return False


# ============================================================================
# MAIN
# ============================================================================


async def main():
    """Run all Phase 6 integration tests"""
    print("\n" + "="*70)
    print("PHASE 6 INTEGRATION TESTS - Process Isolation (Subprocess)")
    print("="*70 + "\n")

    tests = [
        # Isolation Tests (4)
        test_isolation_own_file_access,
        test_isolation_cross_client_denied,
        test_isolation_cross_client_allowed,
        test_isolation_path_traversal_blocked,

        # Subprocess Tests (4)
        test_subprocess_normal_execution,
        test_subprocess_code_with_error,
        test_subprocess_timeout,
        test_subprocess_with_context,

        # Quota Tests (4)
        test_quota_within_limit,
        test_quota_exceeds_limit,
        test_quota_override_allows,
        test_quota_allocation_and_release,

        # State Persistence Tests (3)
        test_state_persistence_same_client,
        test_state_isolation,
        test_state_clear,

        # Permission Tests (2)
        test_permission_file_read_cross_client,
        test_permission_quota_override,
    ]

    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            logger.error(f"Test failed: {e}")
            results.append(False)

    # Summary
    passed = sum(results)
    total = len(results)

    print("\n" + "="*70)
    print(f"Results: {passed}/{total} tests passed")
    print("="*70 + "\n")

    return all(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
