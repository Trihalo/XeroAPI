import json
import requests
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def fetchXeroInvoiceAttachmentsIds(accessToken, xeroTenantId, invoiceIds):
    baseUrl = "https://api.xero.com/api.xro/2.0/Invoices"
    invoiceAttachments = {}

    for invoiceId in invoiceIds:
        url = f"{baseUrl}/{invoiceId}/Attachments"

        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {accessToken}",
                "Xero-tenant-id": xeroTenantId,
                "Accept": "application/json",
            },
        )

        if response.status_code == 200:
            jsonResponse = response.json()
            attachments = jsonResponse.get("Attachments", [])
            # Extract all attachment IDs for the given invoice
            attachmentIds = [attachment["AttachmentID"] for attachment in attachments]
            invoiceAttachments[invoiceId] = attachmentIds if attachmentIds else None  # Store None if no attachments found
        else:
            invoiceAttachments[invoiceId] = f"Error: {response.status_code} - {response.text}"

    return invoiceAttachments


def fetchXeroInvoiceAttachmentsPDF(accessToken, tenantId, invoiceId, attachmentId):
    url = f"https://api.xero.com/api.xro/2.0/Invoices/{invoiceId}/Attachments/{attachmentId}"
    
    headers = {
        "Authorization": f"Bearer {accessToken}",
        "Xero-Tenant-Id": tenantId,
        "Accept": "application/pdf"  
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.content  # Return binary content (e.g., PDF, image, etc.)
    else:
        print(f"Error fetching attachment: {response.status_code} - {response.text}")
        return None
