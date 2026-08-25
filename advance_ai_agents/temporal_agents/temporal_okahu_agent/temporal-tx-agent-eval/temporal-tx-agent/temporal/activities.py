"""Temporal activities for transaction processing with heartbeats and error handling."""

import logging
from typing import Dict, List, Optional
from temporalio import activity
from temporalio.common import RetryPolicy
from temporal.shared import TransactionDetails, DecisionResult
from ai.llm_client import llm_client
from ai.embedding_client import embedding_client
from database.repositories import TransactionRepository, DecisionRepository, HumanReviewRepository
from database.schemas import TransactionDecision, DecisionType, HumanReview
from database.connection import connect_to_couchbase, get_db
from utils.config import config
from utils.decimal_utils import to_decimal
from decimal import Decimal

logger = logging.getLogger(__name__)

# Ensure Couchbase connection is available for activities
async def ensure_couchbase_connection():
    """Ensure Couchbase connection is established."""
    from database.connection import _db, connect_to_couchbase, get_db
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Check if connection exists and is valid
    try:
        db = get_db()
        if db is None:
            raise RuntimeError("Database connection is None")
        # Connection exists and is valid
        logger.debug("Couchbase connection already established")
        return
    except (RuntimeError, AttributeError) as e:
        # Connection not established or invalid, connect now
        logger.info(f"Couchbase connection not available ({e}), establishing connection...")
        try:
            await connect_to_couchbase()
            # Verify connection was established
            db = get_db()
            if db is None:
                raise RuntimeError("Failed to establish Couchbase connection")
            logger.info("Couchbase connection established successfully")
        except Exception as conn_error:
            logger.error(f"Failed to establish Couchbase connection: {conn_error}")
            from temporalio.exceptions import ApplicationError
            # Raise as ApplicationError to allow retries
            raise ApplicationError(
                f"Couchbase connection failed: {str(conn_error)}",
                type="ConnectionError",
                non_retryable=False
            ) from conn_error

@activity.defn
async def generate_embedding(transaction_data: Dict) -> List[float]:
    """Generate embedding for a transaction with activity heartbeat."""
    from temporalio.exceptions import ApplicationError
    
    activity.logger.info(f"Generating embedding for transaction {transaction_data.get('transaction_id')}")
    
    # Create text representation of transaction
    text = f"{transaction_data.get('transaction_type', '')} {transaction_data.get('amount', 0)} {transaction_data.get('currency', 'USD')} {transaction_data.get('sender', {}).get('name', '')} {transaction_data.get('recipient', {}).get('name', '')}"
    
    # Send heartbeat before API call
    activity.heartbeat("starting_embedding_generation")
    
    try:
        embedding = embedding_client.generate_embedding(text)
        
        if not embedding:
            # If API returns None/empty, raise error to trigger retry
            raise ApplicationError(
                "OpenAI API returned empty embedding",
                type="EmbeddingGenerationError",
                non_retryable=False
            )
        
        activity.heartbeat("embedding_generated")
        return embedding
    except ApplicationError:
        # Re-raise ApplicationError as-is
        raise
    except Exception as e:
        activity.logger.error(f"Error generating embedding: {e}")
        activity.heartbeat(f"error: {str(e)}")
        # Raise ApplicationError to let Temporal handle retries
        raise ApplicationError(
            f"Failed to generate embedding: {str(e)}",
            type="EmbeddingGenerationError",
            non_retryable=False
        ) from e

@activity.defn
async def analyze_transaction_with_ai(transaction_data: Dict, context: Optional[Dict] = None) -> DecisionResult:
    """Analyze transaction using AI with activity heartbeat."""
    from temporalio.exceptions import ApplicationError
    
    activity.logger.info(f"Analyzing transaction {transaction_data.get('transaction_id')} with AI")
    activity.heartbeat("starting_ai_analysis")
    
    try:
        # Use LLM client to analyze transaction
        analysis = llm_client.analyze_transaction(transaction_data, context)
        
        activity.heartbeat("ai_analysis_complete")
        
        # Calculate risk score based on multiple factors
        risk_score = _calculate_risk_score(transaction_data, analysis, context)
        
        return DecisionResult(
            decision=analysis["decision"],
            confidence=analysis["confidence"],
            risk_score=risk_score,
            reasoning={
                "primary_reasoning": analysis["reasoning"],
                "risk_factors": analysis["risk_factors"]
            },
            risk_factors=analysis["risk_factors"]
        )
    except ApplicationError:
        # Re-raise ApplicationError as-is
        raise
    except Exception as e:
        activity.logger.error(f"Error analyzing transaction: {e}")
        activity.heartbeat(f"error: {str(e)}")
        # Raise ApplicationError to let Temporal handle retries
        raise ApplicationError(
            f"Failed to analyze transaction with AI: {str(e)}",
            type="AIAnalysisError",
            non_retryable=False
        ) from e

