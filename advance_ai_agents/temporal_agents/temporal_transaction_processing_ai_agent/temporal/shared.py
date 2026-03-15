"""Shared types and constants for Temporal workflows."""

from dataclasses import dataclass
from typing import Dict, List, Optional

# Task queue name
TRANSACTION_PROCESSING_TASK_QUEUE = "transaction-processing"

@dataclass
class TransactionDetails:
    """Transaction details passed to workflow."""
    transaction_id: str
    transaction_type: str
    amount: str
    currency: str
    sender: Dict
    recipient: Dict
    reference_number: Optional[str] = None
    risk_flags: List[str] = None
    metadata: Dict = None
    
    def __post_init__(self):
        if self.risk_flags is None:
            self.risk_flags = []
        if self.metadata is None:
            self.metadata = {}

@dataclass
class DecisionResult:
    """Result of transaction decision."""
    decision: str  # "approve", "reject", "escalate"
    confidence: float
    risk_score: float
    reasoning: Dict
    risk_factors: List[str]

