import sys
import os
import requests
import csv
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta, timezone
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas_gbq
from dotenv import load_dotenv
import pytz

load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xeroAuth import XeroTenants
from xeroAuthHelper import getXeroAccessToken

FULL_RESET = False

# --- Helpers ---

aest = pytz.timezone("Australia/Sydney")

def parse_xero_date(date_str):
    if not isinstance(date_str, str):
        return None
    match = re.search(r"/Date\((\d+)", date_str)
    if match:
        timestamp_ms = int(match.group(1))
        utc_dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        return utc_dt.astimezone(aest)
    return None

def clean_small_numbers(val, threshold=1e-8):
    return 0 if abs(val) < threshold else val

def export_to_bigquery(rows, table_id):
    if not rows:
        print("❌ No rows to upload")
        return

    key_path = os.getenv("MAC_MERCHANDISING_BQACCESS")
    project_id = "macmerchandising"
    dataset_id = "FinanceData"
    table_ref = f"{project_id}.{dataset_id}.{table_id}"

    try:
        credentials = service_account.Credentials.from_service_account_file(
            key_path,
            scopes=["https://www.googleapis.com/auth/bigquery"]
        )
        client = bigquery.Client(credentials=credentials, project=project_id)

        deleted_ids = [r["InvoiceID"] for r in rows if r.get("__deleted__") and r.get("InvoiceID")]
        if deleted_ids:
            placeholders = ", ".join(f"'{id}'" for id in deleted_ids)
            query = f"DELETE FROM `{table_ref}` WHERE InvoiceID IN ({placeholders})"
            client.query(query).result()
            print(f"🗑️ Deleted {len(deleted_ids)} voided/deleted invoices from BigQuery.")

        filtered_rows = [r for r in rows if not r.get("__deleted__")]
        if not filtered_rows:
            print("ℹ️ No valid rows to upload after filtering.")
            return

        df = pd.DataFrame(filtered_rows)
        df = df.where(pd.notnull(df), None)

        if FULL_RESET:
            client.query(f"DELETE FROM `{table_ref}` WHERE 1=1").result()
            print("⚠️ Full reset: all rows deleted.")
        else:
            updated_ids = df["InvoiceID"].dropna().astype(str).tolist()
            if updated_ids:
                placeholders = ", ".join(f"'{id}'" for id in updated_ids)
                client.query(f"DELETE FROM `{table_ref}` WHERE InvoiceID IN ({placeholders})").result()
                print(f"✅ Deleted {len(updated_ids)} updated invoices from BigQuery.")

        date_columns = ["InvoiceDate", "DueDate", "FullyPaidOffDate", "UpdatedDate"]

        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        pandas_gbq.to_gbq(
            df,
            f"{dataset_id}.{table_id}",
            project_id=project_id,
            credentials=credentials,
            if_exists="append"
        )
        print(f"✅ Successfully uploaded {len(df)} rows to BigQuery.")
    except Exception as e:
        print(f"❌ Upload failed: {e}")

def fetch_all(endpoint, access_token, tenant_id, params=None):
    all_results = []
    params = params or {"page": 1, "pageSize": 1000}
    while True:
        res = requests.get(
            f"https://api.xero.com/api.xro/2.0/{endpoint}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Xero-tenant-id": tenant_id,
                "Accept": "application/json"
            },
            params=params
        )
        if res.status_code != 200:
            raise Exception(f"Fetch failed for {endpoint}: {res.status_code} - {res.text}")
        data = res.json().get(endpoint, [])
        if not data:
            break
        all_results.extend(data)
        params["page"] += 1
    return all_results

def export_to_csv(rows, filename="xero_export.csv"):
    if not rows:
        print("❌ No rows to export")
        return
    df = pd.DataFrame(rows)
    df.to_csv(filename, index=False)
    print(f"📄 Exported {len(df)} rows to {filename}")

def map_credit_note_allocations(credit_notes):
    allocation_map = {}
    for note in credit_notes:
        rate = float(note.get("CurrencyRate") or 1)
        for alloc in note.get("Allocations", []):
            invoice_id = alloc.get("Invoice", {}).get("InvoiceID")
            amount = float(alloc.get("AppliedAmount") or 0) / rate
            if invoice_id:
                allocation_map[invoice_id] = allocation_map.get(invoice_id, 0) + amount
    return allocation_map

