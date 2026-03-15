"""API request and response models."""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime

class TransactionRequest(BaseModel):
    """Request model for transaction submission."""
    transaction_type: str
    amount: float
    currency: str = "USD"
    sender: Dict[str, Any]
    recipient: Dict[str, Any]
    reference_number: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class TransactionResponse(BaseModel):
    """Response model for transaction submission."""
    transaction_id: str
    status: str
    message: str
    workflow_id: Optional[str] = None

class DecisionResponse(BaseModel):
    """Response model for transaction decision."""
    transaction_id: str
    decision: str  # "approve", "reject", "escalate", "hold"
    confidence: float
    risk_score: float
    reasoning: str
    processing_time_ms: int
    risk_factors: List[str] = Field(default_factory=list)
    similar_cases: Optional[List[Dict[str, Any]]] = None

class MetricsResponse(BaseModel):
    """Response model for system metrics."""
    total_transactions: int
    transactions_by_type: Dict[str, int]
    total_amount: float
    decisions: Dict[str, Any]
    avg_processing_time_ms: float
    risk_distribution: Dict[str, int]
    timestamp: datetime = Field(default_factory=datetime.now)

