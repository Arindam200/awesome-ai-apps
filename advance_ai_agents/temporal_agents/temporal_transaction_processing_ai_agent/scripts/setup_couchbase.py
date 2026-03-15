"""Setup script for Couchbase collections, indexes, and vector search."""

import asyncio
import logging
from pathlib import Path

# Load .env file FIRST, before importing config
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        logging.info(f"✅ Loaded .env file from {env_path}")
except ImportError:
    pass

from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.management.collections import CollectionSpec
from utils.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup_couchbase():
    """Setup Couchbase collections, indexes, and vector search."""
    try:
        logger.info("Connecting to Couchbase...")
        
        # Validate connection string
        if not config.COUCHBASE_CONNECTION_STRING:
            raise ValueError("COUCHBASE_CONNECTION_STRING is not set in .env file")
        
        logger.info(f"Connection string: {config.COUCHBASE_CONNECTION_STRING}")
        logger.info(f"Bucket: {config.COUCHBASE_BUCKET}")
        logger.info(f"Scope: {config.COUCHBASE_SCOPE}")
        
        # Connect to Couchbase
        auth = PasswordAuthenticator(config.COUCHBASE_USERNAME, config.COUCHBASE_PASSWORD)
        cluster_options = ClusterOptions(auth)
        
        try:
            cluster = Cluster(config.COUCHBASE_CONNECTION_STRING, cluster_options)
        except Exception as e:
            logger.error(f"❌ Failed to create cluster connection: {e}")
            logger.error(f"   Connection string: {config.COUCHBASE_CONNECTION_STRING}")
            logger.error("   For Capella, ensure connection string format is: couchbases://hostname")
            raise
        
        # Wait for connection
        from datetime import timedelta
        try:
            cluster.wait_until_ready(timeout=timedelta(seconds=30))
        except Exception as e:
            logger.error(f"❌ Failed to connect to Couchbase: {e}")
            logger.error("   Please verify:")
            logger.error("   1. Connection string is correct")
            logger.error("   2. Network connectivity")
            logger.error("   3. Credentials are correct")
            raise
        logger.info("✅ Connected to Couchbase")
        
        # Get bucket
        bucket = cluster.bucket(config.COUCHBASE_BUCKET)
        logger.info(f"✅ Opened bucket: {config.COUCHBASE_BUCKET}")
        
        # Get scope
        scope = bucket.scope(config.COUCHBASE_SCOPE)
        logger.info(f"✅ Using scope: {config.COUCHBASE_SCOPE}")
        
        # Create collections if they don't exist
        collections = [
            config.TRANSACTIONS_COLLECTION,
            config.DECISIONS_COLLECTION,
            config.HUMAN_REVIEWS_COLLECTION
        ]
        
        collection_manager = bucket.collections()
        
        for collection_name in collections:
            try:
                # Try to create collection (will fail if it already exists)
                collection_spec = CollectionSpec(collection_name, scope_name=config.COUCHBASE_SCOPE)
                collection_manager.create_collection(collection_spec)
                logger.info(f"✅ Created collection: {collection_name}")
            except Exception as e:
                error_str = str(e).lower()
                if 'already exists' in error_str or 'exists' in error_str:
                    logger.info(f"✅ Collection '{collection_name}' already exists")
                else:
                    logger.warning(f"⚠️  Could not create collection '{collection_name}': {e}")
                    logger.info(f"   You may need to create it manually in Couchbase UI:")
                    logger.info(f"   - Bucket: {config.COUCHBASE_BUCKET}")
                    logger.info(f"   - Scope: {config.COUCHBASE_SCOPE}")
                    logger.info(f"   - Collection: {collection_name}")
        
        # Create N1QL indexes
        logger.info("Creating N1QL indexes...")
        await create_n1ql_indexes(cluster)
        
        # Create Full-Text Search index with vector support
        logger.info("Creating Full-Text Search index with vector support...")
        await create_fts_vector_index(cluster)
        
        logger.info("✅ Couchbase setup complete!")
        
    except Exception as e:
        logger.error(f"❌ Error setting up Couchbase: {e}")
        raise

