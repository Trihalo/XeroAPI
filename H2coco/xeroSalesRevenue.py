import os
import sys
import re
import argparse
import requests
from datetime import date, datetime, timezone
from rapidfuzz import fuzz, process
from dotenv import load_dotenv
import pandas as pd
from google.api_core.exceptions import NotFound
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas_gbq
import gspread

load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xeroAuth import XeroTenants
from xeroAuthHelper import getXeroAccessToken, get_github_variable, update_github_variable

REVENUE_GL_CODES = {"4000", "4001", "4010"}
HISTORY_START = "2024-07-01"
FY_START_MONTH = 7
SO_NUMBER_REGEX = r"SI-(\d{8})"

BQ_PROJECT = "h2dataservices"
BQ_DATASET = "finance"
BQ_TABLE = "xero_sales_revenue"
BQ_TABLE_REF = f"{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"

GH_LAST_UPDATED_VAR = "XERO_LAST_UPDATED_H2COCO"


# --- Date helpers ---

def _fy_from_date(d):
    fy = d.year + 1 if d.month >= FY_START_MONTH else d.year
    return f"FY{str(fy)[2:]}"


def _derived_date_fields(date_str):
    if not date_str:
        return None, None
    try:
        d = date.fromisoformat(date_str[:10])
        return d.strftime("%b"), _fy_from_date(d)
    except ValueError:
        return None, None


def _parse_xero_date(value):
    if not value:
        return None
    if re.match(r"\d{4}-\d{2}-\d{2}", value):
        return value[:10]
    match = re.search(r"/Date\((\d+)", value)
    if match:
        ts = int(match.group(1)) / 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    return None


def _extract_so_number(ref):
    if not ref:
        return None
    match = re.search(SO_NUMBER_REGEX, ref)
    return f"SI-{match.group(1)}" if match else None


def _extract_sku(description):
    match = re.match(r"^([\w-]+) - ", description or "")
    return match.group(1) if match else None


def _digit_parts(text):
    return set(re.findall(r"\d+(?:\.\d+)?", text.lower()))


def _fuzzy_match_sku(description, catalog):
    if not description or not catalog:
        return None
    query_digits = _digit_parts(description)
    choices = {
        row["sku_name"]: row["sku_code"]
        for row in catalog
        if row.get("sku_name") and row.get("sku_code")
        and str(row.get("obsolete", "")).upper() != "OBSOLETE"
        and (not query_digits or query_digits.issubset(_digit_parts(row["sku_name"])))
    }
    if not choices:
        return None
    result = process.extractOne(description, choices.keys(), scorer=fuzz.token_set_ratio, score_cutoff=75)
    if result:
        matched_name, _, _ = result
        return choices[matched_name]
    return None


def _classify_sku(description, catalog):
    return _extract_sku(description) or _fuzzy_match_sku(description, catalog)


CATALOG_SHEET_ID = "1ARCS-K8d1_QQBtI-k9iAuJMonMbO9y9W7reuV7G3z2U"
CATALOG_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def fetch_product_catalog(key_path):
    credentials = service_account.Credentials.from_service_account_file(
        key_path, scopes=CATALOG_SCOPES
    )
    gc = gspread.authorize(credentials)
    worksheet = gc.open_by_key(CATALOG_SHEET_ID).get_worksheet(0)
    rows = worksheet.get_all_values()
    if not rows:
        print("⚠️ Product catalog sheet is empty.")
        return []
    headers = rows[0]
    sku_col = headers.index("SKU")
    product_col = headers.index("Product")
    obsolete_col = headers.index("Obsolete") if "Obsolete" in headers else None
    catalog = [
        {
            "sku_code": row[sku_col].strip(),
            "sku_name": row[product_col].strip(),
            "obsolete": row[obsolete_col].strip() if obsolete_col is not None else "",
        }
        for row in rows[1:]
        if row[sku_col].strip() and row[product_col].strip()
    ]
    print(f"📦 Loaded {len(catalog)} products from catalog.")
    return catalog


def _xero_date_filter(date_str):
    y, m, d = date_str.split("-")
    return f"DateTime({y},{int(m)},{int(d)})"


