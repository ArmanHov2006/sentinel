"""Comprehensive test runner for everything implemented today."""

import os
import sys
import subprocess
import time

# Fix Windows console encoding
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    sys.stdout.reconfigure(encoding='utf-8')

# Set required environment variable for testing
os.environ.setdefault("openai_api_key", "test-key-for-testing")

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("=" * 70)
print("COMPREHENSIVE TEST SUITE - ALL TODAY'S WORK")
print("=" * 70)

# Test results tracker
results = {
    "passed": [],
    "failed": []
}


def run_test(test_name, test_command, description):
    """Run a test and track results."""
    print(f"\n{'=' * 70}")
    print(f"TEST: {test_name}")
    print(f"Description: {description}")
    print(f"{'=' * 70}")
    
    try:
        result = subprocess.run(
            test_command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__)
        )
        
        if result.returncode == 0:
            print(result.stdout)
            results["passed"].append(test_name)
            print(f"✅ {test_name} PASSED")
            return True
        else:
            print(result.stdout)
            print(result.stderr)
            results["failed"].append(test_name)
            print(f"❌ {test_name} FAILED")
            return False
    except Exception as e:
        print(f"❌ Error running {test_name}: {e}")
        results["failed"].append(test_name)
        return False


# === TEST SUITE ===

tests = [
    # Unit tests with pytest
    (
        "Circuit Breaker Unit Tests",
        'python -m pytest tests/test_circuit_breaker.py -v',
        "Test circuit breaker states, transitions, and failure handling"
    ),
    (
        "API Endpoints Unit Tests",
        'python -m pytest tests/test_api_endpoints.py -v',
        "Test FastAPI endpoints (health, chat completions)"
    ),
    (
        "Sentinel Additions Tests",
        'python -m pytest tests/test_sentinel_additions.py -v',
        "Test domain models and exceptions"
    ),
    
    # Integration tests (if server is running)
    (
        "Session 1 Sentinel Test",
        'python test_session1_sentinel.py',
        "Test all Session 1 components"
    ),
]

# Run all tests
print("\n" + "=" * 70)
print("RUNNING ALL TESTS")
print("=" * 70)

all_passed = True
for test_name, command, description in tests:
    if not run_test(test_name, command, description):
        all_passed = False
    time.sleep(0.5)  # Small delay between tests

# === SUMMARY ===
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)

print(f"\n✅ Passed: {len(results['passed'])}")
for test in results["passed"]:
    print(f"   - {test}")

print(f"\n❌ Failed: {len(results['failed'])}")
for test in results["failed"]:
    print(f"   - {test}")

print(f"\n{'=' * 70}")
if all_passed:
    print("🎉 ALL TESTS PASSED!")
    print("=" * 70)
    sys.exit(0)
else:
    print("⚠️  SOME TESTS FAILED")
    print("=" * 70)
    sys.exit(1)