@activity.defn
async def search_similar_transactions(transaction_data: Dict, embedding: List[float]) -> List[Dict]:
    """Search for similar transactions using vector search with heartbeat."""
    from temporalio.exceptions import ApplicationError
    
    activity.logger.info(f"Searching for similar transactions for {transaction_data.get('transaction_id')}")
    activity.heartbeat("starting_vector_search")
    
    try:
        # TODO: Implement actual Couchbase vector search
        # This would use Couchbase FTS with vector similarity
        # For now, return empty list as placeholder (this is intentional, not an error)
        
        activity.heartbeat("vector_search_complete")
        return []
    except ApplicationError:
        # Re-raise ApplicationError as-is
        raise
    except Exception as e:
        activity.logger.error(f"Error searching similar transactions: {e}")
        activity.heartbeat(f"error: {str(e)}")
        # Raise ApplicationError to let Temporal handle retries
        raise ApplicationError(
            f"Failed to search similar transactions: {str(e)}",
            type="VectorSearchError",
            non_retryable=False
        ) from e

@activity.defn
async def apply_business_rules(transaction_data: Dict) -> Dict:
    """Apply business rules and compliance checks."""
    try:
        activity.logger.info(f"Applying business rules for transaction {transaction_data.get('transaction_id')}")
        activity.heartbeat("checking_compliance")
        
        rules_result = {
            "passed": True,
            "violations": [],
            "flags": []
        }
        
        amount = float(transaction_data.get('amount', 0))
        transaction_type = transaction_data.get('transaction_type', '')
        recipient_country = transaction_data.get('recipient', {}).get('country', '')
        
        # Rule 1: High-value transaction requires review
        if amount > config.AUTO_APPROVAL_LIMIT:
            rules_result["flags"].append("high_value_transaction")
            if transaction_type == "wire_transfer" and amount > 50000:
                rules_result["violations"].append("wire_transfer_over_limit")
        
        # Rule 2: Sanctions check (simplified)
        sanctioned_countries = ["RU", "KP", "IR"]  # Example list
        if recipient_country in sanctioned_countries:
            rules_result["passed"] = False
            rules_result["violations"].append("sanctions_violation")
            raise ValueError("Compliance violation: Sanctioned country")
        
        # Rule 3: Structuring detection (multiple transactions just under threshold)
        if 4900 <= amount < 5000:
            rules_result["flags"].append("potential_structuring")
        
        activity.heartbeat("business_rules_complete")
        return rules_result
    except ValueError as e:
        # Non-retryable compliance violation
        activity.logger.error(f"Compliance violation: {e}")
        from temporalio.exceptions import ApplicationError
        # Raise as non-retryable ApplicationError
        raise ApplicationError(
            f"Compliance violation: {str(e)}",
            type="ComplianceViolation",
            non_retryable=True
        ) from e
    except Exception as e:
        activity.logger.error(f"Error applying business rules: {e}")
        activity.heartbeat(f"error: {str(e)}")
        from temporalio.exceptions import ApplicationError
        # Raise ApplicationError to let Temporal handle retries
        raise ApplicationError(
            f"Failed to apply business rules: {str(e)}",
            type="BusinessRulesError",
            non_retryable=False
        ) from e

@activity.defn
async def save_decision(transaction_id: str, decision_result: DecisionResult, processing_time_ms: int) -> str:
    """Save decision to database with retry logic."""
    try:
        # Ensure Couchbase connection
        await ensure_couchbase_connection()
        
        activity.logger.info(f"Saving decision for transaction {transaction_id}")
        activity.heartbeat("saving_decision")
        
        # Convert decision string to DecisionType enum
        decision_type_map = {
            "approve": DecisionType.APPROVE,
            "reject": DecisionType.REJECT,
            "escalate": DecisionType.ESCALATE
        }
        decision_type = decision_type_map.get(decision_result.decision, DecisionType.ESCALATE)
        
        # Ensure required fields are present
        reasoning = decision_result.reasoning if decision_result.reasoning else {}
        risk_factors = decision_result.risk_factors if decision_result.risk_factors else []
        
        # Create decision record
        decision = TransactionDecision(
            transaction_id=transaction_id,
            decision=decision_type,
            confidence_score=Decimal(str(decision_result.confidence)),
            risk_score=Decimal(str(decision_result.risk_score)),
            processing_time_ms=processing_time_ms,
            reasoning=reasoning,
            risk_factors=risk_factors
        )
        
        # Save to database
        decision_id = await DecisionRepository.create_decision(decision)
        activity.heartbeat("decision_saved")
        activity.logger.info(f"Saved decision {decision_id} for transaction {transaction_id}")
        return decision_id
    except Exception as e:
        activity.logger.error(f"Error saving decision: {e}", exc_info=True)
        activity.heartbeat(f"error: {str(e)}")
        # Re-raise with more context
        from temporalio.exceptions import ApplicationError
        raise ApplicationError(
            f"Failed to save decision: {str(e)}",
            type="DecisionSaveError",
            non_retryable=False
        ) from e

