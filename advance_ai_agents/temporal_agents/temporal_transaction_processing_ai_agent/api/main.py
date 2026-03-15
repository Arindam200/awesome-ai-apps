"""FastAPI server for transaction processing API."""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uuid
from datetime import datetime, timedelta, timezone
import logging
from typing import Dict, List

from temporalio.client import Client
from api.models import (
    TransactionRequest,
    TransactionResponse,
    DecisionResponse,
    MetricsResponse
)
from database.connection import connect_to_couchbase, close_couchbase_connection, db
from database.schemas import Transaction, TransactionStatus
from database.repositories import TransactionRepository, DecisionRepository
from utils.decimal_utils import to_decimal, decimal_to_float
from temporal.workflows import TransactionProcessingWorkflow
from temporal.shared import TransactionDetails, TRANSACTION_PROCESSING_TASK_QUEUE
from utils.config import config
from ai.embedding_client import embedding_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Transaction AI Processing API",
    description="AI-powered financial transaction processing system",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temporal client
temporal_client = None

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup."""
    await connect_to_couchbase()
    global temporal_client
    temporal_client = await Client.connect(config.TEMPORAL_HOST, namespace=config.TEMPORAL_NAMESPACE)
    logger.info("API server started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    await close_couchbase_connection()
    logger.info("API server stopped")

@app.post("/api/transaction", response_model=TransactionResponse)
async def process_transaction(transaction_req: TransactionRequest):
    """Submit a new transaction for processing."""
    try:
        # Create transaction record with Decimal for amount
        transaction = Transaction(
            transaction_type=transaction_req.transaction_type,
            amount=to_decimal(transaction_req.amount),
            currency=transaction_req.currency,
            sender=transaction_req.sender,
            recipient=transaction_req.recipient,
            reference_number=transaction_req.reference_number or f"REF-{uuid.uuid4().hex[:8].upper()}",
            description=transaction_req.description,
            status=TransactionStatus.PENDING
        )
        
        # Store in Couchbase
        transaction_id = await TransactionRepository.create_transaction(transaction)
        
        # Prepare for Temporal workflow - ensure transaction_type is properly serialized
        transaction_type_value = transaction.transaction_type.value if hasattr(transaction.transaction_type, 'value') else str(transaction.transaction_type)
        
        transaction_details = TransactionDetails(
            transaction_id=transaction_id,
            transaction_type=transaction_type_value,  # Pass as string
            amount=str(transaction.amount),  # Convert Decimal to string for Temporal
            currency=transaction.currency,
            sender=transaction.sender,
            recipient=transaction.recipient,
            reference_number=transaction.reference_number,
            risk_flags=[],
            metadata=transaction_req.metadata or {}
        )
        
        # Start Temporal workflow
        workflow_id = f"txn-processing-{transaction_id}"
        handle = await temporal_client.start_workflow(
            TransactionProcessingWorkflow.run,
            transaction_details,
            id=workflow_id,
            task_queue=TRANSACTION_PROCESSING_TASK_QUEUE
        )
        
        logger.info(f"Started workflow {workflow_id} for transaction {transaction_id}")
        
        return TransactionResponse(
            transaction_id=transaction_id,
            status=TransactionStatus.PROCESSING,
            message="Transaction submitted for AI analysis",
            workflow_id=workflow_id
        )
        
    except Exception as e:
        logger.error(f"Error processing transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/transaction/{transaction_id}", response_model=DecisionResponse)
async def get_transaction_decision(transaction_id: str):
    """Get the AI decision for a transaction."""
    try:
        # Get decision from Couchbase
        decision = await DecisionRepository.get_decision_by_transaction(transaction_id)

        if not decision:
            # Check if transaction exists and get its status
            transaction = await TransactionRepository.get_transaction(transaction_id)
            if not transaction:
                raise HTTPException(status_code=404, detail="Transaction not found")

            # Check transaction status for failed workflows
            status = transaction.get('status', 'pending')
            if status == 'rejected':
                # Return a rejection decision for failed workflows
                return DecisionResponse(
                    transaction_id=transaction_id,
                    decision='reject',
                    confidence=100,
                    risk_score=100,
                    reasoning='Transaction rejected due to compliance violation or system error',
                    processing_time_ms=0,
                    risk_factors=['compliance_violation']
                )
            elif status == 'failed':
                # Return a rejection decision for failed transactions
                return DecisionResponse(
                    transaction_id=transaction_id,
                    decision='reject',
                    confidence=100,
                    risk_score=100,
                    reasoning='Transaction failed during processing',
                    processing_time_ms=0,
                    risk_factors=['processing_failure']
                )
            else:
                raise HTTPException(status_code=202, detail="Decision pending")

        return DecisionResponse(
            transaction_id=transaction_id,
            decision=decision['decision'],
            confidence=decision['confidence_score'],
            risk_score=decision.get('risk_score', 50),
            reasoning=decision['reasoning'].get('primary_reasoning', ''),
            processing_time_ms=decision.get('processing_time_ms', 0),
            risk_factors=decision['reasoning'].get('risk_factors', [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting decision: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Get system metrics and statistics."""
    try:
        # Calculate metrics
        total_transactions = await db.database[config.TRANSACTIONS_COLLECTION].count_documents({})
        
        # Get transactions by type
        pipeline = [
            {"$group": {
                "_id": "$transaction_type",
                "count": {"$sum": 1},
                "total_amount": {"$sum": "$amount"}
            }}
        ]
        type_stats = await db.database[config.TRANSACTIONS_COLLECTION].aggregate(pipeline).to_list(None)
        transactions_by_type = {stat['_id']: stat['count'] for stat in type_stats}
        # Handle Decimal128 values in sum
        from utils.decimal_utils import from_decimal128
        total_amount = sum(from_decimal128(stat.get('total_amount', 0)) for stat in type_stats)
        
        # Get decision breakdown
        decision_pipeline = [
            {"$group": {
                "_id": "$decision",
                "count": {"$sum": 1},
                "avg_confidence": {"$avg": "$confidence_score"},
                "avg_processing_time": {"$avg": "$processing_time_ms"}
            }}
        ]
        decision_stats = await db.database[config.DECISIONS_COLLECTION].aggregate(decision_pipeline).to_list(None)
        
        decisions_breakdown = {stat['_id']: stat['count'] for stat in decision_stats if stat['_id']}
        
        # Calculate weighted averages safely
        total_decisions = sum(stat['count'] for stat in decision_stats)
        if total_decisions > 0 and decision_stats:
            avg_confidence = sum(
                (stat.get('avg_confidence', 0) or 0) * stat['count'] 
                for stat in decision_stats
            ) / total_decisions
            avg_processing_time = sum(
                (stat.get('avg_processing_time', 0) or 0) * stat['count'] 
                for stat in decision_stats
            ) / total_decisions
        else:
            avg_confidence = 0
            avg_processing_time = 0
        
        return MetricsResponse(
            total_transactions=total_transactions,
            transactions_by_type=transactions_by_type,
            decisions_breakdown=decisions_breakdown,
            average_processing_time_ms=avg_processing_time,
            average_confidence=avg_confidence,
            total_amount_processed=total_amount
        )
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    embedding_health = embedding_client.health_check()

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc),
        "couchbase": "connected" if db.client else "disconnected",
        "temporal": "connected" if temporal_client else "disconnected",
        "embedding": {
            "primary_model": embedding_health["primary_model"],
            "openai_available": embedding_health["openai_available"],
            "available_models": embedding_health["available_models"]
        }
    }
