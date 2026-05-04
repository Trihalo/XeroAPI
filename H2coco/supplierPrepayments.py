import sys
import os
import re
import json
import pandas as pd
import requests
from datetime import datetime
from google.cloud import bigquery
from google.oauth2 import service_account
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from helpers.fetchInvoicesForClient import fetchInvoicesForClient

if not os.path.exists('logs'): os.makedirs('logs')
log_filename = datetime.now().strftime('logs/payment_%Y%m%d_%H%M%S.log')

SP_TABLE = "h2dataservices.finance.supplierPrepayments"


def read_env_json(var_name):
    """Read a (potentially multiline) JSON value from the nearest .env file."""
    d = os.path.dirname(os.path.abspath(__file__))
    env_path = None
    for _ in range(4):
        candidate = os.path.join(d, ".env")
        if os.path.exists(candidate):
            env_path = candidate
            break
        d = os.path.dirname(d)

    if env_path:
        with open(env_path) as f:
            content = f.read()
        match = re.search(rf'^{var_name}=(.*)', content, re.MULTILINE)
        if match:
            start = match.start(1)
            fragment = content[start:]
            if fragment.strip().startswith("{"):
                depth = end = 0
                for i, ch in enumerate(fragment):
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                return fragment[:end]
            return fragment.split("\n")[0].strip()

    return os.getenv(var_name)


def get_bq_client():
    val = read_env_json("H2DATASERVICES_BQACCESS").strip().strip('"').strip("'")
    if val.startswith("{"):
        credentials = service_account.Credentials.from_service_account_info(json.loads(val))
    else:
        credentials = service_account.Credentials.from_service_account_file(val)
    return bigquery.Client(credentials=credentials, project="h2dataservices")


def fetch_pending_pos(client):
    query = f"""
        SELECT poNumber, date, currencyRate, usdAmount
        FROM `{SP_TABLE}`
        WHERE parseStatus = 'OK'
          AND transactionType = 'SPEND'
          AND allocatedDate IS NULL
          AND poNumber IS NOT NULL
        ORDER BY date ASC
    """
    rows = list(client.query(query).result())
    return (
        [int(r.poNumber) for r in rows],
        [r.date.strftime("%Y-%m-%d") for r in rows],
        [r.currencyRate for r in rows],
        [r.usdAmount for r in rows],
    )


def mark_po_allocated(client, po_number, allocated_date):
    query = f"""
        UPDATE `{SP_TABLE}`
        SET allocatedDate = '{allocated_date}'
        WHERE poNumber = '{po_number}'
          AND allocatedDate IS NULL
    """
    client.query(query).result()


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


def create_xero_overpayment(access_token, tenant_id, contact_id, date_str, currency_rate, overpayment_usd, po_number):
    url = "https://api.xero.com/api.xro/2.0/Overpayments"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Xero-tenant-id": tenant_id,
    }
    payload = {
        "Overpayments": [{
            "Type": "SPEND-OVERPAYMENT",
            "Contact": {"ContactID": contact_id},
            "Date": date_str,
            "CurrencyCode": "USD",
            "CurrencyRate": currency_rate,
            "LineAmountTypes": "EXCLUSIVE",
            "LineItems": [{
                "Description": f"Overpayment PO{po_number} USD {overpayment_usd:.2f}",
                "UnitAmount": overpayment_usd,
            }]
        }]
    }
    return requests.post(url, headers=headers, data=json.dumps(payload))


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

    bq_client = get_bq_client()
    poNumbers, dates, currencyRates, amounts = fetch_pending_pos(bq_client)

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
            "ContactID": invoice.get("Contact", {}).get("ContactID") if invoiceId else None,
            "supplierInvNumber": supplierInvNumber,
            "InvoiceDate": invoice.get("DateString", "").split('T')[0] if invoice.get("DateString", "") else "",
            "AmountPaid": invoice.get("AmountPaid", 0),
            "AmountDue": invoice.get("AmountDue", 0),
        }

    paidPOs = []
    paid_results = []    # (poNumber, supplierInv, amount, paymentDate)
    skipped_results = [] # (poNumber, reason)
    failed_results = []  # (poNumber, reason)

    # Create and send individual payment requests
    for poNumber, date, currencyRate, amount in zip(poNumbers, dates, currencyRates, amounts):

        invoiceData = poInvoiceDict.get(poNumber)

        # compare the dates to see which one should be used
        invoiceDate = datetime.strptime(invoiceData["InvoiceDate"], "%Y-%m-%d")
        dateObj = datetime.strptime(date, "%Y-%m-%d")
        paymentDate = invoiceDate if dateObj < invoiceDate else dateObj

        if invoiceData and invoiceData["supplierInvNumber"] and invoiceData["AmountPaid"] == 0.0:
            invoice_due = invoiceData["AmountDue"]
            overpayment_usd = round(amount - invoice_due, 2) if amount > invoice_due else 0.0
            pay_amount = invoice_due if overpayment_usd > 0 else amount

            payment = {
                "Invoice": {
                    "InvoiceID": invoiceData["InvoiceID"]
                },
                "Account": {
                    "Code": "2010"
                },
                "Date": paymentDate.strftime("%Y-%m-%d"),
                "CurrencyRate": currencyRate,
                "Amount": pay_amount,
                "Reference": f"PO{poNumber} {invoiceData['supplierInvNumber']} USD {pay_amount}"
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
                allocated_date_str = paymentDate.strftime("%Y-%m-%d")
                if overpayment_usd > 0:
                    print(f"Payment for PO {poNumber} ({invoiceData['supplierInvNumber']}) of ${pay_amount} allocated on {allocated_date_str}. Creating overpayment of ${overpayment_usd:.2f}.")
                    op_response = create_xero_overpayment(
                        accessToken, xeroTenantId,
                        invoiceData["ContactID"],
                        allocated_date_str,
                        currencyRate,
                        overpayment_usd,
                        poNumber,
                    )
                    if op_response.status_code in [200, 201]:
                        print(f"  Overpayment of ${overpayment_usd:.2f} USD created for PO {poNumber}.")
                    else:
                        print(f"  Overpayment creation failed: {op_response.status_code} - {op_response.text[:200]}")
                else:
                    print(f"Payment for PO {poNumber} ({invoiceData['supplierInvNumber']}) of ${pay_amount} at exchange rate of {currencyRate} allocated on {allocated_date_str}.")
                paidPOs.append({
                    "poNumber": str(poNumber),
                    "xeroInvNumber": invoiceData["supplierInvNumber"],
                    "date": allocated_date_str,
                    "usdAmount": amount,
                })
                mark_po_allocated(bq_client, str(poNumber), allocated_date_str)
                paid_results.append((poNumber, invoiceData["supplierInvNumber"], f"${amount:,.2f}", allocated_date_str))
            else:
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

                    if messages:
                        cleaned_text = "; ".join(messages)
                    else:
                        cleaned_text = json.dumps(error_data, indent=2)

                except ValueError:
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