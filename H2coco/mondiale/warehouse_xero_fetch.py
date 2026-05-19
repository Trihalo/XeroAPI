import sys
import os
import time
import tempfile
import requests
import pandas as pd
from collections import deque
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from xeroAuth import XeroTenants
from xeroAuthHelper import getXeroAccessToken, get_github_variable, update_github_variable
from warehouse_to_csv import parse_invoice
from warehouse_bq import upsert_to_bigquery

DISTRIBUTION_LAST_UPDATED_VAR = "DISTRIBUTION_LAST_UPDATED"

RATE_LIMIT = 60  # Xero allows 60 calls per minute
_call_times: deque = deque()


def xero_get(url, headers, params=None):
    """Xero GET with sliding-window rate limiting (60 calls/min)."""
    now = time.monotonic()
    while _call_times and now - _call_times[0] >= 60:
        _call_times.popleft()
    if len(_call_times) >= RATE_LIMIT:
        wait = 60 - (now - _call_times[0]) + 0.1
        print(f"  [rate limit] sleeping {wait:.1f}s...")
        time.sleep(wait)
        now = time.monotonic()
        while _call_times and now - _call_times[0] >= 60:
            _call_times.popleft()
    _call_times.append(time.monotonic())
    return requests.get(url, headers=headers, params=params)


CONTACT_ID = "fbb4e42b-ede0-4c86-93fe-b8d258a0ce38"  # Mondiale Warehouse
FY26_START = "2025-07-01"
PAGE_SIZE  = 100
CSV_PATH   = os.path.join(os.path.dirname(__file__), "warehouse_invoices_combined.csv")


def fetch_bills(access_token, tenant_id, modified_since=None):
    """Fetch ACCPAY bills for the warehouse contact, optionally filtered by modification date."""
    url     = "https://api.xero.com/api.xro/2.0/Invoices"
    headers = {
        "Authorization":  f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept":         "application/json",
    }
    if modified_since:
        headers["If-Modified-Since"] = modified_since
        print(f"  Using If-Modified-Since: {modified_since}")

    base_params = {
        "Type":     "ACCPAY",
        "Statuses": "AUTHORISED,PAID",
        "where": (
            f'Contact.ContactID=Guid("{CONTACT_ID}")'
            f' AND Date >= DateTime({FY26_START.replace("-", ",")})'
        ),
        "pageSize": PAGE_SIZE,
    }

    all_bills = []
    page      = 1
    while True:
        params   = {**base_params, "page": page}
        response = xero_get(url, headers=headers, params=params)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch bills (page {page}): {response.status_code} - {response.text}")
        batch = response.json().get("Invoices", [])
        all_bills.extend(batch)
        print(f"  Page {page}: {len(batch)} bill(s)")
        if len(batch) < PAGE_SIZE:
            break
        page += 1

    return all_bills


def fetch_attachment_ids(access_token, tenant_id, invoice_id):
    url     = f"https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}/Attachments"
    headers = {
        "Authorization":  f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept":         "application/json",
    }
    response = xero_get(url, headers=headers)
    if response.status_code != 200:
        print(f"  Warning: could not fetch attachments for {invoice_id}: {response.status_code}")
        return []
    return [
        (a["AttachmentID"], a.get("FileName", ""), a.get("MimeType", ""))
        for a in response.json().get("Attachments", [])
    ]


def fetch_attachment_pdf(access_token, tenant_id, invoice_id, attachment_id):
    url     = f"https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}/Attachments/{attachment_id}"
    headers = {
        "Authorization":  f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept":         "application/pdf",
    }
    response = xero_get(url, headers=headers)
    if response.status_code != 200:
        print(f"  Warning: could not download attachment {attachment_id}: {response.status_code}")
        return None
    return response.content


def load_existing_invoice_numbers():
    if not os.path.exists(CSV_PATH):
        return set()
    df = pd.read_csv(CSV_PATH, usecols=["Invoice No"], dtype=str)
    return set(df["Invoice No"].dropna().str.strip())


def is_pdf(filename, mime_type):
    return filename.lower().endswith(".pdf") or "pdf" in mime_type.lower()


def main():
    print(f"[{datetime.now():%H:%M:%S}] Authenticating with Xero (H2COCO)...")
    access_token = getXeroAccessToken("H2COCO")
    tenant_id    = XeroTenants(access_token)
    if not tenant_id:
        raise Exception("Could not retrieve Xero tenant ID for H2COCO.")

    last_updated   = get_github_variable(DISTRIBUTION_LAST_UPDATED_VAR)
    modified_since = None if (not last_updated or last_updated == "INIT") else last_updated

    print(f"[{datetime.now():%H:%M:%S}] Fetching warehouse bills (modified_since={modified_since or 'all from ' + FY26_START})...")
    bills = fetch_bills(access_token, tenant_id, modified_since=modified_since)
    print(f"  Found {len(bills)} bill(s).")

    existing = load_existing_invoice_numbers()
    print(f"  CSV already contains {len(existing)} invoice number(s): {existing or 'none'}")

    new_rows = []

    for bill in bills:
        invoice_id     = bill.get("InvoiceID", "")
        invoice_number = bill.get("InvoiceNumber", "").strip()

        if invoice_number in existing:
            print(f"  Skipping {invoice_number} — already in CSV.")
            continue

        print(f"  Processing {invoice_number} ({invoice_id})...")
        attachments     = fetch_attachment_ids(access_token, tenant_id, invoice_id)
        pdf_attachments = [(aid, fname, mime) for aid, fname, mime in attachments if is_pdf(fname, mime)]

        if not pdf_attachments:
            print(f"    No PDF attachment found — skipping.")
            continue

        for attachment_id, filename, mime_type in pdf_attachments:
            print(f"    Downloading {filename}...")
            pdf_bytes = fetch_attachment_pdf(access_token, tenant_id, invoice_id, attachment_id)
            if not pdf_bytes:
                continue

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name

            try:
                rows = parse_invoice(tmp_path)
                if rows:
                    new_rows.extend(rows)
                    print(f"    Parsed {len(rows)} charge row(s).")
                else:
                    print(f"    Warning: no charge rows extracted from {filename}.")
            except Exception as e:
                print(f"    Error parsing {filename}: {e}")
            finally:
                os.unlink(tmp_path)

    if not new_rows:
        print("No new invoices to add.")
        return

    new_df = pd.DataFrame(new_rows)

    # Append to CSV
    if os.path.exists(CSV_PATH):
        existing_df = pd.read_csv(CSV_PATH, dtype=str)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        combined_df = new_df
    combined_df.to_csv(CSV_PATH, index=False)
    print(f"\n{len(new_rows)} new row(s) written to {CSV_PATH}")

    # Upsert to BigQuery
    print("Upserting to BigQuery...")
    upsert_to_bigquery(new_rows)

    summary = new_df[["Invoice No", "Invoice Date", "Period Month", "Period Year",
                       "State", "Invoice Total (Ex GST)", "Invoice Total (Inc GST)"]].drop_duplicates()
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
