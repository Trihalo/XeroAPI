import base64
import os
import requests
from xeroAuth import XeroFirstAuth, XeroRefreshToken
from dotenv import load_dotenv

load_dotenv()

GITHUB_REPO = "Trihalo/XeroAPI"
GITHUB_PAT = os.getenv("GH_PAT")

GITHUB_SECRET_URL = f"https://api.github.com/repos/{GITHUB_REPO}/actions/secrets"


def get_github_secret(secret_name):
    """Fetch the latest refresh token from GitHub Secrets."""
    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(f"{GITHUB_SECRET_URL}/{secret_name}", headers=headers)

    if response.status_code == 200:
        return response.json().get("value") 
    elif response.status_code == 404:
        print(f"⚠️ Secret {secret_name} not found. It may not exist yet.")
        return None
    else:
        print(f"❌ Failed to fetch GitHub secret: {response.text}")
        return None


def get_github_public_key():
    """Retrieve the public key for encrypting GitHub Secrets."""
    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(f"{GITHUB_SECRET_URL}/public-key", headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Failed to get GitHub public key: {response.text}")
        return None


def update_github_secret(secret_name, new_value):
    """Update the refresh token in GitHub Secrets."""
    public_key_data = get_github_public_key()
    if not public_key_data:
        print("❌ Could not retrieve GitHub public key. Cannot update secret.")
        return
    key_id = public_key_data["key_id"]

    encrypted_value = base64.b64encode(new_value.encode()).decode()

    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "encrypted_value": encrypted_value, 
        "key_id": key_id
    }

    response = requests.put(f"{GITHUB_SECRET_URL}/{secret_name}", headers=headers, json=payload)

    if response.status_code in [201, 204]: print(f"✅ GitHub secret {secret_name} updated successfully!")
    else: print(f"❌ Failed to update GitHub secret: {response.text}")



def getXeroAccessToken(client):
    """
    Retrieves or refreshes the Xero access token for the given client.
    """
    client_id = os.getenv(f"{client.upper()}_CLIENT_ID")
    client_secret = os.getenv(f"{client.upper()}_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError(f"❌ Missing environment variables for {client}. Ensure they are set.")

    b64_id_secret = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    refresh_token_secret_name = f"XERO_REFRESH_TOKEN_{client.upper()}"
    refresh_token = get_github_secret(refresh_token_secret_name)

    if refresh_token is None:
        print(f"🔄 No refresh token found for {client}, initiating first-time authentication.")
        tokens = XeroFirstAuth(client)
        if not tokens:
            raise Exception("❌ First authentication failed.")

        access_token, new_refresh_token = tokens
        update_github_secret(refresh_token_secret_name, new_refresh_token)

    else:
        tokens = XeroRefreshToken(client, refresh_token)

        if not tokens:
            raise Exception("❌ Token refresh failed.")

        access_token, new_refresh_token = tokens

        if new_refresh_token and new_refresh_token != refresh_token:
            update_github_secret(refresh_token_secret_name, new_refresh_token)

    return access_token
