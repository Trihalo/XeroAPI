import os
import sys
import pandas as pd
from datetime import datetime, date
import requests
import time
import logging
from google.cloud import bigquery
from google.oauth2 import service_account

logging.basicConfig(level=logging.INFO)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from helpers.dateStringsHelper import getSydneyDate

# --- Helper functions ---
def getCategory(invoice):
    if "LineItems" in invoice and isinstance(invoice["LineItems"], list):
        for line_item in invoice["LineItems"]:
            if "Tracking" in line_item and isinstance(line_item["Tracking"], list):
                for tracking_item in line_item["Tracking"]:
                    if tracking_item.get("Name") == "Category": return tracking_item.get("Option")
    return None

# --- Get Notes ---
def fetchInvoiceHistory(invoice_id, access_token, xero_tenant_id):
    XERO_HISTORY_API_URL = "https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}/History"

    if not access_token or not xero_tenant_id:
        raise Exception("Missing Xero authentication credentials.")
    url = XERO_HISTORY_API_URL.format(invoice_id=invoice_id)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Xero-Tenant-Id": xero_tenant_id
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200: return response.json()
    elif response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 5))  
        print(f"⚠️ Rate limit hit! Retrying in {retry_after} seconds for invoice {invoice_id}...")
        time.sleep(retry_after)
        return fetchInvoiceHistory(invoice_id, access_token, xero_tenant_id) 
    else:
        print(f"❌ Error fetching invoice history: {invoice_id}: {response.status_code} - {response.text}")
        return None

def getNotes(invoice_id, invoice_number, client_tokens):
    # Determine which credentials to use
    if invoice_number.startswith("TC"): client_key = "FUTUREYOU_CONTRACTING"
    else: client_key = "FUTUREYOU_RECRUITMENT"

    if client_key not in client_tokens:
        raise Exception(f"❌ No credentials found for {client_key}")

    access_token = client_tokens[client_key]["access_token"]
    xero_tenant_id = client_tokens[client_key]["xero_tenant_id"]

    notes = []
    history = fetchInvoiceHistory(invoice_id, access_token, xero_tenant_id)

    if history:
        history_records = history.get("HistoryRecords", [])
        for record in history_records:
            if record.get("Changes") == "Note":
                details = record.get("Details", "").strip()
                date_string = record.get("DateUTCString", "")
                # Convert date string to DD/M format
                try:
                    note_date = getSydneyDate(date_string)
                    formatted_date = note_date.strftime("%d/%m")
                except ValueError:
                    formatted_date = "Unknown Date"
                note_entry = f"{formatted_date}: {details}"
                if note_entry not in notes: notes.append(note_entry)

    print(f"✅ Notes fetched for invoice {invoice_number}")
    time.sleep(1)  # Enforce rate limit (1 request per second)
    return ", ".join(notes) if notes else ""

# --- Process Data ---
def getAtbData(data, client_tokens):     
    accrec_invoices = [
        invoice for invoice in data.get("Invoices", [])
        if isinstance(invoice, dict) and invoice.get("Type") == "ACCREC"
    ]
    invoice_rows = []

    for index, invoice in enumerate(accrec_invoices, start=1):
        invoice_id = invoice.get("InvoiceID", "")
        invoice_number = invoice.get("InvoiceNumber", "")
        invoice_date = datetime.strptime(invoice["DateString"], "%Y-%m-%dT%H:%M:%S")
        due_date = datetime.strptime(invoice["DueDateString"], "%Y-%m-%dT%H:%M:%S")
        formatted_invoice_date = invoice_date.date()
        formatted_due_date = due_date.date()
        reference = invoice.get("Reference", "")
        
        # Classification
        type_column = ""
        if "Retainer Commencement" in reference: 
            type_column = "Commencement Retainer"
        if (date.today() - invoice_date.date()).days > 90: 
            type_column = "Invoices 90 days plus"

        amount_due = float(invoice.get("AmountDue", 0.0))
        currency_rate = float(invoice.get("CurrencyRate", 1.0))
        currency_code = invoice.get("CurrencyCode", "AUD")

        # Convert to AUD if needed
        if currency_code != "AUD" and currency_rate != 0:
            amount_due *= (1 / currency_rate)

        comments = getNotes(invoice_id, invoice_number, client_tokens)
        contact = invoice.get("Contact", {}).get("Name", "")
        category = getCategory(invoice)

        line_items = invoice.get("LineItems", [])
        total_quantity = sum(float(line.get("Quantity", 0)) for line in line_items if line.get("Quantity"))

        for line in line_items:
            quantity = float(line.get("Quantity", 0))
            if quantity == 0: continue
            consultant_name = "No Consultant"
            if "Tracking" in line and isinstance(line["Tracking"], list):
                for tracking_item in line["Tracking"]:
                    if tracking_item.get("Name") == "Consultant":
                        consultant_name = tracking_item.get("Option")
                        break
            if not consultant_name: continue
            proportional_total = amount_due * (quantity / total_quantity)
            invoice_rows.append({
                "InvoiceNumber": invoice_number,
                "Type": type_column,
                "Contact": contact,
                "InvoiceDate": formatted_invoice_date,
                "DueDate": formatted_due_date,
                "Reference": reference,
                "Total": proportional_total,
                "Category": category,
                "Consultant": consultant_name,
                "Comments": comments,
            })
        logging.info(f"✅ Processed invoice {index}/{len(accrec_invoices)} - {invoice_number}")
    return invoice_rows

