#!/usr/bin/env python
"""
Phase 3 Comprehensive Test Runner

Tests all Phase 3 components:
- JSONStore (8 tests)
- TokenManager (12 tests)
- JWTHandler (12 tests)
- ClientManager (18 tests)
- AuditLogger (14 tests)

Total: 64 tests
"""

import sys
import subprocess
from pathlib import Path


def run_module_tests(module_name: str, display_name: str) -> tuple[int, int]:
    """
    Run unittest tests for a module

    Args:
        module_name: Python module path
        display_name: Display name for output

    Returns:
        Tuple of (tests_run, failures)
    """
    print(f"\n{'='*70}")
    print(f"Testing: {display_name}")
    print('='*70)

    result = subprocess.run(
        [sys.executable, "-m", module_name, "-v"],
        capture_output=True,
        text=True,
    )

    # Print output
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    # Parse test count
    output = result.stdout + result.stderr
    if "Ran" in output and "tests" in output:
        # Extract number of tests run
        for line in output.split('\n'):
            if "Ran" in line and "tests" in line:
                parts = line.split()
                try:
                    num_tests = int(parts[1])
                    if "OK" in output:
                        return num_tests, 0
                    else:
                        return num_tests, 1  # At least one failure
                except (IndexError, ValueError):
                    pass

    return 0, 1 if result.returncode != 0 else 0


def main():
    """Run all Phase 3 tests"""
    print("\n" + "="*70)
    print("PHASE 3 - COMPREHENSIVE TEST SUITE")
    print("="*70)

    modules = [
        ("mcp_server.persistence.json_store", "JSONStore (Base JSON File Handling)"),
        ("mcp_server.persistence.token_store", "TokenManager (Token Persistence)"),
        ("mcp_server.security.authentication.jwt_handler", "JWTHandler (JWT Generation/Validation)"),
        ("mcp_server.security.authentication.client_manager", "ClientManager (Client Credentials)"),
        ("mcp_server.persistence.audit_store", "AuditLogger (Audit Trail)"),
    ]

    total_tests = 0
    total_failures = 0
    results = []

    for module_name, display_name in modules:
        tests_run, failures = run_module_tests(module_name, display_name)
        total_tests += tests_run
        total_failures += failures
        results.append((display_name, tests_run, failures))

    # Print summary
    print("\n" + "="*70)
    print("PHASE 3 TEST SUMMARY")
    print("="*70)

    for display_name, tests_run, failures in results:
        status = "✓ PASS" if failures == 0 else "✗ FAIL"
        print(f"{status:8} {display_name:50} ({tests_run} tests)")

    print("="*70)
    print(f"Total Tests: {total_tests}")
    print(f"Total Failures: {total_failures}")
    print("="*70)

    if total_failures == 0:
        print("\n✓ ALL PHASE 3 TESTS PASSING!")
        return 0
    else:
        print(f"\n✗ {total_failures} MODULE(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
