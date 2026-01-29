import sys
import os
import requests
import json
import logging
import csv
import argparse
import time
import pandas as pd
from datetime import datetime

# Add parent directory to path to import helpers
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from helpers.fetchInvoicesForClient import fetchInvoicesForClient

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_payment_to_csv(invoice_number, invoice_date, amount_paid, payment_date, dry_run=False):
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    filename = "payment_allocations_dry_run.csv" if dry_run else "payment_allocations.csv"
    file_path = os.path.join(log_dir, filename)
    file_exists = os.path.isfile(file_path)
    
    with open(file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["InvoiceNumber", "InvoiceDate", "AmountPaid", "PaymentDate", "Status"])
        
        status = "DRY_RUN" if dry_run else "ALLOCATED"
        writer.writerow([invoice_number, invoice_date, amount_paid, payment_date, status])

def main():
    parser = argparse.ArgumentParser(description="Allocate customer prepayments to invoices.")
    parser.add_argument("--dry-run", action="store_true", help="Run without making actual API calls")
    parser.add_argument("--limit", type=int, help="Limit the number of rows to process", default=None)
    args = parser.parse_args()

    dry_run = args.dry_run
    limit = args.limit
    if dry_run:
        logging.info("RUNNING IN DRY-RUN MODE. No payments will be allocated.")

    # 1. Load Excel File
    excel_path = os.path.join(os.path.dirname(__file__), "CustomerPrepayment.xlsx")
    if not os.path.exists(excel_path):
        logging.error(f"Excel file not found at {excel_path}")
        return

    logging.info(f"Reading Excel file from {excel_path}...")
    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        logging.error(f"Failed to read Excel file: {e}")
        return

    # Normalize column names slightly for safety (strip matching)
    df.columns = [c.strip() for c in df.columns]
    
    # Check required columns
    required_cols = ['Sales Order Number', 'Prepayment $']
    for col in required_cols:
        if col not in df.columns:
            logging.error(f"Missing required column '{col}'. Found: {df.columns.tolist()}")
            return

    # 2. Fetch Invoices from Xero
    client = "FLIGHT_RISK"
    invoiceStatus = "AUTHORISED"
    logging.info(f"Fetching {invoiceStatus} invoices for {client}...")
    
    try:
        # fetchInvoicesForClient returns (invoices, accessToken, xeroTenantId)
        invoices_list, accessToken, xeroTenantId = fetchInvoicesForClient(client, invoiceStatus)
    except Exception as e:
        logging.error(f"Error fetching invoices: {e}")
        return

    # Index invoices by InvoiceNumber for fast lookup
    # Only care about ACCREC and invoices that start with FRC# (though user said search "Sales Order Number" from excel)
    # The Excel "Sales Order Number" seems to match the Invoice Number format "FRC#..."
    invoices_map = {}
    for inv in invoices_list:
        if inv.get("Type") == "ACCREC":
            inv_num = inv.get("InvoiceNumber")
            if inv_num:
                invoices_map[inv_num] = inv

    logging.info(f"Fetched {len(invoices_map)} active ACCREC invoices.")

    # 3. Process Excel Rows
    headers = {
        "Authorization": f"Bearer {accessToken}",
        "Xero-tenant-id": xeroTenantId,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Prepayment Account Code - Updated to 2010
    PREPAYMENT_ACCOUNT_CODE = "2010" 
    
    payment_url = "https://api.xero.com/api.xro/2.0/Payments"
    
    rows_to_process = df.iloc[:limit] if limit else df

    for index, row in rows_to_process.iterrows():
        sales_order_num = str(row['Sales Order Number']).strip()
        
        # Check if 'Prepayment $' is valid
        try:
            prepayment_amount = float(row['Prepayment $'])
        except (ValueError, TypeError):
            logging.warning(f"Row {index+2}: Invalid Prepayment Amount '{row['Prepayment $']}'. Skipping.")
            continue

        if prepayment_amount <= 0:
            logging.info(f"Row {index+2}: Prepayment amount is {prepayment_amount}. Skipping.")
            continue

        # Lookup Invoice
        invoice = invoices_map.get(sales_order_num)
        
        if not invoice:
            logging.info(f"Row {index+2}: Invoice {sales_order_num} not found or not AUTHORISED. Skipping.")
            continue

        amount_due = float(invoice.get("AmountDue", 0))
        amount_paid = float(invoice.get("AmountPaid", 0))
        invoice_id = invoice.get("InvoiceID")
        
        # Validation Logic
        if amount_paid > 0:
            logging.info(f"Row {index+2}: Invoice {sales_order_num} already has payments allocated (AmountPaid: {amount_paid}). Skipping.")
            continue

        if amount_due <= 0:
            logging.info(f"Row {index+2}: Invoice {sales_order_num} is fully paid (AmountDue: {amount_due}). Skipping.")
            continue

        if prepayment_amount > amount_due:
            logging.warning(f"Row {index+2}: Invoice {sales_order_num} - Prepayment ({prepayment_amount}) > Amount Due ({amount_due}). DONT allocate rule. Skipping.")
            continue
        
        # Payment Date = Invoice Date
        date_str = invoice.get("DateString", "")
        if not date_str:
            logging.warning(f"Row {index+2}: Invoice {sales_order_num} has no DateString. Skipping.")
            continue
            
        try:
            # DateString format example: '2023-10-27T00:00:00'
            payment_date = date_str.split("T")[0]
        except Exception:
            logging.warning(f"Row {index+2}: Could not parse DateString '{date_str}'. Skipping.")
            continue

        # Allocation Logic
        logging.info(f"Row {index+2}: Allocating {prepayment_amount} to {sales_order_num}. Payment Date: {payment_date}")
        
        if dry_run:
            log_payment_to_csv(sales_order_num, payment_date, prepayment_amount, payment_date, dry_run=True)
            continue

        # Prepare Payment Payload
        payment_payload = {
            "Payments": [
                {
                    "Invoice": {
                        "InvoiceID": invoice_id
                    },
                    "Account": {
                        "Code": PREPAYMENT_ACCOUNT_CODE
                    },
                    "Date": payment_date,
                    "Amount": prepayment_amount,
                    "Reference": f"{sales_order_num} {payment_date}"
                }
            ]
        }

        try:
            response = requests.put(payment_url, headers=headers, json=payment_payload)
            
            if response.status_code in [200, 201]:
                logging.info(f"  [SUCCESS] Payment allocated for {sales_order_num}")
                log_payment_to_csv(sales_order_num, payment_date, prepayment_amount, payment_date)
            else:
                logging.error(f"  [FAILED] Could not allocate payment for {sales_order_num}. Status: {response.status_code}")
                logging.error(f"  Response: {response.text}")
        except Exception as e:
             logging.error(f"  [ERROR] Exception occurred for {sales_order_num}: {e}")

        # Rate Limiting
        time.sleep(1.1)

    logging.info("Processing complete.")

if __name__ == "__main__":
    main()
