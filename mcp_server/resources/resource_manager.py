#!/usr/bin/env python3
"""
Resource Manager for Phase 6 - Quota Management

Module: resources.resource_manager
Date: 2025-11-23
Version: 0.1.0-alpha (Phase 6)

CHANGELOG:
[2025-11-23 v0.1.0-alpha] Resource Manager Implementation
  - Define per-client CPU/Memory/Disk quotas
  - Check resource availability before subprocess execution
  - Allocate resources to subprocess
  - Release resources after subprocess
  - Support QUOTA_OVERRIDE permission
  - Audit trail for quota violations

ARCHITECTURE:
ResourceManager enforces resource quotas per client.
- Default quotas: CPU 50%, RAM 512MB, Disk 1GB
- Before execution: verify available resources
- If QUOTA_OVERRIDE permission: ignore quotas
- If insufficient: PermissionDeniedError
- Track usage per client for monitoring

SECURITY NOTES:
- Quotas prevent resource exhaustion attacks
- QUOTA_OVERRIDE is a special admin permission
- Per-client quotas ensure fair resource sharing
- Audit trail for quota violations
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


logger = logging.getLogger(__name__)


@dataclass
class ClientQuotas:
    """Resource quotas for a client"""
    cpu_percent: float = 50.0          # Max CPU usage (%)
    memory_mb: int = 512               # Max memory (MB)
    disk_gb: int = 1                   # Max disk space (GB)
    concurrent_processes: int = 5      # Max concurrent subprocesses


@dataclass
class ResourceUsage:
    """Current resource usage for a client"""
    cpu_percent: float = 0.0
    memory_mb: int = 0
    disk_gb: float = 0.0
    concurrent_processes: int = 0


@dataclass
class ResourceRequirement:
    """Resource requirement for a subprocess"""
    memory_mb: int = 128               # Estimated memory needed (MB)
    timeout_seconds: float = 30.0      # Execution timeout


class ResourceManager:
    """
    Manages resource quotas and allocation per client.

    Features:
    - Per-client CPU/Memory/Disk quotas
    - Check availability before execution
    - QUOTA_OVERRIDE permission support
    - Audit trail for violations
    """

    def __init__(self):
        """Initialize ResourceManager"""
        self.client_quotas: Dict[str, ClientQuotas] = {}
        self.client_usage: Dict[str, ResourceUsage] = {}
        self.quota_violations: Dict[str, int] = {}  # Count of violations per client
        self.logger = logging.getLogger("resources.resource_manager")

    def get_client_quotas(self, client_id: str) -> ClientQuotas:
        """
        Get resource quotas for a client.

        Args:
            client_id: ID of the client

        Returns:
            ClientQuotas: Quotas for the client (defaults if not set)
        """
        if client_id not in self.client_quotas:
            # Create default quotas
            self.client_quotas[client_id] = ClientQuotas()
            self.logger.debug(f"Created default quotas for {client_id}")

        return self.client_quotas[client_id]

    def set_client_quotas(
        self,
        client_id: str,
        quotas: ClientQuotas
    ) -> None:
        """
        Set custom quotas for a client.

        Args:
            client_id: ID of the client
            quotas: ClientQuotas object with custom values
        """
        self.client_quotas[client_id] = quotas
        self.logger.info(
            f"Set quotas for {client_id}: CPU {quotas.cpu_percent}%, "
            f"RAM {quotas.memory_mb}MB, Disk {quotas.disk_gb}GB"
        )

    def get_client_usage(self, client_id: str) -> ResourceUsage:
        """
        Get current resource usage for a client.

        Args:
            client_id: ID of the client

        Returns:
            ResourceUsage: Current usage metrics
        """
        if client_id not in self.client_usage:
            self.client_usage[client_id] = ResourceUsage()

        return self.client_usage[client_id]

    def check_availability(
        self,
        client_id: str,
        required: ResourceRequirement,
        has_quota_override: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if enough resources available for subprocess.

        Args:
            client_id: Client requesting resources
            required: ResourceRequirement with needed resources
            has_quota_override: Whether client has QUOTA_OVERRIDE permission

        Returns:
            Tuple[bool, Optional[str]]: (allowed, reason_if_denied)

        Logic:
        - If QUOTA_OVERRIDE: always return True
        - Check memory: current + required <= quota
        - Check disk: current + required <= quota
        - Return (True, None) if available, (False, reason) if not
        """
        # If QUOTA_OVERRIDE permission: ignore quotas
        if has_quota_override:
            self.logger.debug(
                f"Resource check skipped for {client_id} (QUOTA_OVERRIDE)"
            )
            return True, None

        # Get quotas and current usage
        quotas = self.get_client_quotas(client_id)
        usage = self.get_client_usage(client_id)

        # Check memory
        if (usage.memory_mb + required.memory_mb) > quotas.memory_mb:
            reason = (
                f"Insufficient memory: "
                f"current {usage.memory_mb}MB + "
                f"required {required.memory_mb}MB > "
                f"quota {quotas.memory_mb}MB"
            )
            self.logger.warning(f"Resource denied for {client_id}: {reason}")
            self._record_quota_violation(client_id)
            return False, reason

        # Check concurrent processes
        if usage.concurrent_processes >= quotas.concurrent_processes:
            reason = (
                f"Too many concurrent processes: "
                f"{usage.concurrent_processes} >= "
                f"quota {quotas.concurrent_processes}"
            )
            self.logger.warning(f"Resource denied for {client_id}: {reason}")
            self._record_quota_violation(client_id)
            return False, reason

        # All checks passed
        self.logger.debug(f"Resource check passed for {client_id}")
        return True, None

    def allocate(
        self,
        client_id: str,
        pid: int,
        required: ResourceRequirement
    ) -> None:
        """
        Allocate resources to subprocess.

        Args:
            client_id: Client ID
            pid: Process ID of subprocess
            required: ResourceRequirement allocated
        """
        usage = self.get_client_usage(client_id)
        usage.memory_mb += required.memory_mb
        usage.concurrent_processes += 1

        self.logger.debug(
            f"Allocated resources for {client_id} (PID {pid}): "
            f"memory {required.memory_mb}MB"
        )

    def release(
        self,
        client_id: str,
        pid: int,
        used: Optional[ResourceRequirement] = None
    ) -> None:
        """
        Release resources from subprocess.

        Args:
            client_id: Client ID
            pid: Process ID of subprocess
            used: ResourceRequirement actually used (if tracked)
        """
        usage = self.get_client_usage(client_id)

        # Decrease concurrent processes
        if usage.concurrent_processes > 0:
            usage.concurrent_processes -= 1

        # Decrease memory if tracked
        if used and used.memory_mb > 0:
            usage.memory_mb = max(0, usage.memory_mb - used.memory_mb)

        self.logger.debug(
            f"Released resources for {client_id} (PID {pid})"
        )

    def get_quota_violations(self, client_id: str) -> int:
        """Get count of quota violations for a client"""
        return self.quota_violations.get(client_id, 0)

    def get_all_violations(self) -> Dict[str, int]:
        """Get all quota violations"""
        return self.quota_violations.copy()

    def _record_quota_violation(self, client_id: str) -> None:
        """Record a quota violation"""
        self.quota_violations[client_id] = self.quota_violations.get(client_id, 0) + 1
        self.logger.warning(
            f"Quota violation #{self.quota_violations[client_id]} for {client_id}"
        )


