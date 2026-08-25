"""Create vector search index in Couchbase Capella via REST API."""

import requests
import json
from pathlib import Path
from dotenv import load_dotenv
import os
from urllib.parse import urlparse

# Load .env
load_dotenv(Path(__file__).parent.parent / '.env')

def get_capella_rest_url(connection_string: str) -> str:
    """Extract REST API URL from connection string."""
    # Parse connection string
    # Format: couchbases://cb.xxxxx.cloud.couchbase.com
    if connection_string.startswith('couchbases://'):
        host = connection_string.replace('couchbases://', '').split('/')[0]
        # Capella REST API uses port 18094
        return f"https://{host}:18094"
    elif connection_string.startswith('couchbase://'):
        host = connection_string.replace('couchbase://', '').split('/')[0]
        return f"http://{host}:8094"
    else:
        # Assume it's already a full URL
        return connection_string

def create_vector_index():
    """Create vector search index in Couchbase Capella."""
    connection_string = os.getenv('COUCHBASE_CONNECTION_STRING', '')
    username = os.getenv('COUCHBASE_USERNAME', '')
    password = os.getenv('COUCHBASE_PASSWORD', '')
    bucket = os.getenv('COUCHBASE_BUCKET', 'transactions')
    scope = os.getenv('COUCHBASE_SCOPE', '_default')
    collection = os.getenv('TRANSACTIONS_COLLECTION', 'transactions')
    
    if not connection_string or not username or not password:
        print("❌ Missing required environment variables:")
        print("   - COUCHBASE_CONNECTION_STRING")
        print("   - COUCHBASE_USERNAME")
        print("   - COUCHBASE_PASSWORD")
        return
    
    # Get REST API URL
    rest_url = get_capella_rest_url(connection_string)
    index_name = "transaction_vector_index"
    index_url = f"{rest_url}/api/index/{index_name}"
    
    print("🚀 Creating Vector Search Index in Couchbase Capella")
    print("=" * 60)
    print(f"   Index Name: {index_name}")
    print(f"   Bucket: {bucket}")
    print(f"   Scope: {scope}")
    print(f"   Collection: {collection}")
    print(f"   REST URL: {rest_url}")
    print("=" * 60)
    
    # Index definition
    index_definition = {
        "type": "fulltext-index",
        "name": index_name,
        "sourceType": "couchbase",
        "sourceName": bucket,
        "planParams": {
            "maxPartitionsPerPIndex": 1024,
            "indexPartitions": 1
        },
        "params": {
            "doc_config": {
                "mode": "scope.collection.type_field",
                "type_mapping": {
                    "types": {
                        f"{scope}.{collection}": {
                            "enabled": True,
                            "dynamic": False,
                            "properties": {
                                "transaction_id": {
                                    "enabled": True,
                                    "fields": [{
                                        "name": "transaction_id",
                                        "type": "text",
                                        "analyzer": "keyword"
                                    }]
                                },
                                "transaction_type": {
                                    "enabled": True,
                                    "fields": [{
                                        "name": "transaction_type",
                                        "type": "text",
                                        "analyzer": "keyword"
                                    }]
                                },
                                "amount": {
                                    "enabled": True,
                                    "fields": [{
                                        "name": "amount",
                                        "type": "number"
                                    }]
                                },
                                "embedding": {
                                    "enabled": True,
                                    "fields": [{
                                        "name": "embedding",
                                        "type": "vector",
                                        "dims": 1536,
                                        "similarity": "cosine"
                                    }]
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    # Check if index already exists
    try:
        response = requests.get(
            index_url,
            auth=(username, password),
            verify=False,  # Capella uses self-signed certs
            timeout=10
        )
        if response.status_code == 200:
            print(f"✅ Index '{index_name}' already exists!")
            print(f"   Status: {response.json().get('status', 'unknown')}")
            return
    except requests.exceptions.SSLError:
        print("⚠️  SSL verification failed, continuing anyway...")
    except Exception as e:
        # Index doesn't exist, which is fine
        pass
    
    # Create the index
    try:
        print("\n📝 Creating index...")
        response = requests.put(
            index_url,
            auth=(username, password),
            json=index_definition,
            verify=False,  # Capella uses self-signed certs
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code in [200, 201, 202]:
            print(f"✅ Index '{index_name}' created successfully!")
            print(f"   Response: {response.status_code}")
            print("\n⏳ The index is now building. This may take a few minutes.")
            print("   Check status in Capella UI: Search → Indexes")
        elif response.status_code == 400:
            error_data = response.json() if response.text else {}
            print(f"❌ Error creating index: {response.status_code}")
            print(f"   Response: {response.text}")
            if 'already exists' in response.text.lower():
                print("   ℹ️  Index already exists")
            else:
                print("\n💡 Try creating it manually via Capella UI:")
                print("   1. Go to Search → Indexes → Create Index")
                print("   2. Name: transaction_vector_index")
                print("   3. Add vector field: embedding (1536 dims, cosine)")
        else:
            print(f"❌ Error creating index: {response.status_code}")
            print(f"   Response: {response.text}")
            print("\n💡 Try creating it manually via Capella UI")
            
    except requests.exceptions.SSLError as e:
        print(f"❌ SSL Error: {e}")
        print("\n💡 This is common with Capella. Try creating the index manually via UI:")
        print("   See scripts/create_vector_index.md for instructions")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Try creating the index manually via Capella UI:")
        print("   See scripts/create_vector_index.md for instructions")

if __name__ == "__main__":
    create_vector_index()

