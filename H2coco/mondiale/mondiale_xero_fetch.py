import argparse
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
from mondiale_to_csv import parse_invoice
from mondiale_bq import (
    upsert_to_bigquery,
    load_existing_invoice_numbers,
    normalize_invoice_no,
    truncate_from_date,
)

FREIGHT_LAST_UPDATED_VAR = "H2COCO_FREIGHT_LAST_UPDATED"

RATE_LIMIT = 60
MAX_RETRIES = 5
_call_times: deque = deque()


def xero_get(url, headers, params=None):
    for attempt in range(MAX_RETRIES):
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
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 429 or response.status_code >= 500:
            retry_after = response.headers.get("Retry-After")
            try:
                wait = float(retry_after) if retry_after else min(2 ** attempt, 60)
            except ValueError:
                wait = min(2 ** attempt, 60)
            wait = max(wait, 1.0)
            if attempt == MAX_RETRIES - 1:
                print(f"  [retry] giving up after {MAX_RETRIES} attempts (status {response.status_code})")
                return response
            print(f"  [retry] status {response.status_code}, sleeping {wait:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})...")
            time.sleep(wait)
            continue
        return response
    return response


CONTACT_IDS = [
    "83a23b56-eb5e-455e-aa89-8b301ccc3fba",  # Mondiale Freight Forwarding
    "49ecbcb8-643f-4abd-9c2c-966f45902683",  # AFER Logistics
]
FY26_START = "2025-07-01"
PAGE_SIZE  = 1000
MAX_BILLS  = None  # set to an int to cap for testing


def fetch_bills(access_token, tenant_id, modified_since=None):
    url = "https://api.xero.com/api.xro/2.0/Invoices"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json",
    }
    if modified_since:
        headers["If-Modified-Since"] = modified_since
        print(f"  Using If-Modified-Since: {modified_since}")

    contact_filter = " OR ".join(f'Contact.ContactID=Guid("{cid}")' for cid in CONTACT_IDS)
    base_params = {
        "Type": "ACCPAY",
        "Statuses": "AUTHORISED,PAID",
        "where": f'({contact_filter}) AND Date >= DateTime({FY26_START.replace("-", ",")})',
        "pageSize": PAGE_SIZE,
    }

    all_bills = []
    page = 1
    while True:
        params = {**base_params, "page": page}
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
    url = f"https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}/Attachments"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json",
    }
    response = xero_get(url, headers=headers)
    if response.status_code != 200:
        print(f"  Warning: could not fetch attachments for {invoice_id}: {response.status_code}")
        return None
    return [
        (a["AttachmentID"], a.get("FileName", ""), a.get("MimeType", ""))
        for a in response.json().get("Attachments", [])
    ]


def fetch_attachment_pdf(access_token, tenant_id, invoice_id, attachment_id):
    url = f"https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}/Attachments/{attachment_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/pdf",
    }
    response = xero_get(url, headers=headers)
    if response.status_code != 200:
        print(f"  Warning: could not download attachment {attachment_id}: {response.status_code}")
        return None
    return response.content


