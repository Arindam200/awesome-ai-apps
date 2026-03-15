"""Temporal workflows for transaction processing with enhanced state management and resilience."""

import logging
from datetime import timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporal.shared import TransactionDetails, DecisionResult
from temporal.activities import (
    generate_embedding,
    analyze_transaction_with_ai,
    search_similar_transactions,
    save_decision,
    update_transaction_status,
    create_human_review,
    apply_business_rules
)

logger = logging.getLogger(__name__)

class WorkflowState(Enum):
    """Workflow execution states."""
    INITIALIZED = "initialized"
    EMBEDDING_GENERATED = "embedding_generated"
    SIMILAR_TRANSACTIONS_FOUND = "similar_transactions_found"
    AI_ANALYSIS_COMPLETE = "ai_analysis_complete"
    BUSINESS_RULES_APPLIED = "business_rules_applied"
    DECISION_SAVED = "decision_saved"
    STATUS_UPDATED = "status_updated"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"

@dataclass
class WorkflowExecutionState:
    """Workflow execution state for durability and recovery."""
    transaction_id: str
    current_state: WorkflowState = WorkflowState.INITIALIZED
    embedding: Optional[List[float]] = None
    similar_transactions: List[Dict] = field(default_factory=list)
    decision_result: Optional[DecisionResult] = None
    decision_id: Optional[str] = None
    processing_time_ms: int = 0
    error_message: Optional[str] = None
    retry_count: int = 0
    stages_completed: List[str] = field(default_factory=list)

