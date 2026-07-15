"""
One-time Gmail OAuth2 setup script.

Run this LOCALLY (not in Docker) to authorize the ESG to access your Gmail.
It will open your browser, ask you to log in, and save a token.json file.

Usage:
    python scripts/setup_gmail_auth.py
"""

import json
import os
import sys

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add the project root to the path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, "credentials.json")
TOKEN_FILE = os.path.join(PROJECT_ROOT, "token.json")

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def main():
    print("=" * 60)
    print("  Email Security Gateway -- Gmail OAuth2 Setup")
    print("=" * 60)
    print()

    # Check for credentials.json
    if not os.path.exists(CREDENTIALS_FILE):
        print("[ERROR] credentials.json not found!")
        print(f"   Expected at: {CREDENTIALS_FILE}")
        print()
        print("   To fix this:")
        print("   1. Go to https://console.cloud.google.com/apis/credentials")
        print("   2. Download your OAuth 2.0 Client ID JSON")
        print("   3. Save it as 'credentials.json' in the project root")
        sys.exit(1)

    print(f"[OK] Found credentials.json at {CREDENTIALS_FILE}")

    # Install dependencies if needed
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print()
        print("Installing required packages...")
        os.system(f"{sys.executable} -m pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None

    # Check if token.json already exists
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            print("[OK] Found existing token.json")
        except Exception:
            creds = None

    # If credentials are invalid or don't exist, run the OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("  Token expired, refreshing...")
            creds.refresh(Request())
        else:
            print()
            print("[BROWSER] Opening your browser for Google sign-in...")
            print("   (If a browser doesn't open, copy the URL from the terminal)")
            print()

            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the token
        with open(TOKEN_FILE, "w") as token_file:
            token_file.write(creds.to_json())
        print(f"[OK] Token saved to {TOKEN_FILE}")

    # Verify by fetching user profile
    try:
        from googleapiclient.discovery import build

        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        email_address = profile.get("emailAddress", "unknown")
        total_messages = profile.get("messagesTotal", 0)

        print()
        print("=" * 60)
        print(f"  SUCCESS! Gmail API is authorized.")
        print(f"  Email: {email_address}")
        print(f"  Total messages: {total_messages:,}")
        print("=" * 60)
        print()
        print("  Next steps:")
        print("  1. Run: docker-compose up --build -d")
        print("  2. The gmail-connector will start monitoring your inbox")
        print("  3. Open http://localhost:3002 to see the dashboard")
        print()

    except Exception as e:
        print(f"[WARN] Token saved but verification failed: {e}")
        print("  The token should still work. Try running docker-compose up.")


if __name__ == "__main__":
    main()
