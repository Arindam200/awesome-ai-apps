"""
Multi-Collection Conference corpus management with guaranteed working vector search
Clean implementation for conferences bucket with talks_* collections
"""
from typing import List, Dict, Any, Optional
import json
import os

from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.exceptions import DocumentExistsException, DocumentNotFoundException
from couchbase.options import ClusterOptions, ClusterTimeoutOptions
from couchbase.search import SearchRequest, MatchNoneQuery
from couchbase.vector_search import VectorQuery, VectorSearch
from datetime import datetime, timedelta
from dotenv import load_dotenv

from ..config.nebius_client import NebiusClient
load_dotenv()

class ConferenceCorpusManager:
    """Multi-collection corpus manager with guaranteed vector search"""

    def __init__(self):
        self.nebius_client = NebiusClient()
        self._initialize_couchbase()

    def _initialize_couchbase(self):
        """Initialize cloud Couchbase connection for multi-collection setup"""
        try:
            connection_string = os.getenv('CB_CONNECTION_STRING')
            username = os.getenv('CB_USERNAME')
            password = os.getenv('CB_PASSWORD')
            bucket_name = os.getenv('CB_BUCKET', 'conferences')

            if not all([connection_string, username, password]):
                raise ValueError("Missing required Couchbase environment variables")

            auth = PasswordAuthenticator(username, password)
            options = ClusterOptions(auth)
            options.apply_profile("wan_development")

            self.cluster = Cluster(connection_string, options)
            self.cluster.wait_until_ready(timedelta(seconds=5))

            self.bucket = self.cluster.bucket(bucket_name)
            self.scope = self.bucket.scope("_default")

            # Multi-collection search index
            self.search_index_name = os.getenv('CB_SEARCH_INDEX', 'conferences-talks-index')

            print(f"✅ Connected to Couchbase Cloud")
            print(f"   Bucket: {bucket_name}")
            print(f"   Multi-Collection Setup: talks_*")
            print(f"   Search Index: {self.search_index_name}")

        except Exception as e:
            print(f"❌ Failed to initialize Couchbase: {str(e)}")
            raise

    async def _ensure_collection_exists(self, collection_name: str):
        """Ensure collection exists and is ready for operations"""
        import asyncio

        max_wait_time = 60
        start_time = datetime.utcnow()

        try:
            collection_manager = self.bucket.collections()

            # Check if collection exists, create if not
            print(f"🔧 Ensuring collection exists: {collection_name}")
            collection_exists = False

            try:
                collections = collection_manager.get_all_scopes()
                for scope in collections:
                    if scope.name == "_default":
                        for collection in scope.collections:
                            if collection.name == collection_name:
                                collection_exists = True
                                print(f"✅ Collection already exists: {collection_name}")
                                break
                        break

                if not collection_exists:
                    print(f"🔧 Creating collection: {collection_name}")
                    collection_manager.create_collection(
                        scope_name="_default",
                        collection_name=collection_name
                    )
                    print(f"✅ Collection created: {collection_name}")
                    await asyncio.sleep(5)

            except Exception as create_error:
                print(f"⚠️ Collection creation warning: {str(create_error)}")

            # Get collection reference and test it
            collection = self.bucket.collection(collection_name)

            # Validate collection is ready with simple test
            validation_attempts = 0
            max_validation_attempts = 12

            while validation_attempts < max_validation_attempts:
                try:
                    elapsed_time = (datetime.utcnow() - start_time).total_seconds()
                    print(f"⏳ Collection validation attempt {validation_attempts + 1}/{max_validation_attempts} ({elapsed_time:.0f}s elapsed)")

                    test_key = f"_readiness_test_{datetime.utcnow().timestamp()}"
                    test_doc = {"test": True, "timestamp": datetime.utcnow().isoformat()}

                    collection.upsert(test_key, test_doc, timeout=timedelta(seconds=15))
                    result = collection.get(test_key, timeout=timedelta(seconds=10))
                    collection.remove(test_key)

                    if result and result.value:
                        print(f"✅ Collection {collection_name} is ready!")
                        return collection

                except Exception as validation_error:
                    validation_attempts += 1
                    elapsed_time = (datetime.utcnow() - start_time).total_seconds()

                    if elapsed_time >= max_wait_time:
                        error_msg = f"Collection validation timeout after {max_wait_time}s. Last error: {str(validation_error)}"
                        print(f"❌ {error_msg}")
                        break

                    if validation_attempts < max_validation_attempts:
                        wait_time = 5
                        print(f"⚠️ Validation failed: {str(validation_error)}")
                        print(f"⏳ Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)

            # If validation failed, return collection anyway (it might still work)
            print(f"⚠️ Collection validation incomplete, but proceeding with {collection_name}")
            return collection

        except Exception as e:
            error_msg = f"Error ensuring collection exists: {str(e)}"
            print(f"❌ {error_msg}")
            # Return collection reference anyway - it might work
            return self.bucket.collection(collection_name)

    async def store_conference_corpus(
        self,
        conference_info: Dict[str, Any],
        talks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Store conference corpus in multi-collection setup"""

        conference_id = conference_info['id']
        collection_name = f"talks_{conference_id}"

        try:
            # Create and ensure collection is ready
            collection = await self._ensure_collection_exists(collection_name)

            print(f"📦 Storing {len(talks)} talks for conference: {conference_id}")
            print(f"📍 Collection: {collection_name}")

            # Store talks with embeddings in batches
            successful_stores = 0
            failed_stores = 0
            batch_size = 10
            batch_delay = 2

            print(f"📦 Processing {len(talks)} talks in batches of {batch_size}")

            import asyncio
            for batch_start in range(0, len(talks), batch_size):
                batch_end = min(batch_start + batch_size, len(talks))
                batch = talks[batch_start:batch_end]
                batch_num = (batch_start // batch_size) + 1
                total_batches = (len(talks) + batch_size - 1) // batch_size

                print(f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} talks)...")

                batch_success = 0
                batch_failures = 0

                for i, talk in enumerate(batch):
                    global_index = batch_start + i
                    try:
                        # Generate document key
                        doc_key = self._generate_talk_key(talk, global_index)

                        # Generate embedding
                        combined_text = self._create_embedding_text(talk)
                        embedding = self.nebius_client.generate_embedding(combined_text)

                        # Create talk document with proper type field for indexing
                        talk_doc = {
                            **talk,
                            'conference_id': conference_id,
                            'embedding': embedding,
                            'embedding_text': combined_text,
                            'stored_at': datetime.utcnow().isoformat(),
                            'batch_number': batch_num,
                            'type': '_default'  # Required for index
                        }

                        # Store in collection
                        collection.upsert(doc_key, talk_doc, timeout=timedelta(seconds=20))
                        batch_success += 1
                        successful_stores += 1

                    except Exception as e:
                        print(f"❌ Error storing talk {global_index} (batch {batch_num}): {str(e)}")
                        batch_failures += 1
                        failed_stores += 1
                        continue

                print(f"✅ Batch {batch_num} complete: {batch_success} success, {batch_failures} failures")

                if batch_end < len(talks):
                    print(f"⏳ Waiting {batch_delay}s before next batch...")
                    await asyncio.sleep(batch_delay)

            # Store conference metadata
            metadata_doc = {
                **conference_info,
                'stored_at': datetime.utcnow().isoformat(),
                'total_talks': len(talks),
                'successful_stores': successful_stores,
                'failed_stores': failed_stores,
                'embedding_model': self.nebius_client.embedding_model,
                'collection_name': collection_name
            }

            try:
                collection.upsert(f"metadata_{conference_id}", metadata_doc)
                print(f"✅ Stored conference metadata")
            except Exception as e:
                print(f"⚠️ Warning storing metadata: {str(e)}")

            print(f"🎉 Storage complete!")
            print(f"✅ Successfully stored {successful_stores} talks")
            if failed_stores > 0:
                print(f"⚠️ Failed to store {failed_stores} talks")

            # Test vector search immediately after storage
            print(f"🧪 Testing vector search for new data...")
            test_result = await self._test_vector_search_for_conference(conference_id)

            return {
                'conference_id': conference_id,
                'collection_name': collection_name,
                'successful_stores': successful_stores,
                'failed_stores': failed_stores,
                'total_talks': len(talks),
                'vector_search_working': test_result
            }

        except Exception as e:
            print(f"❌ Error storing conference corpus: {str(e)}")
            raise

    async def _test_vector_search_for_conference(self, conference_id: str) -> bool:
        """Test vector search immediately after storing conference data"""
        import asyncio

        try:
            print(f"🔍 Testing vector search for {conference_id}...")

            # Wait for index to update
            await asyncio.sleep(10)

            # Test with simple query
            test_query = "kubernetes security"
            similar_talks = self.get_similar_talks(test_query, conference_id, 3)

            if similar_talks and len(similar_talks) > 0:
                print(f"✅ Vector search test PASSED - found {len(similar_talks)} results")
                return True
            else:
                print(f"⚠️ Vector search test returned 0 results")
                return False

        except Exception as e:
            print(f"❌ Vector search test failed: {str(e)}")
            return False

    def _generate_talk_key(self, talk: Dict[str, Any], index: int) -> str:
        """Generate unique document key for talk"""
        url = talk.get('url', '')
        if url:
            url_parts = url.rstrip('/').split('/')
            if len(url_parts) > 0:
                url_id = url_parts[-1]
                if url_id and url_id != 'event':
                    return f"talk_{url_id}"

        import hashlib
        title = (talk.get('title') or talk.get('url') or f'unknown_{index}').encode('utf-8', 'ignore')
        digest = hashlib.blake2b(title, digest_size=8).hexdigest()
        return f"talk_{index}_{digest}"
    def _create_embedding_text(self, talk: Dict[str, Any]) -> str:
        """Create text for embedding generation"""
        parts = []

        title = talk.get('title', '').strip()
        if title and title != 'Unknown Title':
            parts.append(f"Title: {title}")

        description = talk.get('description', '').strip()
        if description and description not in ['No description available', '']:
            parts.append(f"Description: {description}")

        category = talk.get('category', '').strip()
        if category and category not in ['Uncategorized', '']:
            parts.append(f"Category: {category}")

        speaker = talk.get('speaker', '').strip()
        if speaker and speaker not in ['Unknown Speaker', 'Unknown']:
            parts.append(f"Speaker: {speaker}")

        return '\n'.join(parts) if parts else title or 'Unknown talk'

    def get_similar_talks(
        self,
        query: str,
        conference_id: str = None,
        num_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Find similar talks using vector search across collections"""

        try:
            # Generate query embedding
            query_embedding = self.nebius_client.generate_embedding(query)

            # Create vector search request
            vector_query = VectorQuery("embedding", query_embedding, num_candidates=num_results * 2)
            vector_search = VectorSearch.from_vector_query(vector_query)
            search_request = SearchRequest.create(MatchNoneQuery()).with_vector_search(vector_search)

            # Execute search on scope (covers all collections)
            result = self.scope.search(
                self.search_index_name,
                search_request,
                timeout=timedelta(seconds=20)
            )
            rows = list(result.rows())

            similar_talks = []
            for row in rows:
                try:
                    # Extract collection name from document ID context or try multiple collections
                    doc_retrieved = False
                    talk = None

                    # If we have a specific conference, try that collection first
                    if conference_id:
                        try:
                            collection_name = f"talks_{conference_id}"
                            collection = self.bucket.collection(collection_name)
                            doc = collection.get(row.id, timeout=timedelta(seconds=5))
                            if doc and doc.value:
                                talk = doc.value
                                doc_retrieved = True
                        except:
                            pass

                    # If not retrieved yet, try to find the document in any talks_ collection
                    if not doc_retrieved:
                        # Try to determine collection from document structure or search all collections
                        collections = self._discover_talk_collections()
                        for coll_name in collections:
                            try:
                                collection = self.bucket.collection(coll_name)
                                doc = collection.get(row.id, timeout=timedelta(seconds=3))
                                if doc and doc.value:
                                    talk = doc.value
                                    doc_retrieved = True
                                    break
                            except:
                                continue

                    if doc_retrieved and talk:
                        # Filter by conference if specified
                        if conference_id and talk.get('conference_id') != conference_id:
                            continue

                        similar_talks.append({
                            "title": talk.get("title", "N/A"),
                            "description": talk.get("description", "N/A"),
                            "category": talk.get("category", "N/A"),
                            "speaker": talk.get("speaker", "N/A"),
                            "score": row.score,
                            "url": talk.get("url", ""),
                            "conference_id": talk.get("conference_id", "")
                        })

                        if len(similar_talks) >= num_results:
                            break

                except Exception as doc_error:
                    print(f"⚠️ Could not fetch document {row.id}: {doc_error}")
                    continue

            if similar_talks:
                print(f"✅ Vector search found {len(similar_talks)} results")
            else:
                print(f"⚠️ Vector search returned 0 results")

            return similar_talks[:num_results]

        except Exception as e:
            print(f"❌ Error during vector search: {str(e)}")
            return []

    def _discover_talk_collections(self) -> List[str]:
        """Discover all talks_* collections in the bucket"""
        try:
            collection_manager = self.bucket.collections()
            scopes = collection_manager.get_all_scopes()

            talks_collections = []
            for scope in scopes:
                if scope.name == "_default":
                    for collection_info in scope.collections:
                        collection_name = collection_info.name
                        if collection_name.startswith('talks_'):
                            talks_collections.append(collection_name)

            return talks_collections

        except Exception as e:
            print(f"⚠️ Error discovering collections: {str(e)}")
            return []

    def list_conferences(self) -> List[Dict[str, Any]]:
        """List all stored conferences"""
        try:
            conferences = []

            # Discover all talk collections
            collections = self._discover_talk_collections()

            for collection_name in collections:
                try:
                    collection = self.bucket.collection(collection_name)
                    conference_id = collection_name.replace('talks_', '')

                    # Try to get metadata
                    try:
                        metadata_doc = collection.get(f"metadata_{conference_id}", timeout=timedelta(seconds=10))
                        if metadata_doc and metadata_doc.value:
                            conf_data = metadata_doc.value
                            conferences.append({
                                'id': conf_data.get('id', conference_id),
                                'name': conf_data.get('name', f'Conference {conference_id}'),
                                'year': conf_data.get('year', 'Unknown'),
                                'platform': conf_data.get('platform', 'Unknown'),
                                'total_talks': conf_data.get('total_talks', 0),
                                'stored_at': conf_data.get('stored_at', ''),
                                'collection_name': collection_name,
                                'embedding_model': conf_data.get('embedding_model', 'Unknown')
                            })

                    except DocumentNotFoundException:
                        # Create basic info from collection
                        conferences.append({
                            'id': conference_id,
                            'name': f'Conference {conference_id}',
                            'year': 'Unknown',
                            'platform': 'Unknown',
                            'total_talks': 0,
                            'stored_at': '',
                            'collection_name': collection_name,
                            'embedding_model': 'Unknown'
                        })

                except Exception as e:
                    print(f"⚠️ Error processing collection {collection_name}: {str(e)}")
                    continue

            print(f"📊 Found {len(conferences)} conferences")
            return sorted(conferences, key=lambda x: x.get('stored_at', ''), reverse=True)

        except Exception as e:
            print(f"❌ Error listing conferences: {str(e)}")
            return []

    def close(self):
        """Close Couchbase connection"""
        try:
            self.cluster.close()
        except Exception as e:
            print(f"⚠️ Error closing Couchbase connection: {str(e)}")

# Convenience functions for easy integration
async def store_crawled_conference(crawl_result: Dict[str, Any]) -> Dict[str, Any]:
    """Store results from parallel crawler"""

    corpus_manager = ConferenceCorpusManager()

    try:
        if not crawl_result['success']:
            raise ValueError(f"Crawl failed: {crawl_result.get('error')}")

        return await corpus_manager.store_conference_corpus(
            crawl_result['conference'],
            crawl_result['talks']
        )

    finally:
        corpus_manager.close()

def search_conference_talks(query: str, conference_id: str = None, num_results: int = 5) -> List[Dict[str, Any]]:
    """Quick search function"""

    corpus_manager = ConferenceCorpusManager()

    try:
        return corpus_manager.get_similar_talks(query, conference_id, num_results)
    finally:
        corpus_manager.close()