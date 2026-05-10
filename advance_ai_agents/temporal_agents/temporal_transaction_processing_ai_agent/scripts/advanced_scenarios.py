"""Advanced test scenarios showcasing Couchbase Capella and Temporal features."""

import asyncio
import httpx
from typing import Dict, List
from datetime import datetime, timezone
import uuid
import random
from utils.config import config

class AdvancedScenarios:
    """Advanced transaction scenarios demonstrating system capabilities."""

    def __init__(self, api_url: str = None):
        self.api_url = api_url or config.API_BASE_URL
        
    def generate_scenarios(self) -> List[Dict]:
        """Generate advanced test scenarios."""
        return [
            # Scenario 1: Pattern Recognition - Fraud Ring Detection
            {
                "name": "Fraud Ring Detection - Structuring Pattern",
                "description": "Detects potential money structuring using hybrid search (vector, traditional, graph). Multiple wire transfers just under $5000 from related entities trigger compliance alerts for human review",
                "transactions": [
                    self._create_transaction(
                        amount=4999,
                        sender_name="John Smith LLC",
                        recipient_name="Offshore Holdings Inc",
                        transaction_type="wire_transfer",
                        metadata={"ip_address": "192.168.1.100", "device_id": "device_001"}
                    ),
                    self._create_transaction(
                        amount=4998,
                        sender_name="J Smith Enterprises",
                        recipient_name="Offshore Holdings Inc",
                        transaction_type="wire_transfer",
                        metadata={"ip_address": "192.168.1.101", "device_id": "device_001"}
                    ),
                    self._create_transaction(
                        amount=4997,
                        sender_name="Smith John Co",
                        recipient_name="Offshore Holdings Inc",
                        transaction_type="wire_transfer",
                        metadata={"ip_address": "192.168.1.102", "device_id": "device_001"}
                    )
                ],
                "expected_outcome": "ESCALATE - Suspicious pattern under $5000 threshold requires human review to distinguish intentional structuring from legitimate transactions"
            },
            
            # Scenario 2: Time-Based Anomaly Detection
            {
                "name": "Velocity Check - Rapid Fire Transactions",
                "description": "Tests velocity-based fraud detection with multiple high-value ACH transfers in rapid succession. System detects unusual transaction frequency patterns",
                "transactions": [
                    self._create_transaction(
                        amount=25000,
                        sender_name="ABC Corp",
                        recipient_name="Supplier One",
                        transaction_type="ach",
                        metadata={"batch_id": "batch_001", "timestamp": datetime.now(timezone.utc).isoformat()}
                    ),
                    self._create_transaction(
                        amount=30000,
                        sender_name="ABC Corp",
                        recipient_name="Supplier Two",
                        transaction_type="ach",
                        metadata={"batch_id": "batch_001", "timestamp": datetime.now(timezone.utc).isoformat()}
                    ),
                    self._create_transaction(
                        amount=35000,
                        sender_name="ABC Corp",
                        recipient_name="Supplier Three",
                        transaction_type="ach",
                        metadata={"batch_id": "batch_001", "timestamp": datetime.now(timezone.utc).isoformat()}
                    )
                ],
                "expected_outcome": "ESCALATE - High velocity pattern exceeds thresholds but requires human assessment to confirm fraud intent"
            },
            
            # Scenario 3: Cross-Border High-Risk
            {
                "name": "High-Risk Geography - Sanctions Violation",
                "description": "Tests compliance controls with international wire transfer to a sanctioned country. Demonstrates automatic rejection for sanctions violations",
                "transactions": [
                    self._create_transaction(
                        amount=150000,
                        sender_name="Global Trade Inc",
                        recipient_name="International Partners Ltd",
                        recipient_country="RU",  # High risk
                        transaction_type="international",
                        metadata={"purpose": "equipment_purchase", "swift_code": "TEST123"}
                    )
                ],
                "expected_outcome": "REJECT - Automatic rejection for sanctions violation. Transactions to a sanctioned country trigger immediate compliance block"
            },
            
            # Scenario 4: Money Mule Detection
            {
                "name": "Money Mule Pattern Detection",
                "description": "Detects money mule patterns by analyzing receive-and-forward transactions with fee deductions. Classic money laundering behavior triggers alerts",
                "transactions": [
                    self._create_transaction(
                        amount=10000,
                        sender_name="Unknown Sender 1",
                        recipient_name="Middle Account",
                        transaction_type="wire_transfer",
                        metadata={"inbound": True}
                    ),
                    self._create_transaction(
                        amount=9500,  # Minus fee
                        sender_name="Middle Account",
                        recipient_name="Final Destination",
                        transaction_type="wire_transfer",
                        metadata={"outbound": True}
                    )
                ],
                "expected_outcome": "ESCALATE - Money mule pattern requires human review. Receive-and-forward with fee deduction is suspicious but needs investigation to confirm intent"
            },
            
            # Scenario 5: Positive Test - Low Risk Transaction
            {
                "name": "Low-Risk Domestic ACH",
                "description": "Tests automatic approval for low-risk domestic ACH between verified customers with good KYC status and established relationships",
                "transactions": [
                    self._create_transaction(
                        amount=2500,  # Low amount to avoid triggering rules
                        sender_name="Verified Business LLC",
                        recipient_name="Regular Supplier Inc",
                        transaction_type="ach",  # ACH to avoid wire transfer rules
                        metadata={
                            "customer_tier": "standard",
                            "kyc_status": "approved",
                            "relationship_years": 3,
                            "unusual_time": False
                        }
                    )
                ],
                "expected_outcome": "APPROVE - Low-risk domestic ACH automatically approved with high confidence based on verified customers and clean history"
            },
            
            # Scenario 5b: Negative Test - High Amount Wire Transfer
            {
                "name": "High Amount Wire Transfer",
                "description": "Tests mandatory review rule for wire transfers over $50,000. Business rules override AI confidence for high-value transactions",
                "transactions": [
                    self._create_transaction(
                        amount=75000,  # Above $50K threshold
                        sender_name="Fortune 500 Corp",
                        recipient_name="Trusted Vendor Inc",
                        transaction_type="wire_transfer",  # Will trigger wire transfer rule
                        metadata={
                            "customer_tier": "platinum",
                            "kyc_status": "approved",
                            "relationship_years": 10
                        }
                    )
                ],
                "expected_outcome": "ESCALATE - Wire transfer over $50K requires manual approval per business rules, regardless of AI confidence"
            },
            
            # Scenario 6: Complex Fraud Pattern with ML Detection
            {
                "name": "Advanced Fraud - Synthetic Identity",
                "description": "AI detects synthetic identity fraud: new account, VOIP phone, temp email, mail drop address, attempting large crypto transfer",
                "transactions": [
                    self._create_transaction(
                        amount=75000,
                        sender_name="NewCo Enterprises 2024",
                        recipient_name="Crypto Exchange XYZ",
                        transaction_type="wire_transfer",
                        metadata={
                            "account_age_days": 2,
                            "phone_carrier": "VOIP",
                            "email_domain": "tempmail.com",
                            "address_type": "mail_drop"
                        }
                    )
                ],
                "expected_outcome": "REJECT - Multiple synthetic identity red flags trigger automatic rejection. New account with suspicious attributes blocked"
            },
            
            # Scenario 7: Workflow Resilience Demo
            {
                "name": "Temporal Workflow Resilience",
                "description": "Demonstrates Temporal's durable execution guarantees. Even if the system experiences interruptions, the workflow state is preserved and processing completes successfully",
                "transactions": [
                    self._create_transaction(
                        amount=15000,
                        sender_name="Reliable Processing Corp",
                        recipient_name="Trusted Vendor",
                        transaction_type="ach",
                        metadata={"demonstrate_durability": True, "workflow_test": "resilience"}
                    )
                ],
                "expected_outcome": "APPROVE - Low-risk transaction processed successfully. Temporal's durable execution ensures completion even if workers restart"
            },
            
            # Scenario 8: Hybrid Search Pattern Matching
            {
                "name": "Similar Historical Pattern Match",
                "description": "Demonstrates hybrid search matching known fraud patterns using vector embeddings, traditional indexes, and behavioral correlation",
                "transactions": [
                    self._create_transaction(
                        amount=49999,  # Just under 50k limit
                        sender_name="Suspicious Corp Variant",
                        recipient_name="Known Bad Actor LLC",
                        transaction_type="wire_transfer",
                        metadata={
                            "similarity_test": True,
                            "match_previous_fraud": True
                        }
                    )
                ],
                "expected_outcome": "REJECT - High similarity to known fraud patterns detected by hybrid search triggers automatic rejection"
            },
            
            # Scenario 9: Live Demo Test - Full Integration Test
            {
                "name": "Live Demo Test - Full Workflow Integration",
                "description": "Complete end-to-end workflow test: Creates transaction, starts Temporal workflow, monitors progress, sends human review signal, and verifies results. Demonstrates all Temporal features including state management, signals, and durability.",
                "transactions": [
                    self._create_transaction(
                        amount=1000.00,
                        sender_name="Test Sender",
                        recipient_name="Test Recipient",
                        transaction_type="wire_transfer",
                        metadata={
                            "test": True,
                            "integration_test": True,
                            "live_demo": True
                        }
                    )
                ],
                "expected_outcome": "COMPLETE - Full workflow execution with all stages: embedding generation, similarity search, business rules, AI analysis, human review escalation, signal handling, decision saving, and status update. Demonstrates Temporal's durability and state management.",
                "is_integration_test": True  # Special flag for integration test
            }
        ]
    
    def _create_transaction(
        self,
        amount: float,
        sender_name: str,
        recipient_name: str,
        transaction_type: str = "wire_transfer",
        recipient_country: str = "US",
        metadata: Dict = None
    ) -> Dict:
        """Create a transaction object."""
        return {
            "transaction_id": f"TXN_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8].upper()}",
            "amount": amount,
            "currency": "USD",
            "transaction_type": transaction_type,
            "sender": {
                "name": sender_name,
                "account_number": f"ACC{random.randint(100000, 999999)}",
                "routing_number": "121000248",
                "country": "US"
            },
            "recipient": {
                "name": recipient_name,
                "account_number": f"ACC{random.randint(100000, 999999)}",
                "routing_number": "121000248",
                "country": recipient_country
            },
            "reference_number": f"REF{uuid.uuid4().hex[:12].upper()}",
            "metadata": metadata or {}
        }
    
    async def run_scenario(self, scenario: Dict) -> Dict:
        """Execute a single scenario."""
        # Check if this is the integration test scenario
        if scenario.get("is_integration_test"):
            return await self._run_integration_test(scenario)
        
        results = {
            "scenario_name": scenario["name"],
            "description": scenario["description"],
            "expected": scenario["expected_outcome"],
            "transactions": [],
            "start_time": datetime.now(timezone.utc).isoformat(),
            "workflow_ids": []
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for transaction in scenario["transactions"]:
                try:
                    # Submit transaction
                    response = await client.post(
                        f"{self.api_url}/transaction",
                        json=transaction
                    )
                    
                    if response.status_code in [200, 201, 202]:
                        result = response.json()
                        results["transactions"].append({
                            "transaction_id": transaction["transaction_id"],
                            "status": "submitted",
                            "workflow_id": result.get("workflow_id"),
                            "amount": transaction["amount"]
                        })
                        results["workflow_ids"].append(result.get("workflow_id"))
                    else:
                        results["transactions"].append({
                            "transaction_id": transaction["transaction_id"],
                            "status": "failed",
                            "error": response.text
                        })
                        
                except Exception as e:
                    results["transactions"].append({
                        "transaction_id": transaction["transaction_id"],
                        "status": "error",
                        "error": str(e)
                    })
                
                # Small delay between transactions in a scenario
                await asyncio.sleep(0.5)
        
        results["end_time"] = datetime.now(timezone.utc).isoformat()
        return results
    
    async def _run_integration_test(self, scenario: Dict) -> Dict:
        """Run the full integration test workflow."""
        import sys
        from pathlib import Path
        
        # Add project root to path
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))
        
        from temporalio.client import Client
        from temporal.workflows import TransactionProcessingWorkflow
        from temporal.shared import TransactionDetails, TRANSACTION_PROCESSING_TASK_QUEUE
        from database.connection import connect_to_couchbase
        from database.repositories import TransactionRepository, DecisionRepository
        from database.schemas import Transaction, TransactionStatus
        import time
        
        results = {
            "scenario_name": scenario["name"],
            "description": scenario["description"],
            "expected": scenario["expected_outcome"],
            "transactions": [],
            "start_time": datetime.now(timezone.utc).isoformat(),
            "workflow_ids": [],
            "integration_test_results": {}
        }
        
        try:
            # Step 1: Connect to Temporal
            client = await Client.connect(
                config.TEMPORAL_HOST,
                namespace=config.TEMPORAL_NAMESPACE
            )
            
            # Step 2: Connect to Couchbase
            await connect_to_couchbase()
            
            # Step 3: Create test transaction
            transaction_data = scenario["transactions"][0]
            test_transaction = Transaction(
                transaction_type=transaction_data["transaction_type"],
                amount=transaction_data["amount"],
                currency=transaction_data["currency"],
                sender=transaction_data["sender"],
                recipient=transaction_data["recipient"],
                description="Live demo test transaction",
                status=TransactionStatus.PENDING
            )
            
            transaction_id = await TransactionRepository.create_transaction(test_transaction)
            
            # Step 4: Prepare workflow input
            transaction_details = TransactionDetails(
                transaction_id=transaction_id,
                transaction_type=transaction_data["transaction_type"],
                amount=str(transaction_data["amount"]),
                currency=transaction_data["currency"],
                sender=transaction_data["sender"],
                recipient=transaction_data["recipient"],
                risk_flags=[],
                metadata=transaction_data.get("metadata", {})
            )
            
            # Step 5: Start workflow
            workflow_id = f"test-workflow-{transaction_id}"
            handle = await client.start_workflow(
                TransactionProcessingWorkflow.run,
                transaction_details,
                id=workflow_id,
                task_queue=TRANSACTION_PROCESSING_TASK_QUEUE,
            )
            
            results["workflow_ids"].append(workflow_id)
            
            # Step 6: Monitor workflow progress and send signal if needed
            max_wait = 120  # 2 minutes max
            start_time = time.time()
            last_state = None
            signal_sent = False
            
            while time.time() - start_time < max_wait:
                try:
                    state = await handle.query(TransactionProcessingWorkflow.get_state)
                    current_state = state.get("current_state", "unknown")
                    
                    # If workflow is waiting for human review, send a signal
                    if current_state == "escalated" and not signal_sent:
                        await handle.signal(TransactionProcessingWorkflow.human_review_complete, "approve")
                        signal_sent = True
                        results["integration_test_results"]["signal_sent"] = True
                    
                    if current_state in ["completed", "failed"]:
                        break
                    
                    await asyncio.sleep(2)
                except Exception as e:
                    await asyncio.sleep(2)
            
            # Step 7: Get workflow result
            try:
                result = await asyncio.wait_for(handle.result(), timeout=60.0)
                results["integration_test_results"]["workflow_result"] = {
                    "decision": result.get("decision"),
                    "confidence": result.get("confidence"),
                    "risk_score": result.get("risk_score"),
                    "processing_time_ms": result.get("processing_time_ms"),
                    "decision_id": result.get("decision_id")
                }
                
                # Verify decision in database
                decision = await DecisionRepository.get_decision_by_transaction(transaction_id)
                if decision:
                    results["integration_test_results"]["decision_in_db"] = True
                    results["integration_test_results"]["decision_details"] = {
                        "decision": decision.get("decision"),
                        "confidence": decision.get("confidence_score")
                    }
                
                # Verify transaction status
                transaction = await TransactionRepository.get_transaction(transaction_id)
                if transaction:
                    results["integration_test_results"]["transaction_status"] = transaction.get("status")
                
                results["transactions"].append({
                    "transaction_id": transaction_id,
                    "status": "completed",
                    "workflow_id": workflow_id,
                    "amount": float(transaction_data["amount"]),
                    "decision": result.get("decision"),
                    "processing_time_ms": result.get("processing_time_ms")
                })
                
            except Exception as e:
                # Error getting workflow result
                import traceback
                error_details = traceback.format_exc()
                results["transactions"].append({
                    "transaction_id": transaction_id if 'transaction_id' in locals() else "unknown",
                    "status": "error",
                    "error": str(e),
                    "amount": float(transaction_data["amount"]) if 'transaction_data' in locals() else 0.0
                })
                results["integration_test_results"]["error"] = str(e)
                results["integration_test_results"]["error_details"] = error_details
        
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            results["transactions"].append({
                "transaction_id": transaction_id if 'transaction_id' in locals() else "unknown",
                "status": "error",
                "error": str(e),
                "amount": float(transaction_data["amount"]) if 'transaction_data' in locals() else 0.0
            })
            results["integration_test_results"]["error"] = str(e)
            results["integration_test_results"]["error_details"] = error_details
        
        results["end_time"] = datetime.now(timezone.utc).isoformat()
        return results
    
    async def check_results(self, workflow_ids: List[str]) -> List[Dict]:
        """Check the results of submitted transactions."""
        results = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            for workflow_id in workflow_ids:
                # Extract transaction_id from workflow_id
                # Format: txn-processing-TXN_20250908_XXXXX
                parts = workflow_id.split("-")
                if len(parts) >= 3:
                    transaction_id = "-".join(parts[2:])
                    
                    try:
                        response = await client.get(
                            f"{self.api_url}/transaction/{transaction_id}"
                        )
                        if response.status_code == 200:
                            results.append(response.json())
                        else:
                            results.append({
                                "transaction_id": transaction_id,
                                "status": "pending"
                            })
                    except Exception as e:
                        results.append({
                            "transaction_id": transaction_id,
                            "error": str(e)
                        })
        
        return results


