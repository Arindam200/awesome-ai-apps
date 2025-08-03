import sys
from bs4 import BeautifulSoup

def extract_event_urls(html_content):
    base_url = "https://kccncna2024.sched.com/"
    soup = BeautifulSoup(html_content, 'html.parser')
    urls = set()
    for link in soup.find_all('a', href=True):
        href = link['href']
        if href.startswith('event/'):
            full_url = f"{base_url}{href}"
            urls.add(full_url)
    return urls

if __name__ == "__main__":
    html_input = sys.stdin.read()
    new_urls = extract_event_urls(html_input)
    
    # Read existing URLs
    existing_urls = set()
    try:
        with open("event_urls.txt", "r") as f:
            existing_urls = set(line.strip() for line in f)
    except FileNotFoundError:
        pass
    
    # Combine existing and new URLs
    all_urls = sorted(existing_urls.union(new_urls))
    
    # Write back all unique URLs
    with open("event_urls.txt", "w") as f:
        for url in all_urls:
            f.write(url + "\n")
    
    new_count = len(new_urls - existing_urls)
    print(f"Added {new_count} new URLs. Total URLs in file: {len(all_urls)}")