def transform_invoice_data(rows, allocation_map=None, is_bd=False):
    result = []

    for r in rows:
        try:
            status = r.get("Status", "").upper()
            if status in ["VOIDED", "DELETED"]:
                continue

            invoice_id = r.get("InvoiceID")
            invoice_date = parse_xero_date(r.get("Date"))
            due_date = parse_xero_date(r.get("DueDate"))
            paid_date = parse_xero_date(r.get("FullyPaidOnDate"))
            updated_date = parse_xero_date(r.get("UpdatedDateUTC"))

            rate = float(r.get("CurrencyRate") or 1)
            subtotal = float(r.get("SubTotal", 0))
            tax = float(r.get("TotalTax", 0))
            total_amount = (subtotal + tax) / rate if rate else 0
            amount_paid = float(r.get("AmountPaid", 0)) / rate if rate else 0
            credited = float(r.get("AmountCredited", 0)) 
            outstanding = clean_small_numbers(total_amount - amount_paid - credited)

            base_fields = {
                "Type": "Invoice",
                "InvoiceID": invoice_id,
                "InvoiceNumber": r.get("InvoiceNumber"),
                "Reference": r.get("Reference"),
                "ContactName": r.get("Contact", {}).get("Name"),
                "InvoiceDate": invoice_date,
                "DueDate": due_date,
                "Status": r.get("Status"),
                "FullyPaidOffDate": paid_date,
                "CurrencyCode": r.get("CurrencyCode"),
                "CurrencyRate": rate,
                "SubtotalSource": subtotal,
                "TotalTaxSource": tax,
                "UpdatedDate": updated_date
            }

            if is_bd:
                line_items = r.get("LineItems", [])
                total_line_amount = sum(float(line.get("LineAmount", 0)) for line in line_items)

                for line in line_items:
                    line_amount = float(line.get("LineAmount", 0))
                    proportion = line_amount / total_line_amount if total_line_amount else 0

                    tracking_option = None
                    for t in line.get("Tracking", []):
                        if t.get("Name") == "Product Line":
                            tracking_option = t.get("Option")

                    description = line.get("Description", {})

                    entry = {
                        **base_fields,
                        "ProductLine": tracking_option,
                        "Description": description,
                        "InvoiceAmountAUD": total_amount * proportion,
                        "AmountPaidAUD": amount_paid * proportion,
                        "CreditedAmountAUD": credited * proportion,
                        "OutstandingAmountAUD": outstanding * proportion,
                    }
                    result.append(entry)
            else:
                entry = {
                    **base_fields,
                    "ProductLine": None,
                    "Description": None,
                    "InvoiceAmountAUD": total_amount,
                    "AmountPaidAUD": amount_paid,
                    "CreditedAmountAUD": credited,
                    "OutstandingAmountAUD": outstanding,
                }
                result.append(entry)

        except Exception as e:
            print(f"⚠️ Error transforming invoice {r.get('InvoiceID')}: {e}")

    desired_fields = [
        "Type", "InvoiceID", "InvoiceNumber", "Reference", "ContactName",
        "InvoiceDate", "DueDate", "Status", "FullyPaidOffDate",
        "CurrencyCode", "CurrencyRate", "SubtotalSource", "TotalTaxSource",
        "InvoiceAmountAUD", "AmountPaidAUD", "CreditedAmountAUD", "OutstandingAmountAUD",
        "UpdatedDate"
    ]

    if is_bd:
        desired_fields.extend(["ProductLine", "Description"])

    return [{k: r.get(k) for k in desired_fields} for r in result]


def transform_credit_notes(credit_notes):
    rows = []
    for note in credit_notes:
        try:
            if note.get("Type") != "ACCRECCREDIT":
                # Skip AP credits
                continue

            date = parse_xero_date(note.get("Date"))
            due_date = parse_xero_date(note.get("DueDate"))
            updated = parse_xero_date(note.get("UpdatedDateUTC"))
            paid_date = parse_xero_date(note.get("FullyPaidOnDate"))

            rate = float(note.get("CurrencyRate") or 1)
            subtotal = float(note.get("SubTotal", 0))
            tax = float(note.get("TotalTax", 0))
            amount = (subtotal + tax) / rate if rate else 0

            contact_name = note.get("Contact", {}).get("Name")

            rows.append({
                "Type": "CreditNote",
                "InvoiceID": note.get("CreditNoteID"),
                "InvoiceNumber": note.get("CreditNoteNumber"),
                "Reference": note.get("Reference"),
                "ContactName": contact_name,
                "InvoiceDate": date if date else None,
                "DueDate": due_date if due_date else None,
                "Status": note.get("Status"),
                "FullyPaidOffDate": paid_date if paid_date else None,
                "CurrencyCode": note.get("CurrencyCode"),
                "CurrencyRate": rate,
                "SubtotalSource": subtotal,
                "TotalTaxSource": tax,
                "InvoiceAmountAUD": amount,
                "AmountPaidAUD": 0,
                "CreditedAmountAUD": 0,
                "OutstandingAmountAUD": -amount,
                "UpdatedDate": updated if updated else None,
            })
        except Exception as e:
            print(f"⚠️ Error transforming credit note {note.get('CreditNoteID')}: {e}")
    return rows


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ["BD", "MM"]:
        print("❌ Please specify a valid client: BD or MM")
        sys.exit(1)

    arg = sys.argv[1]
    if arg == "BD":
        client = "BONDI_DAIRY"
        table_id = "BDInvoices"
    else:
        client = "MAC_MERCHANDISING"
        table_id = "MMInvoices"

    updated_since = datetime.now(timezone.utc) - timedelta(days=1)
    updated_date_str = f'DateTime({updated_since.year},{updated_since.month:02},{updated_since.day:02})'

    access_token = getXeroAccessToken(client)
    tenant_id = XeroTenants(access_token)

    invoice_params = {
        "where": 'Type=="ACCREC"' if FULL_RESET else f'Type=="ACCREC" AND UpdatedDateUTC>={updated_date_str}',
        "page": 1,
        "pageSize": 1000
    }
    credit_params = {
        "where": '' if FULL_RESET else f'UpdatedDateUTC>={updated_date_str}',
        "page": 1,
        "pageSize": 1000
    }

    invoices = fetch_all("Invoices", access_token, tenant_id, invoice_params)
    credit_notes = fetch_all("CreditNotes", access_token, tenant_id, credit_params)
    invoices = [inv for inv in invoices if inv.get("Status", "").upper() not in ["VOIDED", "DELETED"]]

    print(f"Fetched {len(invoices)} invoices, {len(credit_notes)} credit notes")

    allocation_map = map_credit_note_allocations(credit_notes)

    invoice_rows = transform_invoice_data(invoices, allocation_map=allocation_map, is_bd=(arg == "BD"))
    credit_rows = transform_credit_notes(credit_notes)

    all_rows = invoice_rows + credit_rows

    # export_to_csv(all_rows, f"xero_combined_export_{arg}.csv")
    export_to_bigquery(all_rows, table_id)


if __name__ == "__main__":
    main()