async def main():
    """Run all advanced scenarios."""
    print("\n" + "="*80)
    print("🚀 ADVANCED TRANSACTION PROCESSING SCENARIOS")
    print("="*80)
    print(f"Demonstrating couchbaseDB Cepalla Vector Search + Temporal Workflows")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    scenarios = AdvancedScenarios()
    test_scenarios = scenarios.generate_scenarios()
    
    print(f"\n📋 Scenarios to execute: {len(test_scenarios)}")
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"  {i}. {scenario['name']}")
    
    print("\n" + "-"*80)
    
    all_workflow_ids = []
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n🎯 Scenario {i}/{len(test_scenarios)}: {scenario['name']}")
        print(f"   Description: {scenario['description']}")
        print(f"   Expected: {scenario['expected_outcome']}")
        print(f"   Transactions: {len(scenario['transactions'])}")
        
        result = await scenarios.run_scenario(scenario)
        all_workflow_ids.extend(result["workflow_ids"])
        
        print(f"   ✅ Submitted {len(result['transactions'])} transactions")
        for txn in result["transactions"]:
            print(f"      - {txn['transaction_id']}: {txn['status']}")
        
        # Wait between scenarios
        if i < len(test_scenarios):
            print("\n⏳ Waiting 2 seconds before next scenario...")
            await asyncio.sleep(2)
    
    # Wait for processing
    print("\n" + "="*80)
    print("⏰ Waiting 15 seconds for all workflows to complete...")
    await asyncio.sleep(15)
    
    # Check results
    print("\n📊 Checking results...")
    results = await scenarios.check_results(all_workflow_ids)
    
    print("\n" + "="*80)
    print("📈 FINAL RESULTS")
    print("="*80)
    
    approved = [r for r in results if r.get("decision") == "approve"]
    rejected = [r for r in results if r.get("decision") == "reject"]
    escalated = [r for r in results if r.get("decision") == "escalate"]
    pending = [r for r in results if r.get("status") == "pending"]
    
    print(f"\n✅ Approved: {len(approved)}")
    print(f"❌ Rejected: {len(rejected)}")
    print(f"⚠️  Escalated: {len(escalated)}")
    print(f"⏳ Still Processing: {len(pending)}")
    
    print("\n" + "="*80)
    print("✨ Scenario execution complete!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())