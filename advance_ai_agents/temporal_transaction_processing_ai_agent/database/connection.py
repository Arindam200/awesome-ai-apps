"""Couchbase database connection management."""

import logging
from typing import Optional
from datetime import timedelta
from utils.config import config

logger = logging.getLogger(__name__)

# Use async couchbase for async operations
from acouchbase.cluster import Cluster as AsyncCluster

# Use sync couchbase for sync operations (Streamlit)
from couchbase.cluster import Cluster

# Shared options classes
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator

# Global connection objects (async)
_cluster: Optional[AsyncCluster] = None
_bucket = None
_scope = None
_db = None

# Sync connection objects (for Streamlit)
_sync_cluster: Optional[Cluster] = None
_sync_scope = None

async def connect_to_couchbase():
    """Connect to Couchbase cluster."""
    global _cluster, _bucket, _scope, _db
    
    if _cluster is not None:
        logger.info("Already connected to Couchbase")
        return
    
    # Validate connection string
    if not config.COUCHBASE_CONNECTION_STRING:
        raise ValueError("COUCHBASE_CONNECTION_STRING is not set. Please check your .env file.")
    
    if not config.COUCHBASE_USERNAME or not config.COUCHBASE_PASSWORD:
        raise ValueError("COUCHBASE_USERNAME and COUCHBASE_PASSWORD must be set. Please check your .env file.")
    
    try:
        logger.info(f"Connecting to Couchbase: {config.COUCHBASE_CONNECTION_STRING}")
        logger.info(f"Bucket: {config.COUCHBASE_BUCKET}, Scope: {config.COUCHBASE_SCOPE}")
        auth = PasswordAuthenticator(config.COUCHBASE_USERNAME, config.COUCHBASE_PASSWORD)
        cluster_options = ClusterOptions(auth)
        
        _cluster = await AsyncCluster.connect(config.COUCHBASE_CONNECTION_STRING, cluster_options)
        await _cluster.wait_until_ready(timedelta(seconds=30))
        
        _bucket = _cluster.bucket(config.COUCHBASE_BUCKET)
        await _bucket.on_connect()
        _scope = _bucket.scope(config.COUCHBASE_SCOPE)
        _db = _scope
        
        # Set module-level db
        import database.connection as conn_module
        conn_module.db = _db
        
        logger.info(f"✅ Connected to Couchbase bucket: {config.COUCHBASE_BUCKET}")
    except Exception as e:
        logger.error(f"Failed to connect to Couchbase: {e}")
        raise

async def close_couchbase_connection():
    """Close Couchbase connection."""
    global _cluster, _bucket, _scope, _db
    if _cluster:
        # Couchbase SDK handles cleanup automatically
        _cluster = None
        _bucket = None
        _scope = None
        _db = None
        logger.info("Couchbase connection closed")

def get_sync_cluster() -> Cluster:
    """Get synchronous Couchbase cluster connection (for Streamlit)."""
    global _sync_cluster
    
    if _sync_cluster is None:
        # Validate connection string
        if not config.COUCHBASE_CONNECTION_STRING:
            raise ValueError("COUCHBASE_CONNECTION_STRING is not set. Please check your .env file.")
        
        if not config.COUCHBASE_USERNAME or not config.COUCHBASE_PASSWORD:
            raise ValueError("COUCHBASE_USERNAME and COUCHBASE_PASSWORD must be set. Please check your .env file.")
        
        logger.info(f"Creating sync Couchbase connection: {config.COUCHBASE_CONNECTION_STRING}")
        auth = PasswordAuthenticator(config.COUCHBASE_USERNAME, config.COUCHBASE_PASSWORD)
        cluster_options = ClusterOptions(auth)
        
        _sync_cluster = Cluster(config.COUCHBASE_CONNECTION_STRING, cluster_options)
        _sync_cluster.wait_until_ready(timedelta(seconds=30))
        logger.info("✅ Sync Couchbase connection established")
    
    return _sync_cluster

def get_sync_scope():
    """Get synchronous Couchbase scope (for Streamlit)."""
    global _sync_scope
    
    if _sync_scope is None:
        cluster = get_sync_cluster()
        bucket = cluster.bucket(config.COUCHBASE_BUCKET)
        _sync_scope = bucket.scope(config.COUCHBASE_SCOPE)
        logger.info(f"✅ Sync scope opened: {config.COUCHBASE_SCOPE}")
    
    return _sync_scope

# Make db accessible as module-level variable
def get_db():
    """Get database scope."""
    if _db is None:
        raise RuntimeError("Couchbase not connected. Call connect_to_couchbase() first.")
    return _db

# Module-level db accessor (for backward compatibility)
# This will be set after connection
db = None