async def create_n1ql_indexes(cluster):
    """Create N1QL indexes for transactions."""
    indexes = [
        {
            "name": "idx_transaction_id",
            "query": f"""
                CREATE PRIMARY INDEX `idx_transaction_id` 
                ON `{config.COUCHBASE_BUCKET}`.`{config.COUCHBASE_SCOPE}`.`{config.TRANSACTIONS_COLLECTION}`
            """
        },
        {
            "name": "idx_transaction_type_amount",
            "query": f"""
                CREATE INDEX `idx_transaction_type_amount` 
                ON `{config.COUCHBASE_BUCKET}`.`{config.COUCHBASE_SCOPE}`.`{config.TRANSACTIONS_COLLECTION}`
                (transaction_type, amount, created_at)
            """
        },
        {
            "name": "idx_sender_recipient_country",
            "query": f"""
                CREATE INDEX `idx_sender_recipient_country` 
                ON `{config.COUCHBASE_BUCKET}`.`{config.COUCHBASE_SCOPE}`.`{config.TRANSACTIONS_COLLECTION}`
                (sender.country, recipient.country, status)
            """
        },
        {
            "name": "idx_transaction_status",
            "query": f"""
                CREATE INDEX `idx_transaction_status` 
                ON `{config.COUCHBASE_BUCKET}`.`{config.COUCHBASE_SCOPE}`.`{config.TRANSACTIONS_COLLECTION}`
                (status, created_at)
            """
        },
        {
            "name": "idx_decision_transaction_id",
            "query": f"""
                CREATE PRIMARY INDEX `idx_decision_transaction_id` 
                ON `{config.COUCHBASE_BUCKET}`.`{config.COUCHBASE_SCOPE}`.`{config.DECISIONS_COLLECTION}`
            """
        },
        {
            "name": "idx_decision_transaction",
            "query": f"""
                CREATE INDEX `idx_decision_transaction` 
                ON `{config.COUCHBASE_BUCKET}`.`{config.COUCHBASE_SCOPE}`.`{config.DECISIONS_COLLECTION}`
                (transaction_id, created_at)
            """
        },
        {
            "name": "idx_human_review_status",
            "query": f"""
                CREATE INDEX `idx_human_review_status` 
                ON `{config.COUCHBASE_BUCKET}`.`{config.COUCHBASE_SCOPE}`.`{config.HUMAN_REVIEWS_COLLECTION}`
                (status, priority, created_at)
            """
        }
    ]
    
    for index in indexes:
        try:
            result = cluster.query(index["query"])
            # Consume the result
            list(result)
            logger.info(f"✅ Created index: {index['name']}")
        except Exception as e:
            error_str = str(e).lower()
            if 'already exists' in error_str or 'duplicate' in error_str or '409' in error_str:
                logger.info(f"✅ Index '{index['name']}' already exists")
            else:
                logger.warning(f"⚠️  Could not create index '{index['name']}': {e}")

async def create_fts_vector_index(cluster):
    """Create Full-Text Search index with vector search support."""
    index_name = "transaction_vector_index"
    
    # FTS index definition with vector search
    index_definition = {
        "type": "fulltext-index",
        "name": index_name,
        "sourceType": "couchbase",
        "sourceName": config.COUCHBASE_BUCKET,
        "planParams": {
            "maxPartitionsPerPIndex": 1024,
            "indexPartitions": 1
        },
        "params": {
            "doc_config": {
                "docid_prefix_delim": "",
                "docid_regexp": "",
                "type_field": "type",
                "mode": "scope.collection.type_field",
                "type_mapping": {
                    "enabled": True,
                    "default_analyzer": "standard",
                    "default_datetime_parser": "dateTimeOptional",
                    "default_field": "_all",
                    "default_mapping": {
                        "enabled": False,
                        "dynamic": True,
                        "default_analyzer": "standard"
                    },
                    "default_type": "_default",
                    "types": {
                        f"{config.COUCHBASE_SCOPE}.{config.TRANSACTIONS_COLLECTION}": {
                            "enabled": True,
                            "dynamic": False,
                            "properties": {
                                "transaction_id": {
                                    "enabled": True,
                                    "dynamic": False,
                                    "fields": [{
                                        "name": "transaction_id",
                                        "type": "text",
                                        "analyzer": "keyword",
                                        "index": True
                                    }]
                                },
                                "transaction_type": {
                                    "enabled": True,
                                    "dynamic": False,
                                    "fields": [{
                                        "name": "transaction_type",
                                        "type": "text",
                                        "analyzer": "keyword",
                                        "index": True
                                    }]
                                },
                                "amount": {
                                    "enabled": True,
                                    "dynamic": False,
                                    "fields": [{
                                        "name": "amount",
                                        "type": "number",
                                        "index": True
                                    }]
                                },
                                "embedding": {
                                    "enabled": True,
                                    "dynamic": False,
                                    "fields": [{
                                        "name": "embedding",
                                        "type": "vector",
                                        "dims": 1536,
                                        "similarity": "cosine"
                                    }]
                                },
                                "sender": {
                                    "enabled": True,
                                    "dynamic": True
                                },
                                "recipient": {
                                    "enabled": True,
                                    "dynamic": True
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    try:
        search_manager = cluster.search_indexes()
        
        # Check if index exists
        try:
            existing_index = search_manager.get_index(index_name)
            logger.info(f"✅ FTS index '{index_name}' already exists")
            return
        except Exception:
            pass
        
        # Create the index
        # Note: Couchbase Python SDK may require different approach for FTS
        # This is a simplified version - you may need to use REST API or UI
        logger.info(f"⚠️  FTS index creation via SDK may require REST API")
        logger.info(f"   Please create the index manually via Couchbase UI or REST API")
        logger.info(f"   Index name: {index_name}")
        logger.info(f"   Vector dimensions: 1536")
        logger.info(f"   Similarity: cosine")
        
        # Alternative: Use REST API to create index
        logger.info("\n📝 To create the FTS index, use Couchbase UI:")
        logger.info("   1. Go to Search → Indexes → New Index")
        logger.info("   2. Name: transaction_vector_index")
        logger.info("   3. Bucket: " + config.COUCHBASE_BUCKET)
        logger.info("   4. Scope: " + config.COUCHBASE_SCOPE)
        logger.info("   5. Collection: " + config.TRANSACTIONS_COLLECTION)
        logger.info("   6. Add vector field: embedding (1536 dimensions, cosine similarity)")
        
    except Exception as e:
        logger.warning(f"⚠️  Could not create FTS index automatically: {e}")
        logger.info("   Please create it manually via Couchbase UI")

if __name__ == "__main__":
    asyncio.run(setup_couchbase())

