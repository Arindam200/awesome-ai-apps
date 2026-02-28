#!/usr/bin/env python3
"""
Docker health check script for AI applications
"""
import sys
import requests
import json
import os

def main():
    port = os.environ.get('APP_PORT', '8000')
    health_endpoint = os.environ.get('HEALTH_ENDPOINT', '/health')

    try:
        response = requests.get(f'http://localhost:{port}{health_endpoint}', timeout=5)

        if response.status_code == 200:
            print("✅ Health check passed")
            sys.exit(0)
        else:
            print(f"❌ Health check failed: HTTP {response.status_code}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Health check error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