def _xero_headers(access_token, tenant_id):
    return {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json",
    }


def _paginate(url, headers, params, key, desc):
    results, page = [], 1
    while True:
        resp = requests.get(url, headers=headers, params={**params, "page": page}, timeout=120)
        if resp.status_code != 200:
            raise Exception(f"Xero API error (page {page}): {resp.status_code} - {resp.text}")
        batch = resp.json().get(key, [])
        if not batch:
            break
        results.extend(batch)
        print(f"  {desc}: page {page} ({len(results)} records so far)")
        if len(batch) < 1000:
            break
        page += 1
    return results


def _updated_since_clause(updated_since):
    if not updated_since:
        return ""
    u = updated_since
    return f" AND UpdatedDateUTC>=DateTime({u.year},{u.month},{u.day},{u.hour},{u.minute},{u.second})"


# --- Xero fetchers ---

def fetch_invoices(access_token, tenant_id, updated_since, catalog):
    dt_filter = _xero_date_filter(HISTORY_START)
    where = f'Type=="ACCREC" AND Date>={dt_filter}' + _updated_since_clause(updated_since)

    invoices = _paginate(
        "https://api.xero.com/api.xro/2.0/Invoices",
        _xero_headers(access_token, tenant_id),
        {"Statuses": "AUTHORISED,PAID", "where": where, "pageSize": 1000},
        "Invoices",
        "invoices",
    )

    rows = []
    for inv in invoices:
        inv_date = inv.get("DateString", "")[:10] or None
        month, financial_year = _derived_date_fields(inv_date)
        currency_rate = inv.get("CurrencyRate") or 1.0
        line_amount_types = inv.get("LineAmountTypes")
        matching = [l for l in inv.get("LineItems", []) if l.get("AccountCode") in REVENUE_GL_CODES]
        for line in matching:
            raw = line.get("LineAmount") or 0
            tax = line.get("TaxAmount") or 0
            amount = raw - tax if (line_amount_types or "").upper() == "INCLUSIVE" else raw
            rows.append({
                "sourceType": "INVOICE",
                "transactionId": inv.get("InvoiceID"),
                "transactionNumber": inv.get("InvoiceNumber"),
                "status": inv.get("Status"),
                "contactName": inv.get("Contact", {}).get("Name"),
                "contactId": inv.get("Contact", {}).get("ContactID"),
                "date": inv_date,
                "month": month,
                "financialYear": financial_year,
                "dueDate": inv.get("DueDateString", "")[:10] or None,
                "lineItemId": line.get("LineItemID"),
                "description": line.get("Description"),
                "quantity": line.get("Quantity"),
                "unitAmount": line.get("UnitAmount"),
                "accountCode": line.get("AccountCode"),
                "currencyCode": inv.get("CurrencyCode"),
                "currencyRate": currency_rate,
                "lineAmount": amount,
                "lineAmountAUD": round(amount / currency_rate, 2),
                "unitAmountAUD": round((line.get("UnitAmount") or 0) / currency_rate, 2),
                "taxAmount": tax,
                "soNumber": _extract_so_number(inv.get("InvoiceNumber") or ""),
                "sku": _classify_sku(line.get("Description"), catalog),
            })
    return rows


