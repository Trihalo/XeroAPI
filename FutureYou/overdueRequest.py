import sys
import os
from datetime import datetime, timedelta
from overdueAnalysis import processOverdueData

# Ensure the script can find modules in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from helpers.emailAttachment import sendEmailWithAttachment
from helpers.fetchInvoicesForClient import fetchInvoicesForClient
from helpers.dateStringsHelper import getSydneyDate


def main():
    clients = ["FUTUREYOU_RECRUITMENT", "FUTUREYOU_CONTRACTING"]
    invoice_status = "AUTHORISED"

    all_invoices = []
    client_tokens = {}

    try:
        for client in clients:
            invoices, access_token, xero_tenant_id = fetchInvoicesForClient(client, invoice_status)
            
            if not isinstance(invoices, list):
                raise Exception(f"Expected a list of invoices but got {type(invoices)} for {client}")
            
            all_invoices.extend(invoices)
            
            client_tokens[client] = {
                "access_token": access_token,
                "xero_tenant_id": xero_tenant_id
            }

        filePath = processOverdueData({"Invoices": all_invoices}, client_tokens)

        recipients = ["leo@trihalo.com.au"]
        time = (getSydneyDate(datetime.now().strftime("%Y-%m-%dT%H:%M:%S")) + timedelta(hours=13)).strftime("%d-%m-%Y %I:%M%p").lower()
        subject = f"Overdue Report at {time}"
        body = f"Hi Silvia,\nPlease find the attached Overdue report as of {time}.\n\nThanks"

        sendEmailWithAttachment(recipients, subject, body, filePath, provider="GMAIL")


    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
