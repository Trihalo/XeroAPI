import sys
import os
from datetime import datetime, timedelta
from overdueAnalysis import processOverdueData
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from helpers.emailAttachment import sendEmailWithAttachment
from helpers.fetchInvoicesForClient import fetchInvoicesForClient


def main():
    client = "FUTUREYOU_RECRUITMENT_PERTH"
    invoiceStatus = "AUTHORISED"

    clientTokens = {}

    try:
        invoices, accessToken, xeroTenantId = fetchInvoicesForClient(client, invoiceStatus)
        
        if not isinstance(invoices, list):
            raise Exception(f"Expected a list of invoices but got {type(invoices)} for {client}")
        
        clientTokens[client] = {
            "access_token": accessToken,
            "xero_tenant_id": xeroTenantId
        }

    except Exception as e:
        print(f"Error: {e}")

    expenseClaims = []
    
    for invoice in invoices:
        if invoice["Type"] == "ACCPAY" and invoice["InvoiceNumber"] == "Expense Claims":
            expenseClaims.append(invoice)
            print(f"Found an expense claim for {invoice['Reference']}")
            


    payload = {
        "Invoices": [
            {
                "InvoiceID": "2f668323-79f4-41ad-bd16-e30a50b2cb57", # get
                "LineItems": [
                    {
                    "Description": "Test Expense claim",
                    "UnitAmount": 69.69,
                    "TaxType": "INPUT",
                    "TaxAmount": 6.34,
                    "LineAmount": 69.69,
                    "AccountCode": "367",
                    "Tracking": [
                        {
                        "Name": "Category",
                        "Option": "Perth"
                        },
                        {
                        "Name": "Consultant",
                        "Option": "PEK002 Tapiwa Utete"
                        }
                    ],
                    "Quantity": 1.0,
                    "LineItemID": "64cc563a-3150-404e-a148-68e1652b3c11", # get 
                    "AccountID": "b7522d40-69c4-49d4-9b5d-1393d7fe93ee"
                    }
                ]
            }
        ]
    }
    
    print(json.dumps(invoices, indent=4))

if __name__ == "__main__":
    main()
