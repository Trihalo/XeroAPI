import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xeroAuth import XeroTenants
from xeroAuthHelper import getXeroAccessToken
from helpers.fetchXeroInvoices import fetchXeroInvoices


def fetchInvoicesForClient(client_name, invoice_status):
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
    
