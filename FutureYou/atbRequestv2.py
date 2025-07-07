import sys
import os
from atbAnalysisv2 import processAtbData

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from helpers.fetchInvoicesForClient import fetchInvoicesForClient

def main():
    clients = ["FUTUREYOU_RECRUITMENT", "FUTUREYOU_CONTRACTING"] 
    invoice_status = "AUTHORISED"

    all_invoices = []
    client_tokens = {}

    try:
        for client in clients:
            invoices, access_token, xero_tenant_id = fetchInvoicesForClient(client, invoice_status)
            if not isinstance(invoices, list):
                raise Exception(
                    f"Expected a list of invoices but got {type(invoices)} for {client}")
            all_invoices.extend(invoices)
            client_tokens[client] = {
                "access_token": access_token,
                "xero_tenant_id": xero_tenant_id
            }
        processAtbData({"Invoices": all_invoices}, client_tokens)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
