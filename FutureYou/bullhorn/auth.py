#!/usr/bin/env python3
import os
import sys
import json
import urllib.parse
from urllib.parse import urlsplit, parse_qs
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ.get("FUTUREYOU_BULLHORN_CLIENT_ID")
CLIENT_SECRET = os.environ.get("FUTUREYOU_BULLHORN_CLIENT_SECRET")
USERNAME = os.environ.get("FUTUREYOU_BULLHORN_USERNAME", "futureyou.restapi")
PASSWORD = os.environ.get("FUTUREYOU_BULLHORN_PASSWORD")
REDIRECT_URI = os.environ.get("FUTUREYOU_BULLHORN_REDIRECT_URI")

session = requests.Session()
session.headers["User-Agent"] = "futureyou-bh-oauth/1.0"
TIMEOUT = 30

def pretty(obj):
    print(json.dumps(obj, indent=2, sort_keys=True))

def authenticate():
    """
    Run Bullhorn OAuth flow and return:
    - BhRestToken
    - restUrl
    - access_token
    - refresh_token
    """

    # Discover swimlane
    login_info = session.get(
        "https://rest.bullhornstaffing.com/rest-services/loginInfo",
        params={"username": USERNAME},
        timeout=TIMEOUT,
    ).json()

    if "oauthUrl" not in login_info:
        sys.exit("loginInfo missing oauthUrl. Check username or Bullhorn status.")

    parts = urlsplit(login_info["oauthUrl"])
    oauth_base = f"{parts.scheme}://{parts.netloc}"
    token_url = f"{oauth_base}/oauth/token"
    authorize_url = f"{oauth_base}/oauth/authorize"

    # Manual step for first-time auth
    auth_params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "action": "Login",
        "username": USERNAME,
        "password": PASSWORD,
        "redirect_uri": REDIRECT_URI,
        "state": "xyz-123",
    }
    auth_url = f"{authorize_url}?{urllib.parse.urlencode(auth_params)}"

    print("\n=== ACTION REQUIRED ===")
    print("Open this URL in a browser and login, then paste redirect URL:")
    print(auth_url)

    redirected = input("Paste redirect URL: ").strip()
    qs = parse_qs(urlsplit(redirected).query)
    code = (qs.get("code") or [None])[0]
    if not code:
        sys.exit("No 'code' found in redirect URL.")

    # Exchange for tokens
    token_resp = session.post(
        token_url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=TIMEOUT,
    )
    tokens = token_resp.json()
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    # REST login
    rest_base = f"{urlsplit(login_info['restUrl']).scheme}://{urlsplit(login_info['restUrl']).netloc}"
    rest_login_resp = session.get(
        f"{rest_base}/rest-services/login",
        params={"version": "*", "access_token": access_token},
        timeout=TIMEOUT,
    )
    rest_login = rest_login_resp.json()

    BhRestToken = rest_login["BhRestToken"]
    restUrl = rest_login["restUrl"]

    return {
        "BhRestToken": BhRestToken,
        "restUrl": restUrl,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }

if __name__ == "__main__":
    creds = authenticate()
    pretty(creds)
