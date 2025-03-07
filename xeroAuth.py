import os
import webbrowser
import requests
import base64

# Static values
REDIRECT_URL = os.getenv("XERO_REDIRECT_URL", "https://xero.com/")
SCOPE = os.getenv(
    "XERO_SCOPE", "offline_access accounting.transactions accounting.attachments")


def getClientCredentials(client_name):
    """
    Retrieves Xero client credentials dynamically from environment variables.
    """
    client_id = os.getenv(f"{client_name}_CLIENT_ID")
    client_secret = os.getenv(f"{client_name}_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError(
            f"❌ ERROR: Missing credentials for {client_name}. Ensure environment variables are set.")

    # Correctly encode client ID and secret as required by Xero
    credentials = f"{client_id}:{client_secret}"
    b64_id_secret = base64.b64encode(credentials.encode()).decode()

    return client_id, client_secret, b64_id_secret


def XeroFirstAuth(client_name):
    """
    Initiates the first authentication process for the given Xero client.
    """
    client_id, _, b64_id_secret = getClientCredentials(client_name)

    # 1. Redirect user to Xero authorization page
    auth_url = (
        f"https://login.xero.com/identity/connect/authorize?"
        f"response_type=code&client_id={client_id}"
        f"&redirect_uri={REDIRECT_URL}&scope={SCOPE}&state=123"
    )
    webbrowser.open_new(auth_url)

    # 2. User gets redirected with an authorization code
    auth_res_url = input("What is the response URL? ")
    start_number = auth_res_url.find("code=") + len("code=")
    end_number = auth_res_url.find(
        "&scope") if "&scope" in auth_res_url else len(auth_res_url)
    auth_code = auth_res_url[start_number:end_number]

    # 3. Exchange authorization code for access and refresh tokens
    exchange_code_url = "https://identity.xero.com/connect/token"
    response = requests.post(
        exchange_code_url,
        headers={
            "Authorization": f"Basic {b64_id_secret}",  # ✅ Ensure correct encoding
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URL,
        },
    )

    if response.status_code != 200:
        print(
            f"❌ Error exchanging code: {response.status_code} - {response.text}")
        return None

    json_response = response.json()
    return json_response.get("access_token"), json_response.get("refresh_token")


def XeroRefreshToken(client_name, refresh_token):
    """
    Refreshes the Xero access token for a given client.
    """
    print(f"🔄 Refreshing token for {client_name}...")
    _, _, b64_id_secret = getClientCredentials(client_name)

    token_refresh_url = "https://identity.xero.com/connect/token"
    response = requests.post(
        token_refresh_url,
        headers={
            "Authorization": f"Basic {b64_id_secret}",  # ✅ Fix: Ensure correct encoding
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
    )

    if response.status_code != 200:
        print(f"❌ Error refreshing token: {response.status_code} - {response.text}")
        return None

    json_response = response.json()
    return json_response.get("access_token"), json_response.get("refresh_token")


def XeroTenants(access_token):
    """
    Fetches the Xero tenant ID associated with the given access token.
    """
    connections_url = "https://api.xero.com/connections"
    response = requests.get(
        connections_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )

    if response.status_code != 200:
        print(f"❌ Error fetching tenants: {response.status_code} - {response.text}")
        return None

    json_response = response.json()
    return json_response[0]["tenantId"] if json_response else None
