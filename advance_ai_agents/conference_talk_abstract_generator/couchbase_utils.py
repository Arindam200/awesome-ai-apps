import asyncio
from crawl4ai import AsyncWebCrawler
import json
from bs4 import BeautifulSoup
import re
import os
from datetime import datetime
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.exceptions import DocumentExistsException
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

async def extract_talk_info(html_content):
    """Extract talk information from HTML content."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Initialize talk info dictionary with default values
        talk_info = {
            'title': 'Unknown',
            'description': 'No description available',
            'speaker': 'Unknown',
            'category': 'Uncategorized',
            'date': 'Unknown',
            'location': 'Unknown'
        }
        
        try:
            # Extract title - from the event name span
            title_elem = soup.find('span', class_='event')
            if title_elem:
                name_elem = title_elem.find('a', class_='name')
                if name_elem:
                    talk_info['title'] = name_elem.text.strip()
        except Exception as e:
            print(f"Error extracting title: {str(e)}")
        
        try:
            # Extract description - from the tip-description div
            desc_elem = soup.find('div', class_='tip-description')
            if desc_elem:
                talk_info['description'] = desc_elem.text.strip()
        except Exception as e:
            print(f"Error extracting description: {str(e)}")
        
        try:
            # Extract speakers - from the sched-event-details-roles div
            speakers = []
            speakers_div = soup.find('div', class_='sched-event-details-roles')
            if speakers_div:
                speaker_elems = speakers_div.find_all('h2')
                for speaker_elem in speaker_elems:
                    speaker_name = speaker_elem.find('a')
                    if speaker_name:
                        speakers.append(speaker_name.text.strip())
            talk_info['speaker'] = ' & '.join(speakers) if speakers else 'Unknown'
        except Exception as e:
            print(f"Error extracting speakers: {str(e)}")
        
        try:
            # Extract category - from the sched-event-type div
            category_elem = soup.find('div', class_='sched-event-type')
            if category_elem:
                category_link = category_elem.find('a')
                if category_link:
                    talk_info['category'] = category_link.text.strip()
        except Exception as e:
            print(f"Error extracting category: {str(e)}")
        
        try:
            # Extract date and time
            date_elem = soup.find('div', class_='sched-event-details-timeandplace')
            if date_elem:
                date_text = date_elem.get_text().split('\n')[0].strip()
                talk_info['date'] = date_text
        except Exception as e:
            print(f"Error extracting date: {str(e)}")
        
        try:
            # Extract location
            location_elem = soup.find('div', class_='sched-event-details-timeandplace')
            if location_elem:
                location_link = location_elem.find('a')
                if location_link:
                    talk_info['location'] = location_link.text.strip()
        except Exception as e:
            print(f"Error extracting location: {str(e)}")
        
        return talk_info
    except Exception as e:
        print(f"Error in extract_talk_info: {str(e)}")
        # Return a minimal talk info object if everything fails
        return {
            'title': 'Error extracting talk info',
            'description': f'Error: {str(e)}',
            'speaker': 'Unknown',
            'category': 'Error',
            'date': 'Unknown',
            'location': 'Unknown'
        }

async def crawl_talks():
    try:
        # Read URLs from sample.txt
        try:
            with open('event_urls.txt', 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print("Error: event_urls.txt file not found")
            return
        except Exception as e:
            print(f"Error reading event_urls.txt: {str(e)}")
            return
        
        if not urls:
            print("No URLs found in event_urls.txt")
            return
        
        # Initialize results list
        results = []
        successful_crawls = 0
        failed_crawls = 0
        
        # Connect to Couchbase
        try:
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
        except Exception as e:
            print(f"Error connecting to Couchbase: {str(e)}")
            return
        
        # Create crawler instance
        async with AsyncWebCrawler() as crawler:
            # Process URLs in batches to avoid overwhelming the server
            batch_size = 5
            for i in range(0, len(urls), batch_size):
                try:
                    batch_urls = urls[i:i + batch_size]
                    
                    # Crawl batch of URLs
                    batch_results = await crawler.arun_many(batch_urls)
                    
                    # Process results
                    for url, result in zip(batch_urls, batch_results):
                        try:
                            if result and result.html:
                                talk_info = await extract_talk_info(result.html)
                                talk_info['url'] = url
                                talk_info['crawled_at'] = datetime.utcnow().isoformat()
                                
                                # Generate a unique document key based on the talk URL
                                doc_key = f"talk_{url.split('/')[-1]}"
                                
                                try:
                                    # Insert the document into Couchbase
                                    collection.insert(doc_key, talk_info)
                                    print(f"Stored in Couchbase: {url}")
                                    print(f"Title: {talk_info['title']}")
                                    print(f"Category: {talk_info['category']}")
                                    print("-" * 80)
                                    successful_crawls += 1
                                except DocumentExistsException:
                                    # Update existing document
                                    collection.upsert(doc_key, talk_info)
                                    print(f"Updated in Couchbase: {url}")
                                    successful_crawls += 1
                                except Exception as e:
                                    print(f"Error storing in Couchbase: {url}")
                                    print(f"Error: {str(e)}")
                                    failed_crawls += 1
                            else:
                                print(f"Failed to crawl: {url}")
                                failed_crawls += 1
                        except Exception as e:
                            print(f"Error processing URL {url}: {str(e)}")
                            failed_crawls += 1
                    
                    # Add a small delay between batches
                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"Error processing batch: {str(e)}")
                    continue
        
        print(f"\nCrawling completed:")
        print(f"Successfully processed: {successful_crawls} talks")
        print(f"Failed to process: {failed_crawls} talks")
        
        # Close Couchbase connection
        try:
            cluster.close()
        except Exception as e:
            print(f"Error closing Couchbase connection: {str(e)}")
    
    except Exception as e:
        print(f"Unexpected error in crawl_talks: {str(e)}")

if __name__ == "__main__":
    asyncio.run(crawl_talks()) 