def writeGithubSummary(df, table_ref):
    today = date.today()
    run_number = os.environ.get("GITHUB_RUN_NUMBER", "?")

    lines = [f"## FutureYou ATB — Run #{run_number}", ""]

    total_amount = df["Total"].sum()
    lines += [
        "### Overview",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Rows Uploaded | {len(df)} |",
        f"| Total Outstanding | ${total_amount:,.2f} |",
        f"| Table | {table_ref} |",
        "",
    ]

    def age_bucket(invoice_date):
        days = (today - invoice_date).days
        if days <= 30: return "0–30 days"
        elif days <= 60: return "31–60 days"
        elif days <= 90: return "61–90 days"
        elif days <= 120: return "91–120 days"
        else: return "> 120 days"

    bucket_order = ["0–30 days", "31–60 days", "61–90 days", "91–120 days", "> 120 days"]
    df2 = df.copy()
    df2["AgeBucket"] = df2["InvoiceDate"].apply(age_bucket)
    aged = df2.groupby("AgeBucket")["Total"].sum()

    lines += ["### Aged Receivables", "| Period | Amount |", "| --- | --- |"]
    for b in bucket_order:
        lines.append(f"| {b} | ${aged.get(b, 0):,.2f} |")
    lines.append("")

    type_summary = df2.groupby("Type").agg(Rows=("Total", "count"), Amount=("Total", "sum"))
    lines += ["### By Type", "| Type | Rows | Amount |", "| --- | --- | --- |"]
    for t, row in type_summary.iterrows():
        lines.append(f"| {t or '—'} | {int(row['Rows'])} | ${row['Amount']:,.2f} |")
    lines += ["", f"_Generated {today.strftime('%d %b %Y')}_"]

    summary = "\n".join(lines)
    print(summary)
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        with open(gh_summary, "a") as f:
            f.write(summary + "\n")


def processAtbData(data, client_tokens):
    invoices = getAtbData(data, client_tokens)

    # Convert to DataFrame
    df = pd.DataFrame(invoices)

    # Set up BigQuery configuration
    key_path = os.getenv("FUTUREYOU_BQACCESS")
    project_id = "futureyou-458212"
    dataset_id = "InvoiceData"
    table_id = "ATBEnquiry"
    table_ref = f"{project_id}.{dataset_id}.{table_id}"

    # Authenticate using service account
    credentials = service_account.Credentials.from_service_account_file(key_path)
    client = bigquery.Client(credentials=credentials, project=project_id)

    # 🧹 Clear existing contents without dropping the table
    clear_query = f"DELETE FROM `{table_ref}` WHERE TRUE"
    client.query(clear_query).result()
    print(f"🧹 Cleared existing rows in {table_ref}")

    # Upload the data
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True,
    )

    load_job = client.load_table_from_dataframe(
        df, table_ref, job_config=job_config
    )
    load_job.result()  # Wait for the job to complete

    print(f"📊 Successfully uploaded {len(df)} rows to BigQuery table {table_ref}")
    writeGithubSummary(df, table_ref)
    return table_ref


# # --- Testing Purposes ---
# def processAtbData(data, client_tokens):
#     invoices = getAtbData(data, client_tokens)

#     # Convert to DataFrame
#     df = pd.DataFrame(invoices)

#     # Define the output Excel path
#     output_file = "ATB_Test_Export.xlsx"

#     # Export to Excel
#     df.to_excel(output_file, index=False)
#     print(f"📁 Exported {len(df)} rows to Excel file: {output_file}")
#     return output_file
    

