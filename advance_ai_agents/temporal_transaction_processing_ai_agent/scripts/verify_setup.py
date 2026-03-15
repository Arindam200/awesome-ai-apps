"""Verify setup before starting the application."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv(Path(__file__).parent.parent / '.env')

def check_env_var(name: str, required: bool = True) -> tuple[bool, str]:
    """Check if environment variable is set."""
    value = os.getenv(name)
    if required and not value:
        return False, f"❌ {name} is not set"
    elif not value:
        return True, f"⚠️  {name} is not set (optional)"
    else:
        # Mask sensitive values
        if 'PASSWORD' in name or 'KEY' in name or 'SECRET' in name:
            display_value = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
        else:
            display_value = value
        return True, f"✅ {name} = {display_value}"

def main():
    """Verify setup."""
    print("🔍 Verifying Application Setup")
    print("=" * 60)
    
    all_ok = True
    
    # Check required environment variables
    print("\n📋 Environment Variables:")
    print("-" * 60)
    
    required_vars = [
        ("COUCHBASE_CONNECTION_STRING", True),
        ("COUCHBASE_USERNAME", True),
        ("COUCHBASE_PASSWORD", True),
        ("COUCHBASE_BUCKET", True),
        ("OPENAI_API_KEY", True),
        ("TEMPORAL_HOST", True),
        ("TEMPORAL_NAMESPACE", False),
        ("TEMPORAL_TASK_QUEUE", False),
    ]
    
    for var_name, required in required_vars:
        ok, message = check_env_var(var_name, required)
        print(f"  {message}")
        if not ok:
            all_ok = False
    
    # Check Python packages
    print("\n📦 Python Packages:")
    print("-" * 60)
    
    required_packages = [
        "couchbase",
        "temporalio",
        "openai",
        "fastapi",
        "streamlit",
        "pydantic",
        "uvicorn",
    ]
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package} installed")
        except ImportError:
            print(f"  ❌ {package} NOT installed")
            all_ok = False
    
    # Check Temporal
    print("\n⏰ Temporal Server:")
    print("-" * 60)
    try:
        import requests
        response = requests.get("http://localhost:8080", timeout=2)
        if response.status_code == 200:
            print("  ✅ Temporal server is running (http://localhost:8080)")
        else:
            print(f"  ⚠️  Temporal server responded with status {response.status_code}")
    except Exception as e:
        print(f"  ❌ Temporal server not accessible: {e}")
        print("     Start it with: cd docker-compose && docker-compose up -d")
        all_ok = False
    
    # Check Couchbase connection
    print("\n💾 Couchbase Connection:")
    print("-" * 60)
    try:
        from couchbase.cluster import Cluster
        from couchbase.options import ClusterOptions
        from couchbase.auth import PasswordAuthenticator
        from datetime import timedelta
        
        connection_string = os.getenv("COUCHBASE_CONNECTION_STRING")
        username = os.getenv("COUCHBASE_USERNAME")
        password = os.getenv("COUCHBASE_PASSWORD")
        
        if connection_string and username and password:
            cluster = Cluster(
                connection_string,
                ClusterOptions(PasswordAuthenticator(username, password))
            )
            cluster.wait_until_ready(timedelta(seconds=5))
            print("  ✅ Connected to Couchbase")
            
            # Check bucket
            bucket_name = os.getenv("COUCHBASE_BUCKET")
            if bucket_name:
                bucket = cluster.bucket(bucket_name)
                print(f"  ✅ Bucket '{bucket_name}' accessible")
        else:
            print("  ⚠️  Couchbase credentials not set")
    except Exception as e:
        print(f"  ❌ Couchbase connection failed: {e}")
        all_ok = False
    
    # Summary
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ All checks passed! You're ready to start the application.")
        print("\n📖 Next steps:")
        print("   1. Start Temporal worker: python -m temporal.run_worker")
        print("   2. Start API server: uvicorn api.main:app --reload --port 8000")
        print("   3. Start Dashboard: streamlit run app.py --server.port 8501")
        print("\n   See START_APP.md for detailed instructions.")
        return 0
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        print("\n📖 See START_APP.md for setup instructions.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

