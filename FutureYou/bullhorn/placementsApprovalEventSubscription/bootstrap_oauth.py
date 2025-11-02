# bootstrap_oauth.py
import json
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
import os

from dotenv import load_dotenv
load_dotenv()

CLIENT_ID = os.environ.get("FUTUREYOU_CALENDAR_OAUTH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("FUTUREYOU_CALENDAR_OAUTH_CLIENT_SECRET")

REDIRECT_URI = "http://127.0.0.1:8081/callback"
SCOPE = "https://www.googleapis.com/auth/calendar"

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/callback"):
            qs = parse_qs(urlparse(self.path).query)
            code = qs.get("code", [None])[0]
            if not code:
                self.send_response(400); self.end_headers()
                self.wfile.write(b"Missing ?code"); return
            token = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "redirect_uri": REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
                timeout=30,
            ).json()
            token["client_id"] = CLIENT_ID
            token["client_secret"] = CLIENT_SECRET
            token["token_uri"] = "https://oauth2.googleapis.com/token"
            token["scopes"] = [SCOPE]
            self.send_response(200); self.end_headers()
            self.wfile.write(b"All set! You can close this window.")
            print("\n=== COPY THIS JSON BELOW ===\n")
            print(json.dumps(token, indent=2))
        else:
            self.send_response(404); self.end_headers()

if __name__ == "__main__":
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={SCOPE}"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    webbrowser.open(auth_url)
    HTTPServer(("127.0.0.1", 8081), Handler).serve_forever()
