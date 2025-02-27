import base64
import os
from xeroAuth import XeroFirstAuth, XeroRefreshToken, needsFirstAuth
from clientHelper import load_client_config

def getXeroAccessToken(client):
    """
    Retrieves or refreshes the Xero access token for the given client.
    """
    refresh_token_path = f"../refreshTokens/{client}.txt"

    # Load client-specific config
    config = load_client_config(client)

    client_id = config["client_id"]
    client_secret = config["client_secret"]
    redirect_url = config["redirect_url"]
    scope = config["scope"]

    # Encode credentials
    b64_id_secret = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    if needsFirstAuth(client):
        tokens = XeroFirstAuth(client_id, redirect_url, scope, b64_id_secret)
        if not tokens:
            raise Exception("First authentication failed.")
        
        access_token, refresh_token = tokens

        # Save the refresh token
        os.makedirs(os.path.dirname(refresh_token_path), exist_ok=True)
        with open(refresh_token_path, "w") as file:
            file.write(refresh_token)

    else:
        # Read the existing refresh token
        if os.path.exists(refresh_token_path):
            with open(refresh_token_path, "r") as file:
                old_refresh_token = file.read().strip()
        else:
            raise Exception("Refresh token file not found.")

        tokens = XeroRefreshToken(old_refresh_token, b64_id_secret)
        if not tokens:
            raise Exception("Token refresh failed.")

        access_token, refresh_token = tokens

        # Update stored refresh token
        with open(refresh_token_path, "w") as file:
            file.write(refresh_token)

    return access_token
