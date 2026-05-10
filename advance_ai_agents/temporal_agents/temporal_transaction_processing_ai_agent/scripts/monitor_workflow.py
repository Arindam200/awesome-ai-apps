"""Monitor a running Temporal workflow."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from temporalio.client import Client
from temporal.workflows import TransactionProcessingWorkflow
from utils.config import config

async def monitor_workflow(workflow_id: str):
    """Monitor a workflow by ID."""
    print(f"🔍 Monitoring Workflow: {workflow_id}")
    print("=" * 60)
    
    # Connect to Temporal
    client = await Client.connect(
        config.TEMPORAL_HOST,
        namespace=config.TEMPORAL_NAMESPACE
    )
    
    # Get workflow handle
    handle = client.get_workflow_handle(workflow_id)
    
    # Query state
    try:
        state = await handle.query(TransactionProcessingWorkflow.get_state)
        print("\n📊 Current State:")
        print(f"   Transaction ID: {state.get('transaction_id')}")
        print(f"   Current State: {state.get('current_state')}")
        print(f"   Decision: {state.get('decision')}")
        print(f"   Confidence: {state.get('confidence')}")
        print(f"   Stages Completed: {', '.join(state.get('stages_completed', []))}")
        if state.get('error_message'):
            print(f"   Error: {state.get('error_message')}")
        print(f"   Retry Count: {state.get('retry_count', 0)}")
    except Exception as e:
        print(f"❌ Error querying workflow: {e}")
        return
    
    # Try to get result if completed
    try:
        result = await handle.result()
        print("\n✅ Workflow Result:")
        print(f"   Decision: {result.get('decision')}")
        print(f"   Confidence: {result.get('confidence')}")
        print(f"   Risk Score: {result.get('risk_score')}")
        print(f"   Processing Time: {result.get('processing_time_ms')}ms")
    except:
        print("\n⏳ Workflow is still running...")
        print(f"\n🔗 View in Temporal UI:")
        print(f"   http://localhost:8080/namespaces/{config.TEMPORAL_NAMESPACE}/workflows/{workflow_id}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/monitor_workflow.py <workflow_id>")
        sys.exit(1)
    
    workflow_id = sys.argv[1]
    asyncio.run(monitor_workflow(workflow_id))