def fetch_credit_notes(access_token, tenant_id, updated_since, catalog):
    dt_filter = _xero_date_filter(HISTORY_START)
    where = f'Type=="ACCRECCREDIT" AND Date>={dt_filter}' + _updated_since_clause(updated_since)

    credit_notes = _paginate(
        "https://api.xero.com/api.xro/2.0/CreditNotes",
        _xero_headers(access_token, tenant_id),
        {"where": where, "Statuses": "AUTHORISED,PAID", "pageSize": 1000},
        "CreditNotes",
        "credit notes",
    )

    rows = []
    for cn in credit_notes:
        if cn.get("Status") in ("DELETED", "VOIDED"):
            continue
        cn_date = cn.get("DateString", "")[:10] or None
        month, financial_year = _derived_date_fields(cn_date)
        currency_rate = cn.get("CurrencyRate") or 1.0
        line_amount_types = cn.get("LineAmountTypes")
        matching = [l for l in cn.get("LineItems", []) if l.get("AccountCode") in REVENUE_GL_CODES]
        for line in matching:
            raw = line.get("LineAmount") or 0
            tax = line.get("TaxAmount") or 0
            amount = -(raw - tax) if (line_amount_types or "").upper() == "INCLUSIVE" else -raw
            rows.append({
                "sourceType": "CREDIT_NOTE",
                "transactionId": cn.get("CreditNoteID"),
                "transactionNumber": cn.get("CreditNoteNumber"),
                "status": cn.get("Status"),
                "contactName": cn.get("Contact", {}).get("Name"),
                "contactId": cn.get("Contact", {}).get("ContactID"),
                "date": cn_date,
                "month": month,
                "financialYear": financial_year,
                "dueDate": None,
                "lineItemId": line.get("LineItemID"),
                "description": line.get("Description"),
                "quantity": -(line.get("Quantity") or 0),
                "unitAmount": -(line.get("UnitAmount") or 0),
                "accountCode": line.get("AccountCode"),
                "currencyCode": cn.get("CurrencyCode"),
                "currencyRate": currency_rate,
                "lineAmount": amount,
                "lineAmountAUD": round(amount / currency_rate, 2),
                "unitAmountAUD": round(-(line.get("UnitAmount") or 0) / currency_rate, 2),
                "taxAmount": tax,
                "soNumber": _extract_so_number(cn.get("CreditNoteNumber") or ""),
                "sku": _classify_sku(line.get("Description"), catalog),
            })
    return rows


def fetch_manual_journals(access_token, tenant_id, updated_since):
    y, m, d = HISTORY_START.split("-")
    where = f'Date>=DateTime({y}, {int(m)}, {int(d)}) AND Status=="POSTED"' + _updated_since_clause(updated_since)

    journals = _paginate(
        "https://api.xero.com/api.xro/2.0/ManualJournals",
        _xero_headers(access_token, tenant_id),
        {"where": where, "pageSize": 1000},
        "ManualJournals",
        "manual journals",
    )

    rows = []
    for journal in journals:
        narration = journal.get("Narration", "")
        journal_id = journal.get("ManualJournalID")
        raw_date = _parse_xero_date(journal.get("DateString") or journal.get("Date"))
        month, financial_year = _derived_date_fields(raw_date) if raw_date else (None, None)
        matching = [l for l in journal.get("JournalLines", []) if l.get("AccountCode") in REVENUE_GL_CODES]
        for idx, line in enumerate(matching):
            line_desc = line.get("Description", "")
            description = f"{narration} - {line_desc}" if line_desc else narration
            line_amount = -(line.get("LineAmount") or 0)
            tax_amount = line.get("TaxAmount") or 0
            rows.append({
                "sourceType": "MANUAL_JOURNAL",
                "transactionId": journal_id,
                "transactionNumber": None,
                "status": journal.get("Status"),
                "contactName": None,
                "contactId": None,
                "date": raw_date,
                "month": month,
                "financialYear": financial_year,
                "dueDate": None,
                "lineItemId": f"{journal_id}:{idx}",
                "description": description,
                "quantity": 1,
                "unitAmount": line_amount,
                "accountCode": line.get("AccountCode"),
                "currencyCode": "AUD",
                "currencyRate": 1.0,
                "lineAmount": line_amount,
                "lineAmountAUD": line_amount,
                "unitAmountAUD": line_amount,
                "taxAmount": tax_amount,
                "soNumber": _extract_so_number(narration),
                "sku": None,
            })
    return rows


# --- BigQuery upsert ---

