import sys
import os
import requests
import json
import logging
import csv
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from helpers.fetchInvoicesForClient import fetchInvoicesForClient

def log_payment_to_csv(invoice_number, invoice_date, amount_paid, payment_date):
    file_path = os.path.join(os.path.dirname(__file__), "payment_allocations.csv")
    file_exists = os.path.isfile(file_path)
    
    with open(file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["InvoiceNumber", "InvoiceDate", "AmountPaid", "PaymentDate"])
        
        writer.writerow([invoice_number, invoice_date, amount_paid, payment_date])


def main():
    client = "FLIGHT_RISK"
    invoiceStatus = "AUTHORISED" # We need authorised invoices to make payments on them
    
    print(f"Fetching invoices for {client}...")
    try:
        invoices, accessToken, xeroTenantId = fetchInvoicesForClient(client, invoiceStatus)
    except Exception as e:
        logging.error(f"Error fetching data: {e}")
        return

    cutoff_date = datetime(2025, 7, 1)

    # Filter for ACCREC invoices that start with FRC# and have an amount due
    # Also filter for Date strictly before 2025-07-01
    target_invoices = []
    for inv in invoices:
        if not (isinstance(inv, dict) and inv.get("Type") == "ACCREC"):
            continue
        
        if not inv.get("InvoiceNumber", "").startswith("FRC#"):
            continue
            
        if inv.get("AmountDue", 0) <= 0:
            continue
            
        date_str = inv.get("DateString", "")
        if not date_str:
            continue
            
        # Parse invoice date
        try:
            # DateString format example: '2023-10-27T00:00:00'
            inv_date = datetime.strptime(date_str.split("T")[0], "%Y-%m-%d")
        except ValueError:
            logging.warning(f"Could not parse date for {inv.get('InvoiceNumber')}: {date_str}")
            continue

        if inv_date < cutoff_date:
            target_invoices.append(inv)

    if not target_invoices:
        print("No pending FRC# invoices found.")
        return

    print(f"Found {len(target_invoices)} pending FRC# invoices.")

    headers = {
        "Authorization": f"Bearer {accessToken}",
        "Xero-tenant-id": xeroTenantId,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    url = "https://api.xero.com/api.xro/2.0/Payments"

    for inv in target_invoices:
        invoice_number = inv.get("InvoiceNumber")
        amount_due = inv.get("AmountDue")
        invoice_id = inv.get("InvoiceID")
        
        # Payment date is equal to Issue date
        # DateString is usually in format like '2023-10-27T00:00:00'
        date_string = inv.get("DateString", "")
        if date_string:
            payment_date = date_string.split("T")[0]
        else:
            # Fallback if DateString is missing, though unlikely for Authorised invoice
            print(f"Skipping {invoice_number}: Missing DateString")
            continue

        print(f"\nProcessing {invoice_number}...")
        print(f"  Amount Due: {amount_due}")
        print(f"  Payment Date: {payment_date}")
        
        payment_payload = {
            "Payments": [
                {
                    "Invoice": {
                        "InvoiceID": invoice_id
                    },
                    "Account": {
                        "Code": "4002"
                    },
                    "Date": payment_date,
                    "Amount": amount_due,
                    "Reference": "" 
                }
            ]
        }

        try:
            response = requests.put(url, headers=headers, json=payment_payload)
            
            if response.status_code in [200, 201]:
                print(f"  [SUCCESS] Payment allocated for {invoice_number}")
                log_payment_to_csv(invoice_number, payment_date, amount_due, payment_date)
            else:
                print(f"  [FAILED] Could not allocate payment: {response.status_code}")
                print(f"  Response: {response.text}")
        except Exception as e:
             print(f"  [ERROR] Exception occurred: {e}")

if __name__ == "__main__":
    main()
