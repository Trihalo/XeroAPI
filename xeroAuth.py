import os
import webbrowser
import requests

def XeroFirstAuth(client_id, redirect_url, scope, b64_id_secret):
    # 1. Send a user to authorize your app
    auth_url = (
        f"https://login.xero.com/identity/connect/authorize?"
        f"response_type=code&client_id={client_id}"
        f"&redirect_uri={redirect_url}&scope={scope}&state=123"
    )
    webbrowser.open_new(auth_url)

    # 2. Users are redirected back to you with a code
    auth_res_url = input("What is the response URL? ")
    start_number = auth_res_url.find("code=") + len("code=")
    end_number = auth_res_url.find("&scope")
    auth_code = auth_res_url[start_number:end_number]

    # 3. Exchange the code
    exchange_code_url = "https://identity.xero.com/connect/token"
    response = requests.post(
        exchange_code_url,
        headers={"Authorization": "Basic " + b64_id_secret},
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": redirect_url,
        },
    )

    if response.status_code != 200:
        print(f"Error exchanging code: {response.status_code} - {response.text}")
        return None

    json_response = response.json()
    # 4. Receive your tokens
    return json_response.get("access_token"), json_response.get("refresh_token")


def XeroRefreshToken(refresh_token, b64_id_secret):

    token_refresh_url = "https://identity.xero.com/connect/token"
    response = requests.post(
        token_refresh_url,
        headers={
            "Authorization": "Basic " + b64_id_secret,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
    )

    if response.status_code != 200:
        print(f"Error refreshing token: {response.status_code} - {response.text}")
        return None

    json_response = response.json()
    new_refresh_token = json_response.get("refresh_token")

    return json_response.get("access_token"), new_refresh_token


def XeroTenants(access_token):
    connections_url = "https://api.xero.com/connections"
    response = requests.get(
        connections_url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )

    if response.status_code != 200:
        print(f"Error fetching tenants: {response.status_code} - {response.text}")
        return None

    json_response = response.json()
    return json_response[0]["tenantId"] if json_response else None


def needsFirstAuth(xeroCompany):
    file_path = f'../refreshTokens/{xeroCompany}.txt'
    return not (os.path.exists(file_path) and os.path.getsize(file_path) > 0)