def upsert_to_bigquery(rows, truncate=False):
    if not rows:
        print("ℹ️ No rows to upload.")
        return

    key_path = os.getenv("H2DATASERVICES_BQACCESS")
    credentials = service_account.Credentials.from_service_account_file(
        key_path,
        scopes=["https://www.googleapis.com/auth/bigquery"]
    )
    client = bigquery.Client(credentials=credentials, project=BQ_PROJECT)

    if truncate:
        client.delete_table(BQ_TABLE_REF, not_found_ok=True)
        print(f"⚠️ Dropped {BQ_TABLE_REF} — will be recreated with current schema.")
    else:
        try:
            transaction_ids = list({r["transactionId"] for r in rows if r.get("transactionId")})
            if transaction_ids:
                placeholders = ", ".join(f"'{tid}'" for tid in transaction_ids)
                client.query(f"DELETE FROM `{BQ_TABLE_REF}` WHERE transactionId IN ({placeholders})").result()
                print(f"🗑️ Deleted existing rows for {len(transaction_ids)} transactions.")
        except NotFound:
            print(f"ℹ️ Table {BQ_TABLE_REF} does not exist yet — will be created on insert.")

    df = pd.DataFrame(rows)
    df = df.where(pd.notnull(df), None)

    for col in ["date", "dueDate"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    pandas_gbq.to_gbq(
        df,
        f"{BQ_DATASET}.{BQ_TABLE}",
        project_id=BQ_PROJECT,
        credentials=credentials,
        if_exists="append"
    )
    print(f"✅ Uploaded {len(df)} rows to {BQ_TABLE_REF}.")


# --- Main ---

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--truncate", action="store_true", help="Truncate the BQ table before uploading (full reset)")
    args = parser.parse_args()

    run_start = datetime.now(timezone.utc)

    if args.truncate:
        updated_since = None
        print(f"⚠️ --truncate flag set: full history reload from {HISTORY_START}.")
    else:
        last_updated_str = get_github_variable(GH_LAST_UPDATED_VAR)
        if last_updated_str and last_updated_str != "INIT":
            try:
                updated_since = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
                print(f"📅 Incremental run: fetching records updated since {updated_since.isoformat()}")
            except ValueError:
                updated_since = None
                print(f"⚠️ Could not parse {GH_LAST_UPDATED_VAR} ('{last_updated_str}'), falling back to full history.")
        else:
            updated_since = None
            print(f"ℹ️ {GH_LAST_UPDATED_VAR} is '{last_updated_str}' — fetching full history from {HISTORY_START}.")

    key_path = os.getenv("H2DATASERVICES_BQACCESS")
    catalog = fetch_product_catalog(key_path)

    access_token = getXeroAccessToken("H2COCO")
    tenant_id = XeroTenants(access_token)

    invoices = fetch_invoices(access_token, tenant_id, updated_since, catalog)
    print(f"  invoices:        {len(invoices)} lines")

    credit_notes = fetch_credit_notes(access_token, tenant_id, updated_since, catalog)
    print(f"  credit_notes:    {len(credit_notes)} lines")

    journals = fetch_manual_journals(access_token, tenant_id, updated_since)
    print(f"  manual_journals: {len(journals)} lines")

    all_rows = invoices + credit_notes + journals
    print(f"Total: {len(all_rows)} lines")

    upsert_to_bigquery(all_rows, truncate=args.truncate)

    update_github_variable(GH_LAST_UPDATED_VAR, run_start.strftime("%Y-%m-%dT%H:%M:%SZ"))
    print(f"📝 Updated {GH_LAST_UPDATED_VAR} to {run_start.isoformat()}.")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        since_label = updated_since.strftime("%Y-%m-%d %H:%M UTC") if updated_since else HISTORY_START
        mode_note = "> ⚠️ Full reset: table was truncated and reloaded from scratch.\n" if args.truncate else f"> 📅 Incremental run — records updated since `{since_label}`\n"
        with open(summary_path, "w") as f:
            f.write("## H2coco Sales Revenue Upload\n\n")
            f.write("| Source | Lines |\n|--------|------:|\n")
            f.write(f"| Invoices | {len(invoices)} |\n")
            f.write(f"| Credit Notes | {len(credit_notes)} |\n")
            f.write(f"| Manual Journals | {len(journals)} |\n")
            f.write(f"| **Total** | **{len(all_rows)}** |\n\n")
            f.write(mode_note)


if __name__ == "__main__":
    main()