@workflow.defn
class TransactionProcessingWorkflow:
    """Workflow for processing financial transactions with state management and resilience."""
    
    def __init__(self):
        self.state: Optional[WorkflowExecutionState] = None
        self.human_review_decision: Optional[str] = None
        self._human_review_signal_received = False
    
    @workflow.run
    async def run(self, transaction_details: TransactionDetails) -> Dict:
        """Main workflow execution with state management and error recovery."""
        # Use workflow.now() instead of datetime.now() for determinism
        start_time = workflow.now()
        self.state = WorkflowExecutionState(transaction_id=transaction_details.transaction_id)
        
        workflow.logger.info(f"Starting transaction processing workflow for {self.state.transaction_id}")
        
        try:
            # Step 1: Generate embedding for vector search
            await self._execute_with_state_tracking(
                "generate_embedding",
                self._generate_embedding,
                transaction_details,
                WorkflowState.EMBEDDING_GENERATED
            )
            
            # Step 2: Search for similar transactions
            await self._execute_with_state_tracking(
                "search_similar_transactions",
                self._search_similar_transactions,
                transaction_details,
                WorkflowState.SIMILAR_TRANSACTIONS_FOUND
            )
            
            # Step 3: Apply business rules (compliance checks, amount limits, etc.)
            await self._execute_with_state_tracking(
                "apply_business_rules",
                self._apply_business_rules,
                transaction_details,
                WorkflowState.BUSINESS_RULES_APPLIED
            )
            
            # Step 4: Analyze transaction with AI
            await self._execute_with_state_tracking(
                "analyze_transaction_with_ai",
                self._analyze_transaction_with_ai,
                transaction_details,
                WorkflowState.AI_ANALYSIS_COMPLETE
            )
            
            # Step 5: Check if human review is needed
            if self.state.decision_result and self.state.decision_result.decision == "escalate":
                await self._handle_human_review(transaction_details)
            
            # Step 6: Calculate processing time
            # Use workflow.now() instead of datetime.now() for determinism
            end_time = workflow.now()
            duration = end_time - start_time
            self.state.processing_time_ms = int(duration.total_seconds() * 1000)
            
            # Step 7: Save decision
            await self._execute_with_state_tracking(
                "save_decision",
                self._save_decision,
                transaction_details,
                WorkflowState.DECISION_SAVED
            )
            
            # Step 8: Update transaction status
            await self._execute_with_state_tracking(
                "update_transaction_status",
                self._update_transaction_status,
                transaction_details,
                WorkflowState.STATUS_UPDATED
            )
            
            self.state.current_state = WorkflowState.COMPLETED
            workflow.logger.info(f"Completed workflow for {self.state.transaction_id} with decision: {self.state.decision_result.decision}")
            
            return {
                "transaction_id": self.state.transaction_id,
                "decision": self.state.decision_result.decision,
                "confidence": self.state.decision_result.confidence,
                "risk_score": self.state.decision_result.risk_score,
                "decision_id": self.state.decision_id,
                "processing_time_ms": self.state.processing_time_ms,
                "state": self.state.current_state.value
            }
            
        except Exception as e:
            workflow.logger.error(f"Error in workflow for {self.state.transaction_id}: {e}")
            self.state.current_state = WorkflowState.FAILED
            self.state.error_message = str(e)
            
            # Compensation: Update transaction status to failed
            try:
                await workflow.execute_activity(
                    update_transaction_status,
                    args=[self.state.transaction_id, "failed"],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=1)
                )
            except Exception as comp_e:
                workflow.logger.error(f"Compensation failed: {comp_e}", exc_info=True)
                # Still raise original exception to fail workflow
            
            # Explicitly fail workflow with ApplicationError
            from temporalio.exceptions import ApplicationError
            raise ApplicationError(
                f"Workflow failed: {str(e)}",
                type="WorkflowExecutionError"
            ) from e
    
    async def _generate_embedding(self, transaction_details: TransactionDetails) -> List[float]:
        """Generate embedding activity wrapper."""
        transaction_data = self._build_transaction_data(transaction_details)
        
        embedding = await workflow.execute_activity(
            generate_embedding,
            transaction_data,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(seconds=10),
                maximum_attempts=3,
                non_retryable_error_types=["ValueError", "TypeError"]
            )
        )
        self.state.embedding = embedding
        return embedding
    
    async def _search_similar_transactions(self, transaction_details: TransactionDetails) -> List[Dict]:
        """Search similar transactions activity wrapper."""
        transaction_data = self._build_transaction_data(transaction_details)
        
        similar = await workflow.execute_activity(
            search_similar_transactions,
            args=[transaction_data, self.state.embedding],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(seconds=10),
                maximum_attempts=3
            )
        )
        self.state.similar_transactions = similar
        return similar
    
    async def _apply_business_rules(self, transaction_details: TransactionDetails) -> Dict:
        """Apply business rules activity wrapper."""
        transaction_data = self._build_transaction_data(transaction_details)
        
        rules_result = await workflow.execute_activity(
            apply_business_rules,
            transaction_data,
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(seconds=5),
                maximum_attempts=2,
                non_retryable_error_types=["ComplianceViolation"]
            )
        )
        return rules_result
    
    async def _analyze_transaction_with_ai(self, transaction_details: TransactionDetails) -> DecisionResult:
        """Analyze transaction with AI activity wrapper."""
        transaction_data = self._build_transaction_data(transaction_details)
        context = {
            "similar_transactions": self.state.similar_transactions,
            "embedding": self.state.embedding
        }
        
        decision_result = await workflow.execute_activity(
            analyze_transaction_with_ai,
            args=[transaction_data, context],
            start_to_close_timeout=timedelta(seconds=90),  # Longer timeout for AI
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(seconds=30),
                maximum_attempts=3
            )
        )
        self.state.decision_result = decision_result
        return decision_result
    
    async def _handle_human_review(self, transaction_details: TransactionDetails) -> None:
        """Handle human review escalation."""
        self.state.current_state = WorkflowState.ESCALATED
        
        # Create human review record
        review_id = await workflow.execute_activity(
            create_human_review,
            args=[self.state.transaction_id, self.state.decision_result],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        workflow.logger.info(f"Created human review {review_id} for transaction {self.state.transaction_id}")
        
        # Wait for human review signal (with timeout)
        try:
            await workflow.wait_condition(
                lambda: self._human_review_signal_received,
                timeout=timedelta(days=7)  # 7 days for human review
            )
            
            # Update decision based on human review
            if self.human_review_decision and self.state.decision_result:
                self.state.decision_result.decision = self.human_review_decision
                workflow.logger.info(f"Human review decision received: {self.human_review_decision}")
        except TimeoutError:
            workflow.logger.warning(f"Human review timeout for transaction {self.state.transaction_id}")
            # Default to reject on timeout
            if self.state.decision_result:
                self.state.decision_result.decision = "reject"
                if self.state.decision_result.reasoning:
                    self.state.decision_result.reasoning["primary_reasoning"] = "Human review timeout - defaulting to reject"
    
    @workflow.signal
    def human_review_complete(self, decision: str) -> None:
        """Signal handler for human review completion."""
        self.human_review_decision = decision
        self._human_review_signal_received = True
        workflow.logger.info(f"Human review signal received: {decision}")
    
    @workflow.query
    def get_state(self) -> Dict:
        """Query handler to get current workflow state."""
        if not self.state:
            return {"status": "not_initialized"}
        
        return {
            "transaction_id": self.state.transaction_id,
            "current_state": self.state.current_state.value,
            "decision": self.state.decision_result.decision if self.state.decision_result else None,
            "confidence": self.state.decision_result.confidence if self.state.decision_result else None,
            "stages_completed": self.state.stages_completed,
            "error_message": self.state.error_message,
            "retry_count": self.state.retry_count
        }
    
    async def _save_decision(self, transaction_details: TransactionDetails) -> str:
        """Save decision activity wrapper."""
        decision_id = await workflow.execute_activity(
            save_decision,
            args=[self.state.transaction_id, self.state.decision_result, self.state.processing_time_ms],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(seconds=10),
                maximum_attempts=5  # More retries for critical database operation
            )
        )
        self.state.decision_id = decision_id
        return decision_id
    
    async def _update_transaction_status(self, transaction_details: TransactionDetails) -> None:
        """Update transaction status activity wrapper."""
        status_map = {
            "approve": "approved",
            "reject": "rejected",
            "escalate": "pending_review"
        }
        # Add null check for decision_result
        if self.state.decision_result:
            new_status = status_map.get(self.state.decision_result.decision, "pending")
        else:
            new_status = "pending"
        
        await workflow.execute_activity(
            update_transaction_status,
            args=[self.state.transaction_id, new_status],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(seconds=10),
                maximum_attempts=5  # More retries for critical database operation
            )
        )
    
    async def _execute_with_state_tracking(
        self,
        stage_name: str,
        func,
        transaction_details: TransactionDetails,
        next_state: WorkflowState
    ):
        """Execute a stage with state tracking and error handling."""
        try:
            self.state.retry_count = 0
            result = await func(transaction_details)
            self.state.current_state = next_state
            self.state.stages_completed.append(stage_name)
            return result
        except Exception as e:
            self.state.retry_count += 1
            self.state.error_message = f"Error in {stage_name}: {str(e)}"
            raise
    
    def _build_transaction_data(self, transaction_details: TransactionDetails) -> Dict:
        """Build transaction data dictionary from TransactionDetails."""
        return {
            "transaction_id": transaction_details.transaction_id,
            "transaction_type": transaction_details.transaction_type,
            "amount": float(transaction_details.amount),
            "currency": transaction_details.currency,
            "sender": transaction_details.sender,
            "recipient": transaction_details.recipient,
            "risk_flags": transaction_details.risk_flags or [],
            "metadata": transaction_details.metadata or {}
        }
