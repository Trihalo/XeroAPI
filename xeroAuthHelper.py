import os
import requests
import json
from xeroAuth import XeroFirstAuth, XeroRefreshToken
from dotenv import load_dotenv

load_dotenv()

GITHUB_REPO = "Trihalo/XeroAPI"
GITHUB_PAT = os.getenv("GH_PAT")

# API URLs
GITHUB_VARIABLES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/actions/variables"


def get_github_variable(var_name):
    """Fetch the latest value of a GitHub repository variable (refresh tokens only)."""
    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(f"{GITHUB_VARIABLES_URL}/{var_name}", headers=headers)

    if response.status_code == 200:
        return response.json().get("value")
    elif response.status_code == 404:
        print(f"⚠️ WARNING: GitHub variable {var_name} not found.")
        return None
    else:
        print(f"❌ ERROR: Failed to fetch GitHub variable {var_name}: {response.text}")
        return None


def update_github_variable(var_name, new_value):
    """Update the value of a GitHub repository variable (refresh tokens only)."""
    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {"value": new_value}

    response = requests.patch(f"{GITHUB_VARIABLES_URL}/{var_name}", headers=headers, json=payload)

    if response.status_code in [200, 204]:
        print(f"✅ GitHub variable {var_name} updated successfully!")
    else:
        print(f"❌ ERROR: Failed to update GitHub variable {var_name}: {response.text}")


def getXeroAccessToken(client):
    """
    Retrieves or refreshes the Xero access token for the given client.
    """
    client_id = os.getenv(f"{client.upper()}_CLIENT_ID")  
    client_secret = os.getenv(f"{client.upper()}_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError(f"❌ Missing environment variables for {client}. Ensure they are set.")

    refresh_token_var_name = f"XERO_REFRESH_TOKEN_{client.upper()}"
    refresh_token = get_github_variable(refresh_token_var_name) 

    if refresh_token is None or refresh_token == "INIT":
        print(f"🔄 No refresh token found for {client}, initiating first-time authentication.")
        tokens = XeroFirstAuth(client)
        if not tokens:
            raise Exception("❌ First authentication failed.")

        access_token, new_refresh_token = tokens
        update_github_variable(refresh_token_var_name, new_refresh_token) 
    else:
        tokens = XeroRefreshToken(client, refresh_token)

        if not tokens:
            raise Exception("❌ Token refresh failed.")

        access_token, new_refresh_token = tokens
    
        if new_refresh_token and (new_refresh_token != refresh_token):
            update_github_variable(refresh_token_var_name, new_refresh_token)

    return access_token
