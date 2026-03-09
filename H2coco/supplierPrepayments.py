import sys
import os
import json
import pandas as pd
import requests
from datetime import datetime
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas_gbq
from dotenv import load_dotenv
import pytz

load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from helpers.fetchInvoicesForClient import fetchInvoicesForClient

if not os.path.exists('logs'): os.makedirs('logs')
log_filename = datetime.now().strftime('logs/payment_%Y%m%d_%H%M%S.log')

def export_to_bigquery(paid_po_records):
    key_path = os.getenv("H2COCO_BQACCESS")
    project_id = "h2coco"
    dataset_id = "FinancialData"
    table_id = "SupplierPrepaymentPayments"
    table_ref = f"{project_id}.{dataset_id}.{table_id}"

    # Build DataFrame from list of dicts
    df = pd.DataFrame(paid_po_records)
    df["date"] = pd.to_datetime(df["date"]) 

    # Create BigQuery client
    credentials = service_account.Credentials.from_service_account_file(key_path)
    client = bigquery.Client(credentials=credentials, project=project_id)

    # Load data to BigQuery (APPEND mode)
    job = client.load_table_from_dataframe(
        dataframe=df,
        destination=table_ref,
        job_config=bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND"
        )
    )
    job.result()
    print(f"Uploaded {len(df)} paid PO records to BigQuery.")


def fetch_paid_po_records():
    key_path = os.getenv("H2COCO_BQACCESS")
    project_id = "h2coco"
    dataset_id = "FinancialData"
    table_id = "SupplierPrepaymentPayments"

    client = bigquery.Client.from_service_account_json(key_path)
    query = f"""
        SELECT poNumber
        FROM `{project_id}.{dataset_id}.{table_id}`
        ORDER BY date DESC
    """
    
    df = pandas_gbq.read_gbq(query, project_id=project_id, credentials=client._credentials)
    return df["poNumber"].astype(int).tolist()

    
def write_github_summary(paid, skipped, failed):
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return

    def section(title, rows, headers):
        lines = [f"\n### {title} ({len(rows)})\n"]
        if not rows:
            lines.append("_None._\n")
            return "".join(lines)
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows:
            lines.append("| " + " | ".join(str(c) for c in row) + " |")
        lines.append("")
        return "\n".join(lines)

    with open(summary_file, "a") as f:
        f.write("## H2coco Supplier Prepayment Allocator\n")
        f.write(section(
            "✅ Paid",
            paid,
            ["PO Number", "Supplier Invoice", "Amount (USD)", "Payment Date"],
        ))
        f.write(section(
            "⚠️ Skipped",
            skipped,
            ["PO Number", "Reason"],
        ))
        f.write(section(
            "❌ Failed",
            failed,
            ["PO Number", "Error"],
        ))