def is_pdf(filename, mime_type):
    return filename.lower().endswith(".pdf") or "pdf" in mime_type.lower()


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch Mondiale/AFER freight bills from Xero into BigQuery.")
    parser.add_argument(
        "--truncate",
        action="store_true",
        help=f"Delete all rows in freight_charges with invoice_date >= {FY26_START} before running, "
             f"and reset {FREIGHT_LAST_UPDATED_VAR} to INIT. Requires confirmation.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the truncate confirmation prompt (use with care).",
    )
    parser.add_argument(
        "--truncate-only",
        action="store_true",
        help="Truncate and exit, without running the fetch afterwards.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    run_start = datetime.now(timezone.utc)

    if args.truncate or args.truncate_only:
        print(f"\n  ⚠️  About to DELETE all rows in freight_charges where invoice_date >= {FY26_START}")
        if not args.yes:
            confirm = input("  Type 'TRUNCATE' to confirm: ").strip()
            if confirm != "TRUNCATE":
                print("  Aborted.")
                return
        deleted = truncate_from_date(FY26_START)
        print(f"  Deleted {deleted} row(s) from freight_charges.")
        update_github_variable(FREIGHT_LAST_UPDATED_VAR, "INIT")
        print(f"  Reset {FREIGHT_LAST_UPDATED_VAR} → INIT")
        if args.truncate_only:
            print("  --truncate-only set, exiting without fetch.")
            return

    print(f"[{datetime.now():%H:%M:%S}] Authenticating with Xero (H2COCO)...")
    access_token = getXeroAccessToken("H2COCO")
    tenant_id = XeroTenants(access_token)
    if not tenant_id:
        raise Exception("Could not retrieve Xero tenant ID for H2COCO.")

    last_updated = get_github_variable(FREIGHT_LAST_UPDATED_VAR)
    modified_since = None if (not last_updated or last_updated == "INIT") else last_updated

    print(f"[{datetime.now():%H:%M:%S}] Fetching bills (modified_since={modified_since or 'all from ' + FY26_START})...")
    bills = fetch_bills(access_token, tenant_id, modified_since=modified_since)
    print(f"  Found {len(bills)} bill(s) across both contacts.")

    if MAX_BILLS is not None:
        bills = bills[:MAX_BILLS]
        print(f"  Capped to first {MAX_BILLS} bill(s) for testing.")

    existing = load_existing_invoice_numbers()
    print(f"  BigQuery already contains {len(existing)} invoice number(s).")

    new_rows = []
    failures = []

    for bill in bills:
        invoice_id     = bill.get("InvoiceID", "")
        invoice_number = bill.get("InvoiceNumber", "").strip()
        invoice_key    = normalize_invoice_no(invoice_number)

        if invoice_key and invoice_key in existing:
            print(f"  Skipping {invoice_number} — already in BigQuery.")
            continue

        print(f"  Processing {invoice_number} ({invoice_id})...")
        attach_resp = fetch_attachment_ids(access_token, tenant_id, invoice_id)
        if attach_resp is None:
            failures.append((invoice_number, "attachment list fetch failed"))
            continue
        pdf_attachments = [(aid, fname, mime) for aid, fname, mime in attach_resp if is_pdf(fname, mime)]

        if not pdf_attachments:
            print(f"    No PDF attachment found — skipping.")
            failures.append((invoice_number, "no PDF attachment"))
            continue

        bill_added_rows = False
        for attachment_id, filename, _ in pdf_attachments:
            print(f"    Downloading {filename}...")
            pdf_bytes = fetch_attachment_pdf(access_token, tenant_id, invoice_id, attachment_id)
            if not pdf_bytes:
                failures.append((invoice_number, f"PDF download failed ({filename})"))
                continue

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name

            try:
                rows = parse_invoice(tmp_path)
                if rows:
                    # Xero's InvoiceNumber is canonical — the PDF regex strips
                    # suffixes like "/A" on amended invoices, which silently
                    # collides amendments with originals in BQ.
                    for r in rows:
                        r["Invoice No"] = invoice_number
                    new_rows.extend(rows)
                    bill_added_rows = True
                    print(f"    Parsed {len(rows)} charge row(s).")
                else:
                    print(f"    Warning: no charge rows extracted from {filename}.")
                    failures.append((invoice_number, f"no rows parsed ({filename})"))
            except Exception as e:
                print(f"    Error parsing {filename}: {e}")
                failures.append((invoice_number, f"parse error ({filename}): {e}"))
            finally:
                os.unlink(tmp_path)

        if not bill_added_rows and not any(f[0] == invoice_number for f in failures):
            failures.append((invoice_number, "no rows added"))

    if new_rows:
        print(f"\n{len(new_rows)} new row(s) to upsert.")
        upsert_to_bigquery(new_rows)
    else:
        print("No new invoices to add.")

    if failures:
        print(f"\n  {len(failures)} invoice(s) failed — NOT updating {FREIGHT_LAST_UPDATED_VAR} so they will be retried next run:")
        for inv_num, reason in failures:
            print(f"    - {inv_num}: {reason}")
    elif new_rows:
        # Only advance the watermark when everything we attempted succeeded
        timestamp = run_start.strftime("%a, %d %b %Y %H:%M:%S GMT")
        update_github_variable(FREIGHT_LAST_UPDATED_VAR, timestamp)
        print(f"  Updated {FREIGHT_LAST_UPDATED_VAR} → {timestamp}")

    if not new_rows:
        return

    new_df = pd.DataFrame(new_rows)
    summary = new_df[["Invoice No", "Invoice Total (Inc GST)", "PO", "Total Pkgs"]].drop_duplicates()
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
