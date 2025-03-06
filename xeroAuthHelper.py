import base64
import os
from xeroAuth import XeroFirstAuth, XeroRefreshToken, needsFirstAuth

# Constants for redirect URL and scope
REDIRECT_URL = "https://xero.com/"
SCOPE = "offline_access accounting.transactions accounting.attachments"


def getXeroAccessToken(client):
    """
    Retrieves or refreshes the Xero access token for the given client.
    """
    refresh_token_path = f"../refreshTokens/{client}.txt"

    # Load client credentials from environment variables
    client_id = os.getenv(f"{client.upper()}_CLIENT_ID")
    client_secret = os.getenv(f"{client.upper()}_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError(
            f"Missing environment variables for {client}. Ensure they are set.")

    # Encode credentials
    b64_id_secret = base64.b64encode(
        f"{client_id}:{client_secret}".encode()).decode()

    if needsFirstAuth(client):
        # Pass client name, not client_id, to XeroFirstAuth
        tokens = XeroFirstAuth(client)
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

        tokens = XeroRefreshToken(
            client, old_refresh_token)  # Pass client name
        if not tokens:
            raise Exception("Token refresh failed.")

        access_token, refresh_token = tokens

        # Update stored refresh token
        with open(refresh_token_path, "w") as file:
            file.write(refresh_token)

    return access_token
