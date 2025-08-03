import json
import os
from datetime import datetime
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.exceptions import DocumentExistsException
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def save_to_couchbase():
    try:
        # Read data from JSON file
        with open('talk_results1.json', 'r') as f:
            talks = json.load(f)
        
        # Connect to Couchbase
        connection_string = os.getenv('CB_CONNECTION_STRING')
        username = os.getenv('CB_USERNAME')
        password = os.getenv('CB_PASSWORD')
        bucket_name = os.getenv('CB_BUCKET')
        collection_name = os.getenv('CB_COLLECTION')
        
        if not all([connection_string, username, password, bucket_name, collection_name]):
            raise ValueError("Missing required Couchbase environment variables")
        
        # Initialize Couchbase connection
        auth = PasswordAuthenticator(username, password)
        options = ClusterOptions(auth)
        cluster = Cluster(connection_string, options)
        
        # Wait for the cluster to be ready
        cluster.ping()
        
        bucket = cluster.bucket(bucket_name)
        collection = bucket.collection(collection_name)
        
        # Process each talk
        successful = 0
        failed = 0
        
        for talk in talks:
            try:
                # Add timestamp
                talk['crawled_at'] = datetime.utcnow().isoformat()
                
                # Generate document key from URL
                doc_key = f"talk_{talk['url'].split('/')[-1]}"
                
                try:
                    # Try to insert new document
                    collection.insert(doc_key, talk)
                    print(f"Stored in Couchbase: {talk['url']}")
                    successful += 1
                except DocumentExistsException:
                    # Update if document exists
                    collection.upsert(doc_key, talk)
                    print(f"Updated in Couchbase: {talk['url']}")
                    successful += 1
                except Exception as e:
                    print(f"Error storing {talk['url']}: {str(e)}")
                    failed += 1
                    
            except Exception as e:
                print(f"Error processing talk: {str(e)}")
                failed += 1
        
        print(f"\nProcessing completed:")
        print(f"Successfully stored: {successful} talks")
        print(f"Failed to store: {failed} talks")
        
        # Close Couchbase connection
        cluster.close()
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    save_to_couchbase() 