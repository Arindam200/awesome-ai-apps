import os
import json
from openai import OpenAI
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_couchbase_connection():
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
    
    return cluster, collection, bucket_name

def generate_embedding(text):
    client = OpenAI(
        base_url="https://api.studio.nebius.com/v1/",
        api_key=os.environ.get("NEBIUS_API_KEY")
    )
    
    response = client.embeddings.create(
        model="intfloat/e5-mistral-7b-instruct",
        input=text
    )
    
    return response.data[0].embedding

def process_talks():
    try:
        # Get Couchbase connection
        cluster, collection, bucket_name = get_couchbase_connection()
        
        # Query all documents
        query = f"SELECT * FROM `{bucket_name}`"
        result = cluster.query(query)
        
        successful = 0
        failed = 0
        
        # Process each document
        for row in result:
            try:
                doc = row[bucket_name]
                doc_key = row[bucket_name]['url'].split('/')[-1]
                
                # Combine fields for embedding
                combined_text = f"Title: {doc['title']}\nDescription: {doc['description']}\nCategory: {doc['category']}"
                
                # Generate embedding
                embedding = generate_embedding(combined_text)
                
                # Add embedding to document
                doc['embedding'] = embedding
                
                # Update document in Couchbase
                collection.upsert(f"talk_{doc_key}", doc)
                print(f"Updated embedding for: {doc['url']}")
                successful += 1
                
            except Exception as e:
                print(f"Error processing document: {str(e)}")
                failed += 1
        
        print(f"\nProcessing completed:")
        print(f"Successfully processed: {successful} documents")
        print(f"Failed to process: {failed} documents")
        
        # Close Couchbase connection
        cluster.close()
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    process_talks()

