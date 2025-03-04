import sys
import os
from datetime import datetime
from overdueAnalysis import processOverdueData
from atbRequest import fetch_invoices_for_client

# Ensure the script can find modules in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xeroAuth import XeroTenants
from xeroAuthHelper import getXeroAccessToken
from helpers.fetchXeroInvoices import fetchXeroInvoices
from helpers.emailAttachment import sendEmailWithAttachment


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

        filePath = processOverdueData({"Invoices": all_invoices}, client_tokens)

        # recipients = ["leo@trihalo.com.au", "silvia@trihalo.com.au"]
        # subject = "ATB Report"
        # time = datetime.now().strftime("%d/%m/%Y %I:%M %p")
        # body = f"Hi Silvia,\nPlease find the attached ATB report as of {time}.\n\nThanks"

        # sendEmailWithAttachment(recipients, subject, body, filePath)


    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