def main():
    client = "H2COCO"
    invoiceStatus = "AUTHORISED"

    allInvoices = []
    clientTokens = {}

    try:
        invoices, accessToken, xeroTenantId = fetchInvoicesForClient(client, invoiceStatus)
        if not isinstance(invoices, list):
            raise Exception(f"Expected a list of invoices but got {type(invoices)} for {client}")
        allInvoices.extend(invoices)
        clientTokens[client] = {
            "accessToken": accessToken,
            "xeroTenantId": xeroTenantId
        }
    except Exception as e:
        return

    accpayInvoices = [
        invoice for invoice in allInvoices
        if isinstance(invoice, dict) and invoice.get("Type") == "ACCPAY"
    ]

    # Ask for the file path
    filePath = './PO.xlsx'

    # Read the Excel file to get the PO numbers, dates, currency rates, and amounts
    df = pd.read_excel(filePath)
    poNumbers = df['PO'].tolist()
    dates = df['Date'].dt.strftime('%Y-%m-%d').tolist()  # Convert dates to string format
    currencyRates = df['CurrencyRate'].tolist()
    amounts = df['Amount'].tolist()

    poInvoiceDict = {}
    for poNumber in poNumbers:
        poReference = f"PO-{poNumber}"
        invoiceId = None
        supplierInvNumber = None
        for invoice in accpayInvoices:
            if poReference in invoice.get("InvoiceNumber", ""):
                invoiceId = invoice.get("InvoiceID")
                raw_invoice_number = invoice.get("InvoiceNumber", "")
                supplierInvNumber = ""
                if ' ' in raw_invoice_number:
                    supplierInvNumber = raw_invoice_number.split(' ', 1)[1].strip().rstrip(';')

                break
        poInvoiceDict[poNumber] = {
            "InvoiceID": invoiceId,
            "supplierInvNumber": supplierInvNumber,
            "InvoiceDate": invoice.get("DateString", "").split('T')[0] if invoice.get("DateString", "") else "",
            "AmountPaid": invoice.get("AmountPaid", 0),
            "AmountDue": invoice.get("AmountDue", 0),
        }

    paidPOs = []
    paid_results = []    # (poNumber, supplierInv, amount, paymentDate)
    skipped_results = [] # (poNumber, reason)
    failed_results = []  # (poNumber, reason)

    # Fetch previously paid PO records from BigQuery
    paid_po_records = fetch_paid_po_records()

    # Create and send individual payment requests
    for poNumber, date, currencyRate, amount in zip(poNumbers, dates, currencyRates, amounts):

        invoiceData = poInvoiceDict.get(poNumber)

        # compare the dates to see which one should be used
        invoiceDate = datetime.strptime(invoiceData["InvoiceDate"], "%Y-%m-%d")
        dateObj = datetime.strptime(date, "%Y-%m-%d")
        paymentDate = invoiceDate if dateObj < invoiceDate else dateObj

        if poNumber in paid_po_records:
            skipped_results.append((poNumber, "Already processed (in BigQuery)"))
            continue
        elif invoiceData and invoiceData["supplierInvNumber"] and (invoiceData["AmountPaid"] == 0.0 or invoiceData["AmountDue"] == amount):
            payment = {
                "Invoice": {
                    "InvoiceID": invoiceData["InvoiceID"]
                },
                "Account": {
                    "Code": "2010"
                },
                "Date": paymentDate.strftime("%Y-%m-%d"),
                "CurrencyRate": currencyRate,
                "Amount": amount,
                "Reference": f"PO{poNumber} {invoiceData['supplierInvNumber']} USD {amount}"
            }

            paymentPayload = {
                "Payments": [payment]
            }

            # Send the payment request to the Xero API
            url = "https://api.xero.com/api.xro/2.0/Payments"
            headers = {
                "Authorization": f"Bearer {accessToken}",
                "Content-Type": "application/json",
                "Xero-tenant-id": xeroTenantId
            }

            response = requests.post(url, headers=headers, data=json.dumps(paymentPayload))
            if response.status_code in [200, 201]:
                print(f"Payment for PO {poNumber} ({invoiceData['supplierInvNumber']}) of ${amount} at exchange rate of {currencyRate} allocated on {paymentDate.strftime('%Y-%m-%d')}.")
                paidPOs.append({
                    "poNumber": str(poNumber),
                    "xeroInvNumber": invoiceData["supplierInvNumber"],
                    "date": paymentDate.strftime("%Y-%m-%d"),
                    "usdAmount": amount,
                })
                paid_results.append((poNumber, invoiceData["supplierInvNumber"], f"${amount:,.2f}", paymentDate.strftime("%Y-%m-%d")))
            else:
                try:
                    error_data = response.json()
                    messages = []
                    # Handle Xero Validation Errors
                    if "Elements" in error_data:
                        for element in error_data.get("Elements", []):
                            for error in element.get("ValidationErrors", []):
                                if "Message" in error:
                                    messages.append(error["Message"])

                    if not messages and "Message" in error_data:
                        messages.append(error_data["Message"])

                    if messages:
                        cleaned_text = "; ".join(messages)
                    else:
                        cleaned_text = json.dumps(error_data, indent=2)

                except ValueError:
                    # Truncate likely HTML response
                    text = response.text
                    if len(text) > 300:
                        cleaned_text = f"Non-JSON Response (truncated): {text[:300]}..."
                    else:
                        cleaned_text = f"Non-JSON Response: {text}"

                print(f"Failed to allocate payment for PO {poNumber} ({invoiceData['supplierInvNumber']}): {response.status_code} - {cleaned_text}")
                failed_results.append((poNumber, f"HTTP {response.status_code}: {cleaned_text[:120]}"))
        elif invoiceData and not invoiceData["supplierInvNumber"]:
            print(f"PO {poNumber}'s payment not allocated since supplier invoice number is missing")
            skipped_results.append((poNumber, "Missing supplier invoice number"))
        elif invoiceData["AmountPaid"] > 0:
            print(f"PO {poNumber} has already has a prepayment allocated to it. Please manually check")
            skipped_results.append((poNumber, f"Already paid (AmountPaid: {invoiceData['AmountPaid']})"))
        elif not invoiceData:
            print(f"PO {poNumber} not found in bills")
            skipped_results.append((poNumber, "Not found in Xero bills"))

    # Output the dictionary to a JSON file
    with open("poInvoiceMapping.json", "w") as outfile:
        json.dump(poInvoiceDict, outfile, indent=4)

    if paidPOs:
        export_to_bigquery(paidPOs)

    write_github_summary(paid_results, skipped_results, failed_results)

if __name__ == "__main__":
    main()