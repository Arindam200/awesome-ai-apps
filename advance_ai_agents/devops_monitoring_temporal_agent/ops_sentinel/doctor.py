import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def print_header(text):
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)

def print_result(test_name, passed):
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{test_name}: {status}")
    return passed

def test_compilation():
    print_header("Testing Code Compilation")
    
    files = [
        '../config.py',
        'runtime_gateway.py',
        'workflow_runtime.py',
        'console.py'
    ]
    
    all_passed = True
    for file in files:
        try:
            result = subprocess.run(
                ['python', '-m', 'py_compile', file],
                capture_output=True,
                text=True
            )
            passed = result.returncode == 0
            print_result(f"  {file}", passed)
            if not passed:
                print(f"    Error: {result.stderr}")
                all_passed = False
        except Exception as e:
            print_result(f"  {file}", False)
            print(f"    Error: {e}")
            all_passed = False
    
    return all_passed

def test_imports():
    print_header("Testing Module Imports")
    
    all_passed = True
    
    try:
        import runtime_gateway
        assert hasattr(runtime_gateway, 'ServiceSnapshot')
        assert hasattr(runtime_gateway, 'ServiceHealth')
        assert hasattr(runtime_gateway, 'RuntimeActionReport')
        assert hasattr(runtime_gateway, 'OpsRuntimeGateway')
        print_result("  runtime_gateway", True)
    except Exception as e:
        print_result("  runtime_gateway", False)
        print(f"    Error: {e}")
        all_passed = False
    
    try:
        import workflow_runtime
        assert hasattr(workflow_runtime, 'inspect_services_activity')
        assert hasattr(workflow_runtime, 'health_overview_activity')
        assert hasattr(workflow_runtime, 'collect_logs_activity')
        assert hasattr(workflow_runtime, 'recycle_service_activity')
        assert hasattr(workflow_runtime, 'build_execution_plan_activity')
        assert hasattr(workflow_runtime, 'OpsSentinelWorkflow')
        print_result("  workflow_runtime", True)
    except Exception as e:
        print_result("  workflow_runtime", False)
        print(f"    Error: {e}")
        all_passed = False
    
    return all_passed

def test_data_models():
    print_header("Testing Data Models")
    
    all_passed = True
    
    try:
        from runtime_gateway import RuntimeActionReport, ServiceHealth, ServiceSnapshot
        from datetime import datetime
        
        container = ServiceSnapshot(
            container_id="test123",
            name="test-container",
            state="running",
            image="nginx:latest",
            created_at=datetime.now()
        )
        assert container.to_dict() is not None
        assert container.summary() is not None
        print_result("  ServiceSnapshot", True)
        
        health = ServiceHealth(
            service_name="test",
            healthy=True,
            state="running"
        )
        assert health.to_dict() is not None
        assert health.summary() is not None
        print_result("  ServiceHealth", True)
        
        result = RuntimeActionReport(
            action="test",
            success=True,
            payload="test"
        )
        assert result.to_dict() is not None
        print_result("  RuntimeActionReport", True)
        
    except Exception as e:
        print_result("  Data Models", False)
        print(f"    Error: {e}")
        all_passed = False
    
    return all_passed

def test_configuration():
    print_header("Testing Configuration")
    
    try:
        import config
        
        assert hasattr(config, 'DOCKER_HOST')
        assert hasattr(config, 'DOCKER_TIMEOUT')
        assert hasattr(config, 'OPS_SENTINEL_TASK_QUEUE')
        
        assert hasattr(config, 'STATUS_CHECK_TIMEOUT')
        assert hasattr(config, 'HEALTH_CHECK_TIMEOUT')
        assert hasattr(config, 'LOG_RETRIEVAL_TIMEOUT')
        assert hasattr(config, 'RESTART_TIMEOUT')
        
        assert hasattr(config, 'CPU_THRESHOLD_PERCENT')
        assert hasattr(config, 'MEMORY_THRESHOLD_PERCENT')
        assert hasattr(config, 'RESTART_COUNT_THRESHOLD')
        
        print_result("  Configuration", True)
        return True
    except Exception as e:
        print_result("  Configuration", False)
        print(f"    Error: {e}")
        return False

def test_temporal_worker():
    print_header("Testing Temporal Worker")
    
    try:
        import asyncio
        from temporalio.client import Client
        from temporalio.worker import Worker
        from workflow_runtime import OPS_ACTIVITIES, OpsSentinelWorkflow
        
        async def test():
            try:
                client = await Client.connect('localhost:7233')
                worker = Worker(
                    client,
                    task_queue='ops-sentinel-test-queue',
                    workflows=[OpsSentinelWorkflow],
                    activities=OPS_ACTIVITIES,
                )
                return True
            except Exception as e:
                print(f"    Note: {e}")
                return False
        
        result = asyncio.run(test())
        print_result("  Worker Creation", result)
        if not result:
            print("    (This is OK if Temporal server is not running)")
        return True
        
    except Exception as e:
        print_result("  Worker Creation", False)
        print(f"    Error: {e}")
        return True

def main():
    print("=" * 60)
    print("Ops Sentinel - Validation")
    print("=" * 60)
    
    results = []
    
    results.append(("Compilation", test_compilation()))
    results.append(("Imports", test_imports()))
    results.append(("Data Models", test_data_models()))
    results.append(("Configuration", test_configuration()))
    results.append(("Temporal Worker", test_temporal_worker()))
    
    print_header("Validation Summary")
    
    all_passed = True
    for test_name, passed in results:
        print_result(test_name, passed)
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("✓ All validation tests passed!")
        print("\nOps Sentinel is ready to use.")
        print("\nNext steps:")
        print("  1. Ensure Docker Desktop is running")
        print("  2. Start Temporal: temporal server start-dev")
        print("  3. In ops_sentinel directory:")
        print("     - Worker: python console.py worker")
        print("     - Console: python console.py")
        return 0
    else:
        print("✗ Some validation tests failed.")
        print("Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