@activity.defn
async def update_transaction_status(transaction_id: str, status: str) -> None:
    """Update transaction status in database."""
    try:
        # Ensure Couchbase connection
        await ensure_couchbase_connection()
        
        activity.logger.info(f"Updating transaction {transaction_id} status to {status}")
        activity.heartbeat("updating_status")
        
        await TransactionRepository.update_status(transaction_id, status)
        
        activity.heartbeat("status_updated")
        activity.logger.info(f"Updated transaction {transaction_id} status to {status}")
    except Exception as e:
        activity.logger.error(f"Error updating transaction status: {e}")
        activity.heartbeat(f"error: {str(e)}")
        from temporalio.exceptions import ApplicationError
        # Raise ApplicationError to let Temporal handle retries
        raise ApplicationError(
            f"Failed to update transaction status: {str(e)}",
            type="StatusUpdateError",
            non_retryable=False
        ) from e

@activity.defn
async def create_human_review(transaction_id: str, decision_result: DecisionResult) -> str:
    """Create human review record for escalated transactions."""
    try:
        # Ensure Couchbase connection
        await ensure_couchbase_connection()
        
        activity.logger.info(f"Creating human review for transaction {transaction_id}")
        activity.heartbeat("creating_review")
        
        # Determine priority based on risk score
        priority = "medium"
        if decision_result.risk_score >= 80:
            priority = "urgent"
        elif decision_result.risk_score >= 60:
            priority = "high"
        
        # Create human review record
        review = HumanReview(
            transaction_id=transaction_id,
            priority=priority,
            ai_recommendation={
                "decision": decision_result.decision,
                "confidence": decision_result.confidence,
                "reasoning": decision_result.reasoning,
                "risk_factors": decision_result.risk_factors
            }
        )
        
        review_id = await HumanReviewRepository.create_review(review)
        activity.heartbeat("review_created")
        activity.logger.info(f"Created human review {review_id} for transaction {transaction_id}")
        return review_id
    except Exception as e:
        activity.logger.error(f"Error creating human review: {e}")
        activity.heartbeat(f"error: {str(e)}")
        from temporalio.exceptions import ApplicationError
        # Raise ApplicationError to let Temporal handle retries
        raise ApplicationError(
            f"Failed to create human review: {str(e)}",
            type="HumanReviewCreationError",
            non_retryable=False
        ) from e

def _calculate_risk_score(transaction_data: Dict, analysis: Dict, context: Optional[Dict]) -> float:
    """Calculate comprehensive risk score based on multiple factors."""
    base_risk = 50.0
    
    # Factor 1: Amount-based risk
    amount = float(transaction_data.get('amount', 0))
    if amount > 100000:
        base_risk += 20
    elif amount > 50000:
        base_risk += 10
    elif amount > 10000:
        base_risk += 5
    
    # Factor 2: Transaction type risk
    transaction_type = transaction_data.get('transaction_type', '')
    if transaction_type == 'international':
        base_risk += 15
    elif transaction_type == 'wire_transfer':
        base_risk += 10
    
    # Factor 3: Geographic risk
    recipient_country = transaction_data.get('recipient', {}).get('country', '')
    high_risk_countries = ['RU', 'CN', 'PK', 'NG']
    if recipient_country in high_risk_countries:
        base_risk += 20
    
    # Factor 4: AI confidence (inverse - lower confidence = higher risk)
    ai_confidence = analysis.get('confidence', 50)
    if ai_confidence < 60:
        base_risk += 15
    elif ai_confidence < 75:
        base_risk += 10
    
    # Factor 5: Similar transactions (fraud patterns)
    if context and context.get('similar_transactions'):
        similar_count = len(context['similar_transactions'])
        if similar_count > 5:
            base_risk += 25
        elif similar_count > 2:
            base_risk += 15
    
    # Normalize to 0-100 range
    risk_score = min(100.0, max(0.0, base_risk))
    
    return round(risk_score, 1)
