"""Repository classes for Couchbase database operations."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from decimal import Decimal
from database.connection import get_db, get_sync_scope
from database.schemas import (
    Transaction, TransactionDecision, HumanReview,
    DecisionType, TransactionStatus
)
from utils.config import config
# Decimal utilities not needed here - we handle conversion directly

logger = logging.getLogger(__name__)

class TransactionRepository:
    """Repository for transaction operations."""
    
    @staticmethod
    async def create_transaction(transaction: Transaction) -> str:
        """Create a new transaction in Couchbase."""
        try:
            # Ensure connection is available (for Temporal activities)
            from database.connection import connect_to_couchbase, get_db
            try:
                db = get_db()
            except RuntimeError as e:
                if "not connected" in str(e).lower():
                    await connect_to_couchbase()
                    db = get_db()
                else:
                    raise
            
            collection = db.collection(config.TRANSACTIONS_COLLECTION)
            
            # Convert to dict, handling Decimal and datetime
            transaction_dict = transaction.model_dump(mode='json')
            transaction_dict['amount'] = float(transaction.amount)
            
            # Ensure datetime fields are strings (model_dump(mode='json') should handle this, but double-check)
            from datetime import datetime
            for key, value in transaction_dict.items():
                if isinstance(value, datetime):
                    transaction_dict[key] = value.isoformat()
            
            # Insert document with timeout
            from couchbase.options import UpsertOptions
            from datetime import timedelta
            result = await collection.upsert(
                transaction.transaction_id, 
                transaction_dict,
                UpsertOptions(timeout=timedelta(seconds=10))
            )
            logger.info(f"Created transaction: {transaction.transaction_id}")
            return transaction.transaction_id
        except Exception as e:
            logger.error(f"Error creating transaction: {e}")
            raise
    
    @staticmethod
    async def get_transaction(transaction_id: str) -> Optional[Dict]:
        """Get a transaction by ID."""
        try:
            db = get_db()
            collection = db.collection(config.TRANSACTIONS_COLLECTION)
            result = await collection.get(transaction_id)
            return result.content_as[dict]
        except Exception as e:
            if "document not found" in str(e).lower():
                return None
            logger.error(f"Error getting transaction: {e}")
            raise
    
    @staticmethod
    async def update_status(transaction_id: str, status: str) -> None:
        """Update transaction status."""
        try:
            # Ensure connection is available (for Temporal activities)
            from database.connection import connect_to_couchbase, get_db
            try:
                db = get_db()
            except RuntimeError as e:
                if "not connected" in str(e).lower():
                    await connect_to_couchbase()
                    db = get_db()
                else:
                    raise
            
            collection = db.collection(config.TRANSACTIONS_COLLECTION)
            
            # Get existing transaction
            result = await collection.get(transaction_id)
            transaction = result.content_as[dict]
            
            # Update status
            transaction['status'] = status
            from datetime import datetime, timezone
            transaction['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            await collection.upsert(transaction_id, transaction)
            logger.info(f"Updated transaction {transaction_id} status to {status}")
        except Exception as e:
            logger.error(f"Error updating transaction status: {e}")
            raise
    
    @staticmethod
    def update_status_sync(transaction_id: str, status: str) -> None:
        """Update transaction status (synchronous, for Streamlit)."""
        try:
            scope = get_sync_scope()
            collection = scope.collection(config.TRANSACTIONS_COLLECTION)
            
            # Get existing transaction
            result = collection.get(transaction_id)
            transaction = result.content_as[dict]
            
            # Update status
            transaction['status'] = status
            from datetime import datetime, timezone
            transaction['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            collection.upsert(transaction_id, transaction)
            logger.info(f"Updated transaction {transaction_id} status to {status}")
        except Exception as e:
            logger.error(f"Error updating transaction status: {e}")
            raise

class DecisionRepository:
    """Repository for decision operations."""
    
    @staticmethod
    async def create_decision(decision: TransactionDecision) -> str:
        """Create a new decision in Couchbase."""
        try:
            # Ensure connection is available (for Temporal activities)
            from database.connection import connect_to_couchbase, get_db
            try:
                db = get_db()
            except RuntimeError as e:
                if "not connected" in str(e).lower():
                    await connect_to_couchbase()
                    db = get_db()
                else:
                    raise
            
            collection = db.collection(config.DECISIONS_COLLECTION)
            
            # Convert to dict, handling Decimal and datetime
            decision_dict = decision.model_dump(mode='json')
            decision_dict['confidence_score'] = float(decision.confidence_score)
            decision_dict['risk_score'] = float(decision.risk_score)
            
            # Ensure datetime fields are strings
            from datetime import datetime
            for key, value in decision_dict.items():
                if isinstance(value, datetime):
                    decision_dict[key] = value.isoformat()
            
            # Insert document
            await collection.upsert(decision.decision_id, decision_dict)
            logger.info(f"Created decision: {decision.decision_id}")
            return decision.decision_id
        except Exception as e:
            logger.error(f"Error creating decision: {e}")
            raise
    
    @staticmethod
    async def get_decision_by_transaction(transaction_id: str) -> Optional[Dict]:
        """Get decision by transaction ID."""
        try:
            db = get_db()
            collection = db.collection(config.DECISIONS_COLLECTION)
            
            # Try direct lookup by transaction_id as key first
            try:
                result = await collection.get(transaction_id)
                decision = result.content_as[dict]
                if decision.get('transaction_id') == transaction_id:
                    return decision
            except:
                pass
            
            # Fallback: Query for decision by transaction_id
            from couchbase.options import QueryOptions
            query = f"SELECT * FROM `{config.COUCHBASE_BUCKET}`.`{config.COUCHBASE_SCOPE}`.`{config.DECISIONS_COLLECTION}` WHERE transaction_id = $1 LIMIT 1"
            result = db.query(query, QueryOptions(positional_parameters=[transaction_id]))
            
            # QueryResult is not awaitable, iterate over it directly
            rows = []
            async for row in result:
                rows.append(row)
            if rows:
                # Extract the decision data from the query result
                row_data = rows[0]
                if config.DECISIONS_COLLECTION in row_data:
                    return row_data[config.DECISIONS_COLLECTION]
                return dict(row_data)
            return None
        except Exception as e:
            logger.error(f"Error getting decision: {e}")
            return None

class HumanReviewRepository:
    """Repository for human review operations."""
    
    @staticmethod
    async def create_review(review: HumanReview) -> str:
        """Create a new human review in Couchbase."""
        try:
            # Ensure connection is available (for Temporal activities)
            from database.connection import connect_to_couchbase, get_db
            import logging
            repo_logger = logging.getLogger(__name__)
            
            # Try to get connection, establish if needed
            try:
                db = get_db()
            except RuntimeError as e:
                if "not connected" in str(e).lower():
                    repo_logger.info("Couchbase connection not available, establishing...")
                    await connect_to_couchbase()
                    db = get_db()
                else:
                    raise
            
            if db is None:
                raise RuntimeError("Database connection is None after establishment")
            
            collection = db.collection(config.HUMAN_REVIEWS_COLLECTION)
            
            # Convert to dict, handling datetime
            review_dict = review.model_dump(mode='json')
            
            # Ensure datetime fields are strings
            from datetime import datetime
            for key, value in review_dict.items():
                if isinstance(value, datetime):
                    review_dict[key] = value.isoformat()
            
            # Insert document
            await collection.upsert(review.review_id, review_dict)
            logger.info(f"Created human review: {review.review_id}")
            return review.review_id
        except Exception as e:
            logger.error(f"Error creating human review: {e}")
            raise
    
    @staticmethod
    def complete_review_sync(review_id: str, decision: str, reviewer: str, notes: Optional[str] = None) -> None:
        """Complete a human review (synchronous, for Streamlit)."""
        try:
            scope = get_sync_scope()
            collection = scope.collection(config.HUMAN_REVIEWS_COLLECTION)
            
            # Get existing review
            result = collection.get(review_id)
            review = result.content_as[dict]
            
            # Update review
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            review['status'] = 'completed'
            review['completed_at'] = now
            review['human_decision'] = {
                'decision': decision,
                'reviewer': reviewer,
                'notes': notes,
                'decided_at': now
            }
            if notes:
                review['notes'] = notes
            
            collection.upsert(review_id, review)
            logger.info(f"Completed human review: {review_id}")
        except Exception as e:
            logger.error(f"Error completing human review: {e}")
            raise

