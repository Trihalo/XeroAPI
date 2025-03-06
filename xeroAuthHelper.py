import base64
import os
import requests
import json
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

    print(f"🔍 DEBUG: GitHub API Response for {secret_name}: {response.status_code}")
    print(f"🔍 DEBUG: Response Content: {response.text}")
    print(f"🔍 DEBUG: Full Response JSON: {json.dumps(response.json(), indent=2)}")


    if response.status_code == 200:
        return response.json().get("encrypted_value")
    elif response.status_code == 404:
        print(f"⚠️ WARNING: Secret {secret_name} not found. Returning None.")
        return None
    else:
        print(f"❌ ERROR: Failed to fetch GitHub secret: {response.text}")
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
        print("❌ ERROR: Could not retrieve GitHub public key. Cannot update secret.")
        return

    public_key = public_key_data["key"]
    key_id = public_key_data["key_id"]

    # ✅ GitHub requires the secret value to be Base64-encoded
    encrypted_value = base64.b64encode(new_value.encode()).decode()

    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "encrypted_value": encrypted_value,
        "key_id": key_id
    }

    print(f"🔍 DEBUG: Updating GitHub Secret {secret_name}")
    print(f"🔍 DEBUG: Payload Sent: {json.dumps(payload, indent=2)}")

    response = requests.put(f"{GITHUB_SECRET_URL}/{secret_name}", headers=headers, json=payload)

    if response.status_code in [201, 204]:
        print(f"✅ GitHub secret {secret_name} updated successfully!")
    else:
        print(f"❌ ERROR: Failed to update GitHub secret: {response.text}")


def getXeroAccessToken(client):
    """
    Retrieves or refreshes the Xero access token for the given client.
    """
    client_id = os.getenv(f"{client.upper()}_CLIENT_ID")
    client_secret = os.getenv(f"{client.upper()}_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError(f"❌ Missing environment variables for {client}. Ensure they are set.")

    b64_id_secret = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    
    refresh_token = os.getenv(f"XERO_REFRESH_TOKEN_{client.upper()}")

    if refresh_token is None or refresh_token == "INIT":
        print(f"🔄 No refresh token found for {client}, initiating first-time authentication.")
        tokens = XeroFirstAuth(client)
        if not tokens:
            raise Exception("❌ First authentication failed.")

        access_token, new_refresh_token = tokens
        update_github_secret(f"XERO_REFRESH_TOKEN_{client.upper()}", new_refresh_token)

    else:
        print(f"🔄 Refreshing token for {client}")
        tokens = XeroRefreshToken(client, refresh_token)

        if not tokens:
            raise Exception("❌ Token refresh failed.")

        access_token, new_refresh_token = tokens

        if new_refresh_token and new_refresh_token != refresh_token:
            update_github_secret(f"XERO_REFRESH_TOKEN_{client.upper()}", new_refresh_token)

    return access_token
