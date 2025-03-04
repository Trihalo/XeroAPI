import json
import requests
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def fetchXeroInvoices(accessToken, xeroTenantId, status):
    url = "https://api.xero.com/api.xro/2.0/Invoices"

    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {accessToken}",
            "Xero-tenant-id": xeroTenantId,
            "Accept": "application/json",
        },
        params={"Statuses": [status], "pageSize": 1000},
    )

    if response.status_code == 200:
        json_response = response.json()
        return json_response
    else:
        raise Exception(f"Error fetching invoices: {response.status_code} - {response.text}")