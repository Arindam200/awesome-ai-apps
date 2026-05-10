# authenticator.py
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials



# Get the directory containing this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CLIENT_SECRETS = os.path.join(SCRIPT_DIR, "credentials.json")  # your OAuth client secret (Desktop app)
TOKEN_PATH = os.path.join(SCRIPT_DIR, "token.json")


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    # For creating events only:
    "https://www.googleapis.com/auth/calendar.events",
    # If you later need full calendar read/write, replace/add:
    # "https://www.googleapis.com/auth/calendar"
]
import sys

def main():
    # Check for credentials file first
    if not os.path.exists(CLIENT_SECRETS):
        print(f"❌ Error: {CLIENT_SECRETS} not found.")
        print("Please download OAuth credentials from Google Cloud Console.")
        print("See README.md for setup instructions.")
        sys.exit(1)


    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception as e:
            print(f"⚠️  Warning: Could not load existing token: {e}")
            print("Will re-authenticate...")
            creds = None
        

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Refreshing expired token...")
                creds.refresh(Request())
            except Exception as e:
                print(f"⚠️  Token refresh failed: {e}")
                print("Will re-authenticate...")
                creds = None
        
        if not creds:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
                creds = flow.run_local_server(port=8090)
            except Exception as e:
                print(f"❌ Authentication failed: {e}")
                sys.exit(1)

        try:
            with open(TOKEN_PATH, "w") as f:
                f.write(creds.to_json())
        except Exception as e:
            print(f"❌ Error writing token file: {e}")
            sys.exit(1)

    print("✅ Authentication complete. Token written to", TOKEN_PATH)

if __name__ == "__main__":
    main()
