import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    print("Testing imports...")
    from ops_sentinel import runtime_gateway
    print("✓ runtime_gateway imported successfully")

    assert hasattr(runtime_gateway, 'ServiceSnapshot')
    assert hasattr(runtime_gateway, 'ServiceHealth')
    assert hasattr(runtime_gateway, 'RuntimeActionReport')
    print("✓ Data models found")

    assert hasattr(runtime_gateway, 'RuntimeUnavailableError')
    assert hasattr(runtime_gateway, 'ServiceMissingError')
    print("✓ Custom exceptions found")

    assert hasattr(runtime_gateway, 'OpsRuntimeGateway')
    print("✓ OpsRuntimeGateway class found")

def test_data_models():
    print("\nTesting data models...")
    from ops_sentinel.runtime_gateway import RuntimeActionReport, ServiceHealth, ServiceSnapshot
    from datetime import datetime

    container = ServiceSnapshot(
        container_id="abc123",
        name="test-container",
        state="running",
        image="nginx:latest",
        created_at=datetime.now()
    )
    assert container.to_dict() is not None
    assert container.summary() is not None
    print("✓ ServiceSnapshot works")

    health = ServiceHealth(
        service_name="test-container",
        healthy=True,
        state="running"
    )
    assert health.to_dict() is not None
    assert health.summary() is not None
    print("✓ ServiceHealth works")

    result = RuntimeActionReport(
        action="test",
        success=True,
        payload="test data"
    )
    assert result.to_dict() is not None
    print("✓ RuntimeActionReport works")

def test_agent_structure():
    print("\nTesting workflow runtime structure...")
    from ops_sentinel import workflow_runtime

    assert hasattr(workflow_runtime, 'inspect_services_activity')
    assert hasattr(workflow_runtime, 'health_overview_activity')
    assert hasattr(workflow_runtime, 'collect_logs_activity')
    assert hasattr(workflow_runtime, 'recycle_service_activity')
    print("✓ All workflow activities defined")

    assert hasattr(workflow_runtime, 'build_execution_plan_activity')
    assert hasattr(workflow_runtime, 'OpsSentinelWorkflow')
    print("✓ Planner and workflow found")

def main():
    """Run all tests"""
    print("=" * 60)
    print("Ops Sentinel Validation Tests")
    print("=" * 60)
    
    results = []
    
    try:
        test_imports()
        results.append(("Imports", True))
    except Exception:
        results.append(("Imports", False))

    try:
        test_data_models()
        results.append(("Data Models", True))
    except Exception:
        results.append(("Data Models", False))

    try:
        test_agent_structure()
        results.append(("Agent Structure", True))
    except Exception:
        results.append(("Agent Structure", False))
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✓ All tests passed! Code structure is valid.")
        print("\nNote: Docker daemon is not running, so the agent cannot")
        print("connect to Docker. To test with real containers:")
        print("  1. Start Docker Desktop")
        print("  2. Run: python console.py worker")
        print("  3. Run: python console.py")
        return 0
    else:
        print("\n✗ Some tests failed. Check errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
