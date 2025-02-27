import sys
import os
from datetime import datetime
from atbAnalysis import processAtbData

# Ensure the script can find modules in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xeroAuth import XeroTenants
from xeroAuthHelper import getXeroAccessToken
from helpers.fetchXeroInvoices import fetchXeroInvoices
from helpers.emailAttachment import sendEmailWithAttachment

def fetch_invoices_for_client(client_name, invoice_status):
    """Fetch invoices for a given client."""
    access_token = getXeroAccessToken(client_name)
    xero_tenant_id = XeroTenants(access_token)
    
    if not xero_tenant_id:
        raise Exception(f"Could not retrieve Xero tenant ID for {client_name}.")
    
    invoices_response = fetchXeroInvoices(access_token, xero_tenant_id, invoice_status)
    
    # Ensure we extract only the list of invoices
    if isinstance(invoices_response, dict) and "Invoices" in invoices_response:
        return invoices_response["Invoices"], access_token, xero_tenant_id
    elif isinstance(invoices_response, list):
        return invoices_response, access_token, xero_tenant_id
    else:
        raise Exception(f"Unexpected response format from Xero API for {client_name}: {type(invoices_response)}")

def main():
    clients = ["Futureyou_Recruitment", "Futureyou_Contracting"]
    invoice_status = "AUTHORISED"

    all_invoices = []
    client_tokens = {}

    try:
        for client in clients:
            invoices, access_token, xero_tenant_id = fetch_invoices_for_client(client, invoice_status)
            
            if not isinstance(invoices, list):
                raise Exception(f"Expected a list of invoices but got {type(invoices)} for {client}")
            
            all_invoices.extend(invoices)
            
            client_tokens[client] = {
                "access_token": access_token,
                "xero_tenant_id": xero_tenant_id
            }

        filePath = processAtbData({"Invoices": all_invoices}, client_tokens)

        recipients = ["intern@future-you.com.au"]
        subject = "ATB Report"
        time = datetime.now().strftime("%d/%m/%Y %I:%M %p")
        body = f"Hi Silvia,\nPlease find the attached ATB report as of {time}.\n\nThanks"

        sendEmailWithAttachment(recipients, subject, body, filePath)


    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
