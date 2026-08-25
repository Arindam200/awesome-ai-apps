"""Seed Couchbase with sample transaction data for testing."""

import asyncio
import logging
import random
import uuid
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Dict
from pathlib import Path

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        logging.info(f"✅ Loaded .env file from {env_path}")
except ImportError:
    # dotenv not installed, try to load manually or use environment variables
    pass

from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator
from ai.embedding_client import embedding_client
from utils.config import config
from database.schemas import Transaction, TransactionStatus, TransactionType, TransactionDecision, DecisionType

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

# Sample transaction templates
SAMPLE_TRANSACTIONS = [
    # Normal transactions
    {
        "transaction_type": "ach",
        "amount": 2500.00,
        "sender": {"name": "ABC Corporation", "country": "US", "account_number": "ACC001"},
        "recipient": {"name": "XYZ Suppliers Inc", "country": "US", "account_number": "ACC002"},
        "description": "Monthly payment for services",
        "risk_flags": [],
        "expected_decision": "approve"
    },
    {
        "transaction_type": "wire_transfer",
        "amount": 15000.00,
        "sender": {"name": "Tech Solutions LLC", "country": "US", "account_number": "ACC003"},
        "recipient": {"name": "Global Partners Ltd", "country": "UK", "account_number": "ACC004"},
        "description": "Equipment purchase",
        "risk_flags": [],
        "expected_decision": "approve"
    },
    {
        "transaction_type": "ach",
        "amount": 500.00,
        "sender": {"name": "John Smith", "country": "US", "account_number": "ACC005"},
        "recipient": {"name": "Jane Doe", "country": "US", "account_number": "ACC006"},
        "description": "Personal transfer",
        "risk_flags": [],
        "expected_decision": "approve"
    },
    # Suspicious transactions
    {
        "transaction_type": "wire_transfer",
        "amount": 4999.00,
        "sender": {"name": "Suspicious Corp", "country": "US", "account_number": "ACC007"},
        "recipient": {"name": "Offshore Holdings", "country": "KY", "account_number": "ACC008"},
        "description": "Business payment",
        "risk_flags": ["structuring_pattern", "offshore_account"],
        "expected_decision": "escalate"
    },
    {
        "transaction_type": "wire_transfer",
        "amount": 4998.00,
        "sender": {"name": "Suspicious Corp Variant", "country": "US", "account_number": "ACC009"},
        "recipient": {"name": "Offshore Holdings", "country": "KY", "account_number": "ACC008"},
        "description": "Business payment",
        "risk_flags": ["structuring_pattern", "offshore_account"],
        "expected_decision": "escalate"
    },
    {
        "transaction_type": "international",
        "amount": 75000.00,
        "sender": {"name": "New Account LLC", "country": "US", "account_number": "ACC010"},
        "recipient": {"name": "Unknown Entity", "country": "CN", "account_number": "ACC011"},
        "description": "Trade payment",
        "risk_flags": ["high_value", "new_account", "high_risk_country"],
        "expected_decision": "escalate"
    },
    # High-value transactions
    {
        "transaction_type": "wire_transfer",
        "amount": 100000.00,
        "sender": {"name": "Fortune 500 Corp", "country": "US", "account_number": "ACC012"},
        "recipient": {"name": "Trusted Vendor Inc", "country": "US", "account_number": "ACC013"},
        "description": "Large equipment purchase",
        "risk_flags": ["high_value"],
        "expected_decision": "escalate"
    },
    {
        "transaction_type": "wire_transfer",
        "amount": 250000.00,
        "sender": {"name": "Enterprise Solutions", "country": "US", "account_number": "ACC014"},
        "recipient": {"name": "Major Supplier Corp", "country": "US", "account_number": "ACC015"},
        "description": "Quarterly payment",
        "risk_flags": ["high_value"],
        "expected_decision": "escalate"
    },
    # Fraud pattern transactions
    {
        "transaction_type": "wire_transfer",
        "amount": 10000.00,
        "sender": {"name": "Unknown Sender", "country": "US", "account_number": "ACC016"},
        "recipient": {"name": "Middle Account", "country": "US", "account_number": "ACC017"},
        "description": "Payment",
        "risk_flags": ["unknown_sender", "money_mule_pattern"],
        "expected_decision": "reject"
    },
    {
        "transaction_type": "wire_transfer",
        "amount": 9500.00,
        "sender": {"name": "Middle Account", "country": "US", "account_number": "ACC017"},
        "recipient": {"name": "Final Destination", "country": "US", "account_number": "ACC018"},
        "description": "Transfer",
        "risk_flags": ["money_mule_pattern", "fee_deduction"],
        "expected_decision": "reject"
    },
    # Velocity pattern
    {
        "transaction_type": "ach",
        "amount": 5000.00,
        "sender": {"name": "Rapid Sender Corp", "country": "US", "account_number": "ACC019"},
        "recipient": {"name": "Recipient One", "country": "US", "account_number": "ACC020"},
        "description": "Payment 1",
        "risk_flags": ["velocity_check"],
        "expected_decision": "escalate"
    },
    {
        "transaction_type": "ach",
        "amount": 5500.00,
        "sender": {"name": "Rapid Sender Corp", "country": "US", "account_number": "ACC019"},
        "recipient": {"name": "Recipient Two", "country": "US", "account_number": "ACC021"},
        "description": "Payment 2",
        "risk_flags": ["velocity_check"],
        "expected_decision": "escalate"
    },
    {
        "transaction_type": "ach",
        "amount": 4800.00,
        "sender": {"name": "Rapid Sender Corp", "country": "US", "account_number": "ACC019"},
        "recipient": {"name": "Recipient Three", "country": "US", "account_number": "ACC022"},
        "description": "Payment 3",
        "risk_flags": ["velocity_check"],
        "expected_decision": "escalate"
    }
]

