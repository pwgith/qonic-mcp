"""Quick OAuth helper — opens browser, gets a Qonic access token."""

import hashlib
import http.server
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ.get("QONIC_BASE_URL", "https://api.qonic.com")
CLIENT_ID = os.environ.get("QONIC_OAUTH_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("QONIC_OAUTH_CLIENT_SECRET", "")
AUTHORIZE_URL = os.environ.get(
    "QONIC_OAUTH_AUTHORIZE_URL", f"{BASE_URL}/v1/auth/authorize"
)
TOKEN_URL = os.environ.get("QONIC_OAUTH_TOKEN_URL", f"{BASE_URL}/v1/auth/token")
SCOPES = os.environ.get(
    "QONIC_OAUTH_SCOPES",
    "projects:read projects:write models:read models:write issues:read libraries:read libraries:write",
)

REDIRECT_PORT = 9876
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"


def main() -> None:
    # PKCE challenge
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = (
        hashlib.sha256(code_verifier.encode())
        .digest()
        .__class__
        # Use base64url encoding
    )
    import base64

    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )

    state = secrets.token_urlsafe(32)

    # Build authorization URL
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    # We'll capture the auth code via a simple local HTTP server
    auth_code = None
    error_msg = None

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code, error_msg
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

            if "error" in qs:
                error_msg = qs.get("error_description", qs["error"])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    f"<h2>OAuth Error</h2><p>{error_msg}</p>".encode()
                )
                return

            received_state = qs.get("state", [None])[0]
            if received_state != state:
                error_msg = "State mismatch"
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h2>State mismatch</h2>")
                return

            auth_code = qs.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<h2>Success!</h2><p>You can close this tab and return to the terminal.</p>"
            )

        def log_message(self, format, *args):
            pass  # Suppress log noise

    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), Handler)
    server.timeout = 120

    print(f"Opening browser to authorize with Qonic...")
    print(f"  URL: {auth_url}\n")
    webbrowser.open(auth_url)
    print("Waiting for callback (timeout: 120s)...")

    # Handle one request (the callback)
    server.handle_request()
    server.server_close()

    if error_msg:
        print(f"\nOAuth error: {error_msg}")
        sys.exit(1)

    if not auth_code:
        print("\nNo authorization code received.")
        sys.exit(1)

    print("Authorization code received. Exchanging for token...")

    # Exchange code for token
    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
        },
    )

    if resp.status_code != 200:
        print(f"\nToken exchange failed ({resp.status_code}):")
        print(resp.text)
        sys.exit(1)

    token_data = resp.json()
    access_token = token_data.get("access_token")

    print(f"\n{'='*60}")
    print(f"ACCESS TOKEN:")
    print(f"{access_token}")
    print(f"{'='*60}")
    print(f"\nPaste this into the MCP Inspector:")
    print(f'  1. Enable the "Authorization" custom header (toggle it on)')
    print(f"  2. Set the value to: Bearer {access_token}")
    print(f"  3. Click Reconnect")


if __name__ == "__main__":
    main()
