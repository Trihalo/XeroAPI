import sys
import os
from datetime import datetime, timedelta
from overdueAnalysis import processOverdueData

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from helpers.emailAttachment import sendEmailWithAttachment
from helpers.fetchInvoicesForClient import fetchInvoicesForClient


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 overdueRequest.py <Recipient Name> <Recipient Email>")
        sys.exit(1)
    recipient_name = sys.argv[1]
    recipient_email = sys.argv[2] 
    
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

        time = (datetime.now() + timedelta(hours=11)).strftime("%d-%m-%Y %I:%M%p").lower()
        subject = f"Overdue Report at {time}"
        body = f"Hi {recipient_name},\n\nPlease find the ATB Report attached.\n\nThanks"

        sendEmailWithAttachment([recipient_email], subject, body, "GMAIL", filePath)


    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
