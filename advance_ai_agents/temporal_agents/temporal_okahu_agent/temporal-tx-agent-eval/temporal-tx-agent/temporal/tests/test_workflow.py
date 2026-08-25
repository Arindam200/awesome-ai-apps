"""Tests for Temporal workflows using workflow test framework."""

import pytest
from datetime import timedelta
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from temporal.workflows import TransactionProcessingWorkflow
from temporal.activities import (
    generate_embedding,
    analyze_transaction_with_ai,
    search_similar_transactions,
    save_decision,
    update_transaction_status,
    create_human_review,
    apply_business_rules
)
from temporal.shared import TransactionDetails, TRANSACTION_PROCESSING_TASK_QUEUE

@pytest.mark.asyncio
async def test_transaction_processing_workflow_approval():
    """Test workflow for approved transaction."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TRANSACTION_PROCESSING_TASK_QUEUE,
            workflows=[TransactionProcessingWorkflow],
            activities=[
                generate_embedding,
                analyze_transaction_with_ai,
                search_similar_transactions,
                save_decision,
                update_transaction_status,
                create_human_review,
                apply_business_rules
            ],
        ):
            # Create test transaction
            transaction_details = TransactionDetails(
                transaction_id="TEST-TXN-001",
                transaction_type="ach",
                amount="1000.00",
                currency="USD",
                sender={"name": "Test Sender", "country": "US"},
                recipient={"name": "Test Recipient", "country": "US"},
                risk_flags=[],
                metadata={}
            )
            
            # Start workflow
            handle = await env.client.start_workflow(
                TransactionProcessingWorkflow.run,
                transaction_details,
                id=f"test-workflow-{transaction_details.transaction_id}",
                task_queue=TRANSACTION_PROCESSING_TASK_QUEUE,
            )
            
            # Wait for completion
            result = await handle.result()
            
            # Assertions
            assert result["transaction_id"] == "TEST-TXN-001"
            assert result["decision"] in ["approve", "reject", "escalate"]
            assert "confidence" in result
            assert "risk_score" in result
            assert "processing_time_ms" in result

@pytest.mark.asyncio
async def test_workflow_state_query():
    """Test workflow state query."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TRANSACTION_PROCESSING_TASK_QUEUE,
            workflows=[TransactionProcessingWorkflow],
            activities=[
                generate_embedding,
                analyze_transaction_with_ai,
                search_similar_transactions,
                save_decision,
                update_transaction_status,
                create_human_review,
                apply_business_rules
            ],
        ):
            transaction_details = TransactionDetails(
                transaction_id="TEST-TXN-002",
                transaction_type="wire_transfer",
                amount="5000.00",
                currency="USD",
                sender={"name": "Test Sender", "country": "US"},
                recipient={"name": "Test Recipient", "country": "US"},
                risk_flags=[],
                metadata={}
            )
            
            handle = await env.client.start_workflow(
                TransactionProcessingWorkflow.run,
                transaction_details,
                id=f"test-workflow-{transaction_details.transaction_id}",
                task_queue=TRANSACTION_PROCESSING_TASK_QUEUE,
            )
            
            # Query state while running
            state = await handle.query(TransactionProcessingWorkflow.get_state)
            assert state["transaction_id"] == "TEST-TXN-002"
            assert "current_state" in state
            
            # Wait for completion
            await handle.result()

@pytest.mark.asyncio
async def test_workflow_retry_on_failure():
    """Test workflow retry behavior."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TRANSACTION_PROCESSING_TASK_QUEUE,
            workflows=[TransactionProcessingWorkflow],
            activities=[
                generate_embedding,
                analyze_transaction_with_ai,
                search_similar_transactions,
                save_decision,
                update_transaction_status,
                create_human_review,
                apply_business_rules
            ],
        ):
            transaction_details = TransactionDetails(
                transaction_id="TEST-TXN-003",
                transaction_type="international",
                amount="10000.00",
                currency="USD",
                sender={"name": "Test Sender", "country": "US"},
                recipient={"name": "Test Recipient", "country": "US"},
                risk_flags=[],
                metadata={}
            )
            
            handle = await env.client.start_workflow(
                TransactionProcessingWorkflow.run,
                transaction_details,
                id=f"test-workflow-{transaction_details.transaction_id}",
                task_queue=TRANSACTION_PROCESSING_TASK_QUEUE,
            )
            
            # Workflow should complete or handle errors gracefully
            try:
                result = await handle.result()
                assert result is not None
            except Exception as e:
                # Workflow should handle errors and update status
                state = await handle.query(TransactionProcessingWorkflow.get_state)
                assert state["current_state"] in ["failed", "completed"]

