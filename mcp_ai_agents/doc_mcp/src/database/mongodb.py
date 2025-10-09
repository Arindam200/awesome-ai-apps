"""MongoDB client wrapper with connection management."""

from typing import Optional
import logging

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from ..core.config import settings
from ..core.exceptions import VectorStoreError
logger = logging.getLogger(__name__)


class MongoDBClient:
    """MongoDB client wrapper with connection management."""

    def __init__(self):
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None

    @property
    def client(self) -> MongoClient:
        """Get MongoDB client with lazy initialization."""
        if self._client is None:
            try:
                self._client = MongoClient(settings.mongodb_uri)
                # Test connection
                self._client.admin.command("ping")
                logger.info("Successfully connected to MongoDB")
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                raise VectorStoreError(f"Failed to connect to MongoDB: {e}") from e
        return self._client

    @property
    def database(self) -> Database:
        """Get database instance."""
        if self._db is None:
            self._db = self.client[settings.db_name]
        return self._db

    def get_collection(self, collection_name: str) -> Collection:
        """Get collection by name."""
        return self.database[collection_name]

    def test_connection(self) -> bool:
        """Test MongoDB connection."""
        try:
            self.client.admin.command("ping")
            return True
        except Exception as e:
            logger.error(f"MongoDB connection test failed: {e}")
            return False


# Global MongoDB client instance
mongodb_client = MongoDBClient()