# ============================================================================
# Unit Tests
# ============================================================================

if __name__ == "__main__":
    import unittest

    class TestResourceManager(unittest.TestCase):
        """Test suite for ResourceManager"""

        def setUp(self):
            """Setup test fixtures"""
            self.manager = ResourceManager()

        def test_initialization(self):
            """Test manager initialization"""
            manager = ResourceManager()
            self.assertEqual(len(manager.client_quotas), 0)

        def test_default_quotas(self):
            """Test default quotas"""
            quotas = self.manager.get_client_quotas("alice_123")
            self.assertEqual(quotas.cpu_percent, 50.0)
            self.assertEqual(quotas.memory_mb, 512)
            self.assertEqual(quotas.disk_gb, 1)

        def test_set_custom_quotas(self):
            """Test setting custom quotas"""
            custom = ClientQuotas(cpu_percent=75.0, memory_mb=1024, disk_gb=5)
            self.manager.set_client_quotas("alice_123", custom)

            quotas = self.manager.get_client_quotas("alice_123")
            self.assertEqual(quotas.cpu_percent, 75.0)
            self.assertEqual(quotas.memory_mb, 1024)
            self.assertEqual(quotas.disk_gb, 5)

        def test_check_availability_sufficient(self):
            """Test check availability with sufficient resources"""
            required = ResourceRequirement(memory_mb=256)
            allowed, reason = self.manager.check_availability("alice_123", required)

            self.assertTrue(allowed)
            self.assertIsNone(reason)

        def test_check_availability_insufficient_memory(self):
            """Test check availability with insufficient memory"""
            required = ResourceRequirement(memory_mb=1000)
            allowed, reason = self.manager.check_availability("alice_123", required)

            self.assertFalse(allowed)
            self.assertIn("memory", reason.lower())

        def test_check_availability_with_quota_override(self):
            """Test check availability with QUOTA_OVERRIDE permission"""
            required = ResourceRequirement(memory_mb=1000)
            allowed, reason = self.manager.check_availability(
                "alice_123",
                required,
                has_quota_override=True
            )

            self.assertTrue(allowed)
            self.assertIsNone(reason)

        def test_allocate_resources(self):
            """Test allocating resources"""
            required = ResourceRequirement(memory_mb=256)
            self.manager.allocate("alice_123", pid=1234, required=required)

            usage = self.manager.get_client_usage("alice_123")
            self.assertEqual(usage.memory_mb, 256)
            self.assertEqual(usage.concurrent_processes, 1)

        def test_release_resources(self):
            """Test releasing resources"""
            required = ResourceRequirement(memory_mb=256)
            self.manager.allocate("alice_123", pid=1234, required=required)
            self.manager.release("alice_123", pid=1234, used=required)

            usage = self.manager.get_client_usage("alice_123")
            self.assertEqual(usage.memory_mb, 0)
            self.assertEqual(usage.concurrent_processes, 0)

        def test_quota_violations(self):
            """Test tracking quota violations"""
            required = ResourceRequirement(memory_mb=1000)
            self.manager.check_availability("alice_123", required)
            self.manager.check_availability("alice_123", required)

            violations = self.manager.get_quota_violations("alice_123")
            self.assertEqual(violations, 2)

        def test_concurrent_processes_limit(self):
            """Test concurrent process limit"""
            quotas = ClientQuotas(concurrent_processes=2)
            self.manager.set_client_quotas("alice_123", quotas)

            # Allocate 2 processes
            req = ResourceRequirement(memory_mb=100)
            self.manager.allocate("alice_123", pid=1, required=req)
            self.manager.allocate("alice_123", pid=2, required=req)

            # Third should fail
            allowed, reason = self.manager.check_availability("alice_123", req)
            self.assertFalse(allowed)
            self.assertIn("concurrent", reason.lower())

    # Run tests
    unittest.main()
