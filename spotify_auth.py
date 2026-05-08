#!/usr/bin/env python3
"""Run this once to get your Spotify refresh token. Never needs to run again."""

import os
import base64
import requests
import webbrowser
from urllib.parse import urlencode, urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler

CLIENT_ID     = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
REDIRECT_URI  = "http://127.0.0.1:8888/callback"
SCOPE         = "playlist-read-private"

auth_code = None

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params = parse_qs(urlparse(self.path).query)
        print(f"Received path: {self.path}")     
        print(f"Params: {params}")
        auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Auth complete. You can close this tab.")

    def log_message(self, format, *args):
        pass


def main():
    # Step 1: open the Spotify login page in the browser
    params = urlencode({
        "client_id":     CLIENT_ID,
        "response_type": "code",
        "redirect_uri":  REDIRECT_URI,
        "scope":         SCOPE,
    })
    webbrowser.open(f"https://accounts.spotify.com/authorize?{params}")

    # Step 2: run a tiny local web server to catch the redirect
    print("Waiting for Spotify to redirect...")
    server = HTTPServer(("localhost", 8888), CallbackHandler)
    server.handle_request()

    if not auth_code:
        print("No code received. Check your redirect URI in the Spotify dashboard.")
        return

    # Step 3: exchange the auth code for tokens
    credentials = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {credentials}"},
        data={
            "grant_type":   "authorization_code",
            "code":         auth_code,
            "redirect_uri": REDIRECT_URI,
        },
    )
    tokens = response.json()

    if "refresh_token" not in tokens:
        print(f"Error: {tokens}")
        return

    print("\n=== YOUR REFRESH TOKEN (save this) ===")
    print(tokens["refresh_token"])
    print("======================================\n")
    print("Set it as an environment variable:")
    print(f'$env:SPOTIFY_REFRESH_TOKEN = "{tokens["refresh_token"]}"')


if __name__ == "__main__":
    main()
