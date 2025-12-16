import csv
import sys
import os
import requests
import logging
import time
from datetime import datetime

# Add parent directory to path to import helpers
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xeroAuth import XeroTenants
from xeroAuthHelper import getXeroAccessToken

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

def fetch_bill_by_invoice_number(invoice_number, access_token, xero_tenant_id):
    """Fetches a single bill (ACCPAY) by its InvoiceNumber."""
    url = "https://api.xero.com/api.xro/2.0/Invoices"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": xero_tenant_id,
        "Accept": "application/json",
    }
    # Filter by InvoiceNumber and Type=ACCPAY
    where_clause = f'InvoiceNumber=="{invoice_number}" AND Type=="ACCREC"'
    params = {"where": where_clause}
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        invoices = response.json().get("Invoices", [])
        if invoices:
            return invoices[0]
    else:
        logging.error(f"Failed to fetch bill {invoice_number}: {response.status_code} {response.text}")
    
    return None

def update_bill(bill, new_date_str, access_token, xero_tenant_id):
    """Updates the bill's TaxType, Date, and DueDate."""
    url = f"https://api.xero.com/api.xro/2.0/Invoices/{bill['InvoiceID']}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": xero_tenant_id,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Parse the date string (DD/MM/YYYY) to YYYY-MM-DD for Xero API
    try:
        date_obj = datetime.strptime(new_date_str, "%d/%m/%Y")
        xero_date = date_obj.strftime("%Y-%m-%d")
    except ValueError:
        logging.error(f"Invalid date format for {new_date_str}. Expected DD/MM/YYYY.")
        return False

    # Update fields
    # 1. Change TaxType to BASEXCLUDED for all lines
    # 2. Update Date and DueDate
    
    updated_lines = []
    for line in bill.get("LineItems", []):
        # Create a copy of the line item to update
        new_line = {
            "LineItemID": line.get("LineItemID"),
            "Description": line.get("Description"),
            "Quantity": line.get("Quantity"),
            "UnitAmount": line.get("UnitAmount"),
            "AccountCode": line.get("AccountCode"),
            "TaxType": "BASEXCLUDED" # Force TaxType change
        }
        updated_lines.append(new_line)

    payload = {
        "Date": xero_date,
        "DueDate": xero_date,
        "LineItems": updated_lines
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code in [200, 201]:
        logging.info(f"Successfully updated Bill {bill['InvoiceNumber']}")
        return True
    else:
        logging.error(f"Failed to update Bill {bill['InvoiceNumber']}: {response.status_code} {response.text}")
        return False

def main():
    client_name = "FLIGHT_RISK"
    csv_file_path = "bills_to_update.csv"

    if not os.path.exists(csv_file_path):
        logging.error(f"CSV file not found: {csv_file_path}")
        return

    try:
        # Authenticate
        access_token = getXeroAccessToken(client_name)
        xero_tenant_id = XeroTenants(access_token)
        
        if not xero_tenant_id:
            logging.error("Could not retrieve Xero Tenant ID.")
            return

        with open(csv_file_path, mode='r', encoding='utf-8-sig') as csvfile:
            reader = csv.reader(csvfile)
            
            # Skip header if present (simple check)
            header = next(reader, None)
            if header and "Invoice Number" not in header[0]:
                # If header doesn't look like a header, reset pointer (or assume it is a header based on user screenshot)
                # User screenshot shows "Invoice Number", "Xero Inv Date"
                pass 

            for row in reader:
                if len(row) < 2:
                    continue
                
                invoice_number = row[0].strip()
                date_str = row[1].strip()
                
                if not invoice_number or not date_str:
                    continue

                logging.info(f"Processing {invoice_number} with date {date_str}...")
                
                bill = fetch_bill_by_invoice_number(invoice_number, access_token, xero_tenant_id)
                time.sleep(1.1) # Rate limit: Wait after fetch
                
                if bill:
                    update_bill(bill, date_str, access_token, xero_tenant_id)
                    time.sleep(1.1) # Rate limit: Wait after update
                else:
                    logging.warning(f"Bill not found: {invoice_number}")

    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
