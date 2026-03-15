"""Couchbase database schemas."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
from enum import Enum
from decimal import Decimal
import uuid

# Enums
class TransactionType(str, Enum):
    WIRE_TRANSFER = "wire_transfer"
    ACH = "ach"
    INTERNATIONAL = "international"

class TransactionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    COMPLETED = "completed"

class DecisionType(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    HOLD = "hold"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

class RuleStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TESTING = "testing"

class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    ACKNOWLEDGED = "acknowledged"

# Helper functions for default values
def generate_transaction_id() -> str:
    return f"TXN_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8].upper()}"

def generate_decision_id() -> str:
    return f"DEC_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8].upper()}"

def generate_event_id() -> str:
    return f"EVT_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8].upper()}"

def generate_metric_id() -> str:
    return f"MET_{uuid.uuid4().hex[:8].upper()}"

def generate_rule_id() -> str:
    return f"RULE_{uuid.uuid4().hex[:8].upper()}"

def generate_customer_id() -> str:
    return f"CUST_{uuid.uuid4().hex[:8].upper()}"

def generate_review_id() -> str:
    return f"REV_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8].upper()}"

def generate_notification_id() -> str:
    return f"NOTIF_{uuid.uuid4().hex[:8].upper()}"

def get_current_time() -> datetime:
    return datetime.now(timezone.utc)

# Customer Schema
class Customer(BaseModel):
    customer_id: str = Field(default_factory=generate_customer_id)
    created_at: datetime = Field(default_factory=get_current_time)
    updated_at: datetime = Field(default_factory=get_current_time)
    
    # Basic Information
    legal_name: str
    display_name: str
    customer_type: str  # "individual", "business", "government"
    country: str
    
    # Risk Profile
    risk_profile: Dict[str, Any] = Field(default_factory=lambda: {
        "risk_level": "medium",
        "kyc_status": "pending",
        "last_review_date": None
    })
    
    # Behavioral Profile
    behavior_profile: Dict[str, Any] = Field(default_factory=lambda: {
        "avg_transaction_amount": 0,
        "transaction_frequency": "unknown",
        "common_recipients": []
    })
    
    # Account Information
    accounts: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Status
    status: str = "active"

# Transaction Schema with Vector Support
class Transaction(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    transaction_id: str = Field(default_factory=generate_transaction_id)
    created_at: datetime = Field(default_factory=get_current_time)
    updated_at: datetime = Field(default_factory=get_current_time)
    
    # Core Transaction Data
    transaction_type: TransactionType
    amount: Union[Decimal, float] = Field(...)  # Couchbase stores as string or float
    currency: str = Field(default="USD")
    
    # Parties
    sender: Dict[str, Any]
    recipient: Dict[str, Any]
    
    # Transaction Details
    reference_number: Optional[str] = None
    description: Optional[str] = None
    
    # Status
    status: TransactionStatus = TransactionStatus.PENDING
    processing_stages: List[Dict[str, Any]] = Field(default_factory=list)
    
    # ML Features
    ml_features: Dict[str, Any] = Field(default_factory=dict)
    
    # Vector Embedding for similarity search
    embedding: Optional[List[float]] = None  # Keep as float for vector operations
    embedding_model: Optional[str] = None
    
    # Compliance
    regulatory: Dict[str, Any] = Field(default_factory=dict)
    
    # Risk Indicators
    risk_flags: List[str] = Field(default_factory=list)
    
    # Rules Applied
    rules_applied: List[str] = Field(default_factory=list)

# Rule Engine Schema
class Rule(BaseModel):
    rule_id: str = Field(default_factory=generate_rule_id)
    created_at: datetime = Field(default_factory=get_current_time)
    updated_at: datetime = Field(default_factory=get_current_time)
    
    # Rule Definition
    name: str
    description: str
    category: str  # "amount", "geography", "pattern", "velocity", "compliance"
    status: RuleStatus = RuleStatus.ACTIVE
    
    # Rule Logic
    conditions: Dict[str, Any]  # Couchbase query format
    action: str  # "flag", "reject", "escalate", "approve"
    priority: int = Field(default=0, ge=0, le=100)
    
    # Thresholds and Parameters
    parameters: Dict[str, Any] = Field(default_factory=dict)
    
    # Effectiveness Metrics
    metrics: Dict[str, Any] = Field(default_factory=lambda: {
        "triggered_count": 0,
        "true_positives": 0,
        "false_positives": 0
    })

# Human Review Schema
class HumanReview(BaseModel):
    review_id: str = Field(default_factory=generate_review_id)
    transaction_id: str
    decision_id: Optional[str] = None
    created_at: datetime = Field(default_factory=get_current_time)
    updated_at: datetime = Field(default_factory=get_current_time)
    
    # Review Assignment
    assigned_to: Optional[str] = None
    assigned_at: Optional[datetime] = None
    priority: str = "medium"  # "low", "medium", "high", "urgent"
    sla_deadline: Optional[datetime] = None
    
    # Review Status
    status: str = "pending"  # "pending", "in_progress", "completed", "escalated"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # AI Recommendation
    ai_recommendation: Dict[str, Any] = Field(default_factory=dict)
    
    # Human Decision
    human_decision: Optional[Dict[str, Any]] = None
    
    # Notes
    notes: Optional[str] = None

# Notification Schema
class Notification(BaseModel):
    notification_id: str = Field(default_factory=generate_notification_id)
    created_at: datetime = Field(default_factory=get_current_time)
    
    # Notification Details
    notification_type: str  # "decision", "alert", "escalation", "compliance"
    priority: str = "medium"
    status: NotificationStatus = NotificationStatus.PENDING
    
    # Recipients
    recipients: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Content
    subject: str
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Related Entities
    transaction_id: Optional[str] = None
    decision_id: Optional[str] = None
    
    # Delivery
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None

# Transaction Decision Schema
class TransactionDecision(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    decision_id: str = Field(default_factory=generate_decision_id)
    transaction_id: str
    created_at: datetime = Field(default_factory=get_current_time)
    
    # Decision Details
    decision: DecisionType
    confidence_score: Union[Decimal, float] = Field(...)  # Couchbase compatible
    risk_score: Union[Decimal, float] = Field(...)  # Couchbase compatible
    
    # AI Model Information
    model_version: str = "openai/gpt-oss-120b"
    
    # Processing Performance
    processing_time_ms: int
    
    # Reasoning
    reasoning: Dict[str, Any]
    risk_factors: List[str] = Field(default_factory=list)
    similar_cases: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Rules Triggered
    rules_triggered: List[str] = Field(default_factory=list)
    
    # Workflow
    workflow_id: Optional[str] = None
    temporal_run_id: Optional[str] = None

# Rest of schemas remain the same...
class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=generate_event_id)
    timestamp: datetime = Field(default_factory=get_current_time)
    event_type: str
    event_category: str
    severity: str = "info"
    
    # Related Entities
    transaction_id: Optional[str] = None
    customer_id: Optional[str] = None
    decision_id: Optional[str] = None
    
    # Event Data
    event_data: Dict[str, Any]
    
    # Context
    context: Dict[str, Any] = Field(default_factory=dict)

class SystemMetric(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    metric_id: str = Field(default_factory=generate_metric_id)
    timestamp: datetime = Field(default_factory=get_current_time)
    metric_type: str
    metric_name: str
    value: Union[Decimal, float]  # Couchbase compatible
    unit: str
    dimensions: Dict[str, Any] = Field(default_factory=dict)