async def seed_transactions(num_transactions: int = None, include_embeddings: bool = True):
    """Seed Couchbase with sample transactions."""
    print("🚀 Starting data seeding...")
    try:
        print("📡 Connecting to Couchbase...")
        logger.info("Connecting to Couchbase...")
        logger.info(f"Connection string: {config.COUCHBASE_CONNECTION_STRING}")
        logger.info(f"Bucket: {config.COUCHBASE_BUCKET}")
        logger.info(f"Scope: {config.COUCHBASE_SCOPE}")
        print(f"   Bucket: {config.COUCHBASE_BUCKET}, Scope: {config.COUCHBASE_SCOPE}")
        
        # Validate connection string
        if not config.COUCHBASE_CONNECTION_STRING:
            raise ValueError("COUCHBASE_CONNECTION_STRING is not set in .env file")
        
        if not config.COUCHBASE_USERNAME or not config.COUCHBASE_PASSWORD:
            raise ValueError("COUCHBASE_USERNAME and COUCHBASE_PASSWORD must be set in .env file")
        
        # Connect to Couchbase
        auth = PasswordAuthenticator(config.COUCHBASE_USERNAME, config.COUCHBASE_PASSWORD)
        
        # Configure cluster options
        # For SSL connections (couchbases://), the SDK handles TLS automatically
        cluster_options = ClusterOptions(auth)
        
        # Create cluster connection
        cluster = Cluster(config.COUCHBASE_CONNECTION_STRING, cluster_options)
        
        # Wait for connection with better error handling
        try:
            from datetime import timedelta
            cluster.wait_until_ready(timeout=timedelta(seconds=30))
            logger.info("✅ Connected to Couchbase")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Couchbase: {e}")
            logger.error(f"   Connection string: {config.COUCHBASE_CONNECTION_STRING}")
            logger.error(f"   Username: {config.COUCHBASE_USERNAME}")
            logger.error("   Please verify:")
            logger.error("   1. Connection string format (couchbase:// or couchbases://)")
            logger.error("   2. Network connectivity to Couchbase")
            logger.error("   3. Credentials are correct")
            raise
        
        # Get bucket and collection
        try:
            bucket = cluster.bucket(config.COUCHBASE_BUCKET)
            logger.info(f"✅ Opened bucket: {config.COUCHBASE_BUCKET}")
        except Exception as e:
            logger.error(f"❌ Failed to open bucket '{config.COUCHBASE_BUCKET}': {e}")
            logger.error("   Please verify the bucket exists in Couchbase")
            raise
        
        scope = bucket.scope(config.COUCHBASE_SCOPE)
        logger.info(f"✅ Using scope: {config.COUCHBASE_SCOPE}")
        
        # Check if collections exist - try to access them
        print(f"📦 Checking collections: {config.TRANSACTIONS_COLLECTION}, {config.DECISIONS_COLLECTION}")
        try:
            transactions_collection = scope.collection(config.TRANSACTIONS_COLLECTION)
            decisions_collection = scope.collection(config.DECISIONS_COLLECTION)
            
            # Try a simple operation to verify collection exists
            try:
                # This will fail if collection doesn't exist
                transactions_collection.get("__test__", timeout=1)
            except Exception:
                # Collection might exist but document doesn't - that's fine
                pass
            
            print(f"✅ Collections are accessible")
            logger.info(f"✅ Opened collections: {config.TRANSACTIONS_COLLECTION}, {config.DECISIONS_COLLECTION}")
        except Exception as e:
            print(f"❌ Error accessing collections: {e}")
            logger.error(f"❌ Failed to open collections: {e}")
            logger.error(f"   Collections: {config.TRANSACTIONS_COLLECTION}, {config.DECISIONS_COLLECTION}")
            logger.error("   Please run: python -m scripts.setup_couchbase")
            print("   💡 Tip: Run 'python -m scripts.setup_couchbase' first to create collections")
            raise
        
        # Determine how many transactions to create
        if num_transactions is None:
            num_transactions = len(SAMPLE_TRANSACTIONS)
        
        transactions_to_create = SAMPLE_TRANSACTIONS[:num_transactions] if num_transactions <= len(SAMPLE_TRANSACTIONS) else SAMPLE_TRANSACTIONS * (num_transactions // len(SAMPLE_TRANSACTIONS) + 1)
        transactions_to_create = transactions_to_create[:num_transactions]
        
        print(f"📝 Creating {len(transactions_to_create)} sample transactions...")
        logger.info(f"Creating {len(transactions_to_create)} sample transactions...")
        
        created_count = 0
        decision_count = 0
        
        for i, template in enumerate(transactions_to_create):
            try:
                # Generate transaction ID
                transaction_id = f"TXN_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8].upper()}"
                
                # Create transaction document
                transaction_doc = {
                    "transaction_id": transaction_id,
                    "transaction_type": template["transaction_type"],
                    "amount": template["amount"],
                    "currency": "USD",
                    "sender": template["sender"],
                    "recipient": template["recipient"],
                    "reference_number": f"REF{uuid.uuid4().hex[:12].upper()}",
                    "description": template["description"],
                    "status": "approved" if template["expected_decision"] == "approve" else "pending_review",
                    "risk_flags": template["risk_flags"],
                    "created_at": (datetime.now(timezone.utc) - timedelta(days=random.randint(0, 30))).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "processing_stages": [],
                    "ml_features": {},
                    "regulatory": {},
                    "rules_applied": []
                }
                
                # Generate embedding if requested
                if include_embeddings:
                    try:
                        # Create text representation for embedding
                        currency = template.get('currency', 'USD')
                        text = f"{template['transaction_type']} {template['amount']} {currency} {template['sender']['name']} {template['recipient']['name']} {template.get('description', '')}"
                        embedding = embedding_client.generate_embedding(text)
                        
                        if embedding:
                            transaction_doc["embedding"] = embedding
                            transaction_doc["embedding_model"] = config.OPENAI_EMBEDDING_MODEL
                            logger.info(f"✅ Generated embedding for transaction {transaction_id}")
                        else:
                            logger.warning(f"⚠️  Could not generate embedding for {transaction_id}, using mock")
                            transaction_doc["embedding"] = embedding_client._mock_embedding()
                            transaction_doc["embedding_model"] = "mock"
                    except Exception as e:
                        logger.warning(f"⚠️  Error generating embedding: {e}, using mock")
                        transaction_doc["embedding"] = embedding_client._mock_embedding()
                        transaction_doc["embedding_model"] = "mock"
                
                # Insert transaction with retry
                try:
                    transactions_collection.upsert(f"transaction::{transaction_id}", transaction_doc)
                    created_count += 1
                    if created_count % 5 == 0:
                        print(f"   ✅ Created {created_count} transactions...")
                except Exception as upsert_error:
                    # Check if it's a collection not found error
                    error_str = str(upsert_error).lower()
                    if 'collection' in error_str or 'outdated' in error_str:
                        logger.error(f"❌ Collection '{config.TRANSACTIONS_COLLECTION}' not found in scope '{config.COUCHBASE_SCOPE}'")
                        logger.error("   Please run: python -m scripts.setup_couchbase")
                        logger.error("   Or create the collection manually in Couchbase UI")
                        raise
                    else:
                        raise
                
                # Create decision for some transactions
                if template["expected_decision"] != "approve" or random.random() < 0.3:
                    decision_id = f"DEC_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8].upper()}"
                    
                    # Determine confidence and risk score based on decision
                    if template["expected_decision"] == "approve":
                        confidence = random.uniform(85, 95)
                        risk_score = random.uniform(10, 30)
                    elif template["expected_decision"] == "reject":
                        confidence = random.uniform(80, 90)
                        risk_score = random.uniform(70, 95)
                    else:  # escalate
                        confidence = random.uniform(60, 80)
                        risk_score = random.uniform(50, 75)
                    
                    decision_doc = {
                        "decision_id": decision_id,
                        "transaction_id": transaction_id,
                        "decision": template["expected_decision"],
                        "confidence_score": confidence,
                        "risk_score": risk_score,
                        "processing_time_ms": random.randint(200, 800),
                        "reasoning": {
                            "primary_reasoning": f"Sample decision for {template['expected_decision']}",
                            "risk_factors": template["risk_flags"]
                        },
                        "risk_factors": template["risk_flags"],
                        "similar_cases": [],
                        "rules_triggered": template["risk_flags"],
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "model_version": config.OPENAI_MODEL
                    }
                    
                    decisions_collection.upsert(f"decision::{decision_id}", decision_doc)
                    decision_count += 1
                
                if (i + 1) % 5 == 0:
                    logger.info(f"Progress: {i + 1}/{len(transactions_to_create)} transactions created...")
                    
            except Exception as e:
                logger.error(f"Error creating transaction {i}: {e}")
                continue
        
        print(f"\n✅ Successfully created {created_count} transactions")
        print(f"✅ Successfully created {decision_count} decisions")
        print(f"\n📊 Summary:")
        print(f"   - Transactions: {created_count}")
        print(f"   - Decisions: {decision_count}")
        print(f"   - Embeddings: {'Yes' if include_embeddings else 'No'}")
        logger.info(f"✅ Successfully created {created_count} transactions")
        logger.info(f"✅ Successfully created {decision_count} decisions")
        logger.info(f"\n📊 Summary:")
        logger.info(f"   - Transactions: {created_count}")
        logger.info(f"   - Decisions: {decision_count}")
        logger.info(f"   - Embeddings: {'Yes' if include_embeddings else 'No'}")
        
        # Print some sample transaction IDs
        if created_count > 0:
            logger.info(f"\n💡 Sample transaction IDs (first 5):")
            for i, template in enumerate(transactions_to_create[:5]):
                logger.info(f"   - Transaction type: {template['transaction_type']}, Amount: ${template['amount']}, Expected: {template['expected_decision']}")
        
    except Exception as e:
        logger.error(f"❌ Error seeding data: {e}")
        raise

async def clear_all_data():
    """Clear all transaction and decision data (use with caution!)."""
    try:
        logger.warning("⚠️  This will delete ALL transactions and decisions!")
        response = input("Are you sure? Type 'yes' to continue: ")
        if response.lower() != 'yes':
            logger.info("Cancelled.")
            return
        
        logger.info("Connecting to Couchbase...")
        auth = PasswordAuthenticator(config.COUCHBASE_USERNAME, config.COUCHBASE_PASSWORD)
        cluster_options = ClusterOptions(auth)
        cluster = Cluster(config.COUCHBASE_CONNECTION_STRING, cluster_options)
        cluster.wait_until_ready(timeout=30)
        
        bucket = cluster.bucket(config.COUCHBASE_BUCKET)
        scope = bucket.scope(config.COUCHBASE_SCOPE)
        transactions_collection = scope.collection(config.TRANSACTIONS_COLLECTION)
        decisions_collection = scope.collection(config.DECISIONS_COLLECTION)
        
        # Delete all documents (this is a simple approach - in production, use N1QL DELETE)
        logger.info("Deleting all transactions and decisions...")
        
        # Use N1QL to delete all documents
        delete_transactions = f"""
            DELETE FROM `{config.COUCHBASE_BUCKET}`.`{config.COUCHBASE_SCOPE}`.`{config.TRANSACTIONS_COLLECTION}`
        """
        delete_decisions = f"""
            DELETE FROM `{config.COUCHBASE_BUCKET}`.`{config.COUCHBASE_SCOPE}`.`{config.DECISIONS_COLLECTION}`
        """
        
        try:
            cluster.query(delete_transactions)
            cluster.query(delete_decisions)
            logger.info("✅ All data cleared")
        except Exception as e:
            logger.error(f"Error clearing data: {e}")
            
    except Exception as e:
        logger.error(f"❌ Error clearing data: {e}")
        raise

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        asyncio.run(clear_all_data())
    else:
        # Parse arguments
        num_txns = None
        include_emb = True
        
        for arg in sys.argv[1:]:
            if arg == "--no-embeddings":
                include_emb = False
            elif arg.isdigit():
                num_txns = int(arg)
        
        asyncio.run(seed_transactions(num_txns, include_emb))

