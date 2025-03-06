from requests_oauthlib import OAuth2Session
import os

client_id = os.getenv("OUTLOOK_CLIENT_ID")
client_secret = os.getenv("OUTLOOK_CLIENT_SECRET")
redirect_uri = "https://localhost"
authorization_base_url = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

outlook = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=["https://outlook.office.com/SMTP.Send"])
authorization_url, state = outlook.authorization_url(authorization_base_url)

print(f"Please go to {authorization_url} and authorize access.")

authorization_response = input("Enter the full callback URL: ")
token = outlook.fetch_token(token_url, authorization_response=authorization_response, client_secret=client_secret)

print(f"Access Token: {token['access_token']}")
print(f"Refresh Token: {token['refresh_token']}")