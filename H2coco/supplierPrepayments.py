import sys
import os
import json
import pandas as pd
import requests
from datetime import datetime
from google.cloud import bigquery
from google.oauth2 import service_account
import xml.etree.ElementTree as ET
import pandas_gbq
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from helpers.fetchInvoicesForClient import fetchInvoicesForClient


XERO_PAYMENTS_URL = "https://api.xero.com/api.xro/2.0/Payments"
PAYMENT_ACCOUNT_CODE = "2010"  # Supplier Prepayments


def export_to_bigquery(paid_po_records):
    key_path = os.getenv("H2COCO_BQACCESS")
    project_id = "h2coco"
    dataset_id = "FinancialData"
    table_id = "SupplierPrepaymentPayments"
    table_ref = f"{project_id}.{dataset_id}.{table_id}"

    df = pd.DataFrame(paid_po_records)
    df["date"] = pd.to_datetime(df["date"])

    credentials = service_account.Credentials.from_service_account_file(key_path)
    client = bigquery.Client(credentials=credentials, project=project_id)

    job = client.load_table_from_dataframe(
        dataframe=df,
        destination=table_ref,
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND")
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
        f.write(section("✅ Paid", paid, ["PO Number", "Supplier Invoice", "Amount (USD)", "Payment Date"]))
        f.write(section("⚠️ Skipped", skipped, ["PO Number", "Reason"]))
        f.write(section("❌ Failed", failed, ["PO Number", "Error"]))


def parse_xero_error(response):
    try:
        error_data = response.json()
        messages = []
        if "Elements" in error_data:
            for element in error_data.get("Elements", []):
                for error in element.get("ValidationErrors", []):
                    if "Message" in error:
                        messages.append(error["Message"])
        if not messages and "Message" in error_data:
            messages.append(error_data["Message"])
        return "; ".join(messages) if messages else json.dumps(error_data, indent=2)
    except ValueError:
        try:
            root = ET.fromstring(response.text)
            messages = [el.text for el in root.findall(".//Message") if el.text]
            if messages:
                return "; ".join(messages)
        except ET.ParseError:
            pass
        return response.text


def post_payment(invoice_id, amount, payment_date, currency_rate, reference, access_token, xero_tenant_id):
    payload = {
        "Payments": [{
            "Invoice": {"InvoiceID": invoice_id},
            "Account": {"Code": PAYMENT_ACCOUNT_CODE},
            "Date": payment_date.strftime("%Y-%m-%d"),
            "CurrencyRate": currency_rate,
            "Amount": amount,
            "Reference": reference
        }]
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Xero-tenant-id": xero_tenant_id
    }
    return requests.post(XERO_PAYMENTS_URL, headers=headers, data=json.dumps(payload))


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
    except Exception:
        return

    accpayInvoices = [
        invoice for invoice in allInvoices
        if isinstance(invoice, dict) and invoice.get("Type") == "ACCPAY"
    ]

    filePath = './PO.xlsx'

    df = pd.read_excel(filePath)
    poNumbers = df['PO'].tolist()
    dates = df['Date'].dt.strftime('%Y-%m-%d').tolist()
    currencyRates = df['CurrencyRate'].tolist()
    amounts = df['Amount'].tolist()

    poInvoiceDict = {}
    for poNumber in poNumbers:
        poReference = f"PO-{poNumber}"
        matchedInvoice = None
        supplierInvNumber = None
        for invoice in accpayInvoices:
            if poReference in invoice.get("InvoiceNumber", ""):
                matchedInvoice = invoice
                raw_invoice_number = invoice.get("InvoiceNumber", "")
                supplierInvNumber = ""
                if ' ' in raw_invoice_number:
                    supplierInvNumber = raw_invoice_number.split(' ', 1)[1].strip().rstrip(';')
                break

        if matchedInvoice is None:
            poInvoiceDict[poNumber] = {
                "InvoiceID": None,
                "supplierInvNumber": None,
                "InvoiceDate": "",
                "AmountPaid": 0,
                "AmountDue": 0,
            }
        else:
            poInvoiceDict[poNumber] = {
                "InvoiceID": matchedInvoice.get("InvoiceID"),
                "supplierInvNumber": supplierInvNumber,
                "InvoiceDate": matchedInvoice.get("DateString", "").split('T')[0] if matchedInvoice.get("DateString") else "",
                "AmountPaid": matchedInvoice.get("AmountPaid", 0),
                "AmountDue": matchedInvoice.get("AmountDue", 0),
            }

    paidPOs = []
    paid_results = []    # (poNumber, supplierInv, amount, paymentDate)
    skipped_results = [] # (poNumber, reason)
    failed_results = []  # (poNumber, error)

    paid_po_records = fetch_paid_po_records()

    for poNumber, date, currencyRate, amount in zip(poNumbers, dates, currencyRates, amounts):

        invoiceData = poInvoiceDict.get(poNumber)

        if poNumber in paid_po_records:
            skipped_results.append((poNumber, "Already processed (in BigQuery)"))
            continue

        if not invoiceData or invoiceData["InvoiceID"] is None:
            print(f"PO {poNumber} not found in bills")
            skipped_results.append((poNumber, "Not found in Xero bills"))
            continue

        invoiceDate = datetime.strptime(invoiceData["InvoiceDate"], "%Y-%m-%d")
        dateObj = datetime.strptime(date, "%Y-%m-%d")
        paymentDate = invoiceDate if dateObj < invoiceDate else dateObj

        supplierInvNumber = invoiceData["supplierInvNumber"] or "[MISSING-INV-NO]"
        amountDue = invoiceData["AmountDue"]
        amountPaid = invoiceData["AmountPaid"]
        reference = f"PO{poNumber} {supplierInvNumber} USD {amount}"

        if amountPaid == 0.0 or amount <= amountDue:
            response = post_payment(invoiceData["InvoiceID"], amount, paymentDate, currencyRate, reference, accessToken, xeroTenantId)
            if response.status_code in [200, 201]:
                print(f"Payment for PO {poNumber} ({supplierInvNumber}) of ${amount} at exchange rate of {currencyRate} allocated on {paymentDate.strftime('%Y-%m-%d')}.")
                paidPOs.append({"poNumber": str(poNumber), "xeroInvNumber": supplierInvNumber, "date": paymentDate.strftime("%Y-%m-%d"), "usdAmount": amount})
                paid_results.append((poNumber, supplierInvNumber, f"${amount:,.2f}", paymentDate.strftime("%Y-%m-%d")))
            else:
                cleaned_text = parse_xero_error(response)
                print(f"Failed to allocate payment for PO {poNumber} ({supplierInvNumber}): {response.status_code} - {cleaned_text}")
                failed_results.append((poNumber, f"HTTP {response.status_code}: {cleaned_text[:120]}"))

        else:
            # amount > amountDue with prior partial payment — overpayment required, must be handled manually
            overpayment_amount = round(amount - amountDue, 2)
            print(f"PO {poNumber} requires overpayment of ${overpayment_amount} — please process manually in Xero")
            skipped_results.append((poNumber, f"Overpayment of ${overpayment_amount:,.2f} required — process manually"))

    with open("poInvoiceMapping.json", "w") as outfile:
        json.dump(poInvoiceDict, outfile, indent=4)

    if paidPOs:
        export_to_bigquery(paidPOs)

    write_github_summary(paid_results, skipped_results, failed_results)

if __name__ == "__main__":
    main()
