"""Integration test script to test Temporal workflow end-to-end."""

import asyncio
import sys
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from temporalio.client import Client
from temporal.workflows import TransactionProcessingWorkflow
from temporal.shared import TransactionDetails, TRANSACTION_PROCESSING_TASK_QUEUE
from utils.config import config
from database.connection import connect_to_couchbase
from database.repositories import TransactionRepository, DecisionRepository
from database.schemas import Transaction, TransactionStatus

async def test_workflow():
    """Test the complete workflow by submitting a transaction."""
    print("🧪 Testing Temporal Workflow Integration")
    print("=" * 60)
    
    # Step 1: Connect to Temporal
    print("\n1. Connecting to Temporal...")
    try:
        client = await Client.connect(
            config.TEMPORAL_HOST,
            namespace=config.TEMPORAL_NAMESPACE
        )
        print(f"   ✅ Connected to Temporal at {config.TEMPORAL_HOST}")
    except Exception as e:
        print(f"   ❌ Failed to connect: {e}")
        return False
    
    # Step 2: Connect to Couchbase
    print("\n2. Connecting to Couchbase...")
    try:
        await connect_to_couchbase()
        print("   ✅ Connected to Couchbase")
    except Exception as e:
        print(f"   ❌ Failed to connect: {e}")
        return False
    
    # Step 3: Create test transaction
    print("\n3. Creating test transaction...")
    test_transaction = Transaction(
        transaction_type="wire_transfer",
        amount=1000.00,
        currency="USD",
        sender={"name": "Test Sender", "country": "US", "account_number": "TEST001"},
        recipient={"name": "Test Recipient", "country": "US", "account_number": "TEST002"},
        description="Integration test transaction",
        status=TransactionStatus.PENDING
    )
    
    try:
        transaction_id = await TransactionRepository.create_transaction(test_transaction)
        print(f"   ✅ Created transaction: {transaction_id}")
    except Exception as e:
        print(f"   ❌ Failed to create transaction: {e}")
        return False
    
    # Step 4: Prepare workflow input
    print("\n4. Preparing workflow input...")
    transaction_details = TransactionDetails(
        transaction_id=transaction_id,
        transaction_type="wire_transfer",
        amount="1000.00",
        currency="USD",
        sender=test_transaction.sender,
        recipient=test_transaction.recipient,
        risk_flags=[],
        metadata={"test": True, "timestamp": datetime.now().isoformat()}
    )
    print("   ✅ Workflow input prepared")
    
    # Step 5: Start workflow
    print("\n5. Starting Temporal workflow...")
    workflow_id = f"test-workflow-{transaction_id}"
    try:
        handle = await client.start_workflow(
            TransactionProcessingWorkflow.run,
            transaction_details,
            id=workflow_id,
            task_queue=TRANSACTION_PROCESSING_TASK_QUEUE,
        )
        print(f"   ✅ Workflow started: {workflow_id}")
        print(f"   Run ID: {handle.result_run_id}")
    except Exception as e:
        print(f"   ❌ Failed to start workflow: {e}")
        return False
    
    # Step 6: Monitor workflow progress
    print("\n6. Monitoring workflow progress...")
    print("   (This may take 30-60 seconds)")
    
    max_wait = 120  # 2 minutes max
    start_time = time.time()
    last_state = None
    signal_sent = False
    
    while time.time() - start_time < max_wait:
        try:
            # Query workflow state
            state = await handle.query(TransactionProcessingWorkflow.get_state)
            current_state = state.get("current_state", "unknown")
            
            if current_state != last_state:
                print(f"   📍 State: {current_state}")
                if state.get("stages_completed"):
                    print(f"      Completed stages: {', '.join(state['stages_completed'])}")
                last_state = current_state
            
            # If workflow is waiting for human review, send a signal to complete it
            if current_state == "escalated" and not signal_sent:
                print("   📤 Workflow is waiting for human review, sending approval signal...")
                try:
                    await handle.signal(TransactionProcessingWorkflow.human_review_complete, "approve")
                    signal_sent = True
                    print("   ✅ Human review signal sent (approved)")
                except Exception as signal_err:
                    print(f"   ⚠️  Error sending signal: {signal_err}")
            
            # Check if workflow is complete
            if current_state in ["completed", "failed"]:
                break
            
            await asyncio.sleep(2)
        except Exception as e:
            print(f"   ⚠️  Error querying state: {e}")
            await asyncio.sleep(2)
    
    # Step 7: Get workflow result (with timeout for human review)
    print("\n7. Getting workflow result...")
    print("   (If workflow is waiting for human review, it will complete after signal)")
    try:
        # Use a reasonable timeout for testing (30 seconds should be enough after signal)
        result = await asyncio.wait_for(handle.result(), timeout=60.0)
        print("   ✅ Workflow completed!")
        print(f"      Decision: {result.get('decision')}")
        print(f"      Confidence: {result.get('confidence')}")
        print(f"      Risk Score: {result.get('risk_score')}")
        print(f"      Processing Time: {result.get('processing_time_ms')}ms")
        print(f"      Decision ID: {result.get('decision_id')}")
    except Exception as e:
        print(f"   ❌ Workflow failed: {e}")
        # Print detailed error information
        import traceback
        from temporalio.exceptions import ActivityError, ApplicationError
        from temporalio.client import WorkflowFailureError
        
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error module: {type(e).__module__}")
        
        # Try to extract more details from the error chain
        current_error = e
        depth = 0
        while current_error and depth < 5:
            print(f"\n   Error at depth {depth}: {type(current_error).__name__}")
            print(f"   Message: {str(current_error)}")
            
            # Check for WorkflowFailureError
            if isinstance(current_error, WorkflowFailureError):
                print(f"   ✅ WorkflowFailureError detected")
                if hasattr(current_error, 'cause') and current_error.cause:
                    print(f"   Cause: {type(current_error.cause).__name__}: {current_error.cause}")
            
            # Check for ActivityError
            if isinstance(current_error, ActivityError):
                print(f"   ✅ Failed activity: {current_error.activity_type}")
                print(f"   Activity ID: {current_error.activity_id}")
                print(f"   Retry state: {current_error.retry_state}")
                
                # Try to get failure details
                if hasattr(current_error, 'failure') and current_error.failure:
                    failure = current_error.failure
                    try:
                        if hasattr(failure, 'message') and failure.message:
                            print(f"   Failure message: {failure.message}")
                    except Exception:
                        pass
                    
                    try:
                        if hasattr(failure, 'application_failure_info'):
                            app_failure = failure.application_failure_info
                            if app_failure:
                                print(f"   Application error type: {getattr(app_failure, 'type', 'N/A')}")
                                # Try to get message - it might be in different places
                                if hasattr(app_failure, 'message'):
                                    print(f"   Application error message: {app_failure.message}")
                                elif hasattr(app_failure, 'typed_failure_info'):
                                    print(f"   Application error details available")
                    except Exception as app_err:
                        # Silently skip if we can't access application failure info
                        pass
            
            # Check for ApplicationError
            if isinstance(current_error, ApplicationError):
                print(f"   ✅ Application error type: {current_error.type}")
                print(f"   Non-retryable: {current_error.non_retryable}")
                if current_error.details:
                    print(f"   Details: {current_error.details}")
            
            # Move to next level
            if hasattr(current_error, '__cause__') and current_error.__cause__:
                current_error = current_error.__cause__
            elif hasattr(current_error, 'cause') and current_error.cause:
                current_error = current_error.cause
            else:
                break
            depth += 1
        
        # Print full traceback for debugging
        print("\n   Full traceback:")
        traceback.print_exception(type(e), e, e.__traceback__, limit=10)
        
        # Try to get final state
        try:
            state = await handle.query(TransactionProcessingWorkflow.get_state)
            print(f"\n   Final state: {state}")
        except Exception as state_err:
            print(f"   Could not get final state: {state_err}")
        return False
    
    # Step 8: Verify decision in database
    print("\n8. Verifying decision in database...")
    try:
        decision = await DecisionRepository.get_decision_by_transaction(transaction_id)
        if decision:
            print("   ✅ Decision found in database")
            print(f"      Decision: {decision.get('decision')}")
            print(f"      Confidence: {decision.get('confidence_score')}")
        else:
            print("   ⚠️  Decision not found in database (may take a moment to appear)")
    except Exception as e:
        print(f"   ⚠️  Error checking decision: {e}")
    
    # Step 9: Verify transaction status
    print("\n9. Verifying transaction status...")
    try:
        transaction = await TransactionRepository.get_transaction(transaction_id)
        if transaction:
            print(f"   ✅ Transaction status: {transaction.get('status')}")
        else:
            print("   ⚠️  Transaction not found")
    except Exception as e:
        print(f"   ⚠️  Error checking transaction: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Integration test completed!")
    print(f"\n📊 View workflow in Temporal UI:")
    print(f"   http://localhost:8080/namespaces/{config.TEMPORAL_NAMESPACE}/workflows/{workflow_id}")
    print(f"\n📝 Transaction ID: {transaction_id}")
    print(f"🔗 Workflow ID: {workflow_id}")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_workflow())
    sys.exit(0 if success else 1)

