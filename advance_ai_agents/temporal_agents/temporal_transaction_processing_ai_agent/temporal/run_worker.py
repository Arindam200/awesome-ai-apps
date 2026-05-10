"""Temporal worker for processing transaction workflows."""

import asyncio
import logging
from temporalio.client import Client
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
from temporal.shared import TRANSACTION_PROCESSING_TASK_QUEUE
from utils.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Run the Temporal worker."""
    logger.info("Starting Temporal worker...")
    logger.info(f"Connecting to Temporal at {config.TEMPORAL_HOST}")
    logger.info(f"Namespace: {config.TEMPORAL_NAMESPACE}")
    logger.info(f"Task Queue: {TRANSACTION_PROCESSING_TASK_QUEUE}")
    
    # Connect to Temporal
    client = await Client.connect(
        config.TEMPORAL_HOST,
        namespace=config.TEMPORAL_NAMESPACE
    )
    
    logger.info("Connected to Temporal server")
    
    # Create worker
    worker = Worker(
        client,
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
    )
    
    logger.info("Worker created. Starting to poll for tasks...")
    
    # Run worker
    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())

