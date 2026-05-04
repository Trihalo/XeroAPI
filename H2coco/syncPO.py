import sys
import os
import re
import json
import requests
import pandas as pd
from datetime import datetime, timezone
from google.cloud import bigquery
from google.oauth2 import service_account
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xeroAuth import XeroTenants
from xeroAuthHelper import getXeroAccessToken

PROJECT_ID = "h2dataservices"
DATASET_ID = "finance"
TABLE_ID = "supplierPrepayments"
TABLE_REF = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
SYNC_FROM_DATE = "2026-04-01"
ACCOUNT_CODE = "2010"

REFERENCE_PATTERN = re.compile(
    r'(.+?)\s+PO\s*(\d+)\s+(DP|FP)\s+USD\s*([\d,]+(?:\.\d+)?)',
    re.IGNORECASE
)


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
        match = re.search(rf'^{re.escape(var_name)}=(.*)', content, re.MULTILINE)
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
    return bigquery.Client(credentials=credentials, project=PROJECT_ID)


TABLE_SCHEMA = [
    bigquery.SchemaField("xeroTransactionID", "STRING"),
    bigquery.SchemaField("lineItemIndex", "INT64"),
    bigquery.SchemaField("poNumber", "STRING"),
    bigquery.SchemaField("type", "STRING"),
    bigquery.SchemaField("supplier", "STRING"),
    bigquery.SchemaField("date", "DATE"),
    bigquery.SchemaField("currencyRate", "FLOAT64"),
    bigquery.SchemaField("usdAmount", "FLOAT64"),
    bigquery.SchemaField("audAmount", "FLOAT64"),
    bigquery.SchemaField("transactionType", "STRING"),
    bigquery.SchemaField("rawReference", "STRING"),
    bigquery.SchemaField("parseStatus", "STRING"),
    bigquery.SchemaField("allocatedDate", "DATE"),
    bigquery.SchemaField("syncedAt", "TIMESTAMP"),
]


def ensure_table_exists(client):
    dataset_ref = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_ID}")
    dataset_ref.location = "australia-southeast1"
    client.create_dataset(dataset_ref, exists_ok=True)
    table = bigquery.Table(TABLE_REF, schema=TABLE_SCHEMA)
    client.create_table(table, exists_ok=True)


def migrate_schema(client):
    """Recreate table if required columns are missing (drops and recreates to avoid streaming buffer issues)."""
    try:
        table = client.get_table(TABLE_REF)
        existing_cols = {f.name for f in table.schema}
        required_cols = {"lineItemIndex", "audAmount"}
        if not required_cols.issubset(existing_cols):
            missing = required_cols - existing_cols
            print(f"Migrating schema: recreating table (missing columns: {missing})...")
            client.delete_table(TABLE_REF)
            client.create_table(bigquery.Table(TABLE_REF, schema=TABLE_SCHEMA))
            print("Table recreated — will re-seed and re-sync.")
    except Exception:
        pass


def is_table_empty(client):
    result = client.query(f"SELECT COUNT(*) AS cnt FROM `{TABLE_REF}`").result()
    for row in result:
        return row.cnt == 0
    return True


def get_existing_line_item_keys(client):
    result = client.query(
        f"SELECT xeroTransactionID, lineItemIndex FROM `{TABLE_REF}` "
        f"WHERE xeroTransactionID IS NOT NULL"
    ).result()
    return {(row.xeroTransactionID, row.lineItemIndex) for row in result}


def get_allocated_pos_from_legacy(client):
    try:
        result = client.query(
            "SELECT poNumber, date FROM `h2coco.FinancialData.SupplierPrepaymentPayments`"
        ).result()
        return {row.poNumber: row.date for row in result}
    except Exception:
        return {}


def build_seed_rows(client, xlsx_path="./seedPrepayment.xlsx"):
    """Return seed rows from seedPrepayment.xlsx without inserting — caller does the single combined insert."""
    if not os.path.exists(xlsx_path):
        print(f"seedPrepayment.xlsx not found at {xlsx_path}, skipping seed.")
        return []

    df = pd.read_excel(xlsx_path)
    allocated_pos = get_allocated_pos_from_legacy(client)
    rows = []

    for _, row in df.iterrows():
        try:
            po_number = str(int(row["PO"])) if pd.notna(row["PO"]) else None
        except (ValueError, TypeError):
            continue
        if not po_number:
            continue

        allocated_date = None
        if po_number in allocated_pos:
            d = allocated_pos[po_number]
            allocated_date = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)

        try:
            date_val = row["DP Date"]
            date_str = date_val.strftime("%Y-%m-%d") if hasattr(date_val, "strftime") else str(date_val)[:10]
        except Exception:
            date_str = None

        usd_amount = float(row["USD $"]) if pd.notna(row["USD $"]) else None
        aud_amount = float(row["Estimated AUD"]) if pd.notna(row["Estimated AUD"]) else None
        currency_rate = float(row["Exchange Rate"]) if pd.notna(row["Exchange Rate"]) else None
        supplier = str(row["Supplier"]).strip() if pd.notna(row["Supplier"]) else None
        payment_type = str(row["DP/FP"]).strip().upper() if pd.notna(row["DP/FP"]) else None

        rows.append({
            "xeroTransactionID": None,
            "lineItemIndex": None,
            "poNumber": po_number,
            "type": payment_type,
            "supplier": supplier,
            "date": date_str,
            "currencyRate": currency_rate,
            "usdAmount": usd_amount,
            "audAmount": aud_amount,
            "transactionType": "SPEND",
            "rawReference": None,
            "parseStatus": "OK",
            "allocatedDate": allocated_date,
            "syncedAt": datetime.now(timezone.utc).isoformat(),
        })

    return rows


def parse_xero_date(date_str):
    match = re.search(r"/Date\((\d+)", date_str)
    if match:
        return datetime.fromtimestamp(int(match.group(1)) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    return None


def fetch_bank_transactions(access_token, tenant_id):
    url = "https://api.xero.com/api.xro/2.0/BankTransactions"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json",
    }
    all_txns = []
    page = 1
    while True:
        params = {"where": "Date>=DateTime(2026,4,1)", "page": page}
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Xero API error {response.status_code}: {response.text[:200]}")
            break
        txns = response.json().get("BankTransactions", [])
        if not txns:
            break
        all_txns.extend(txns)
        if len(txns) < 100:
            break
        page += 1
    return all_txns


def parse_reference(description, line_amount_aud):
    if not description:
        return None
    match = REFERENCE_PATTERN.search(description)
    if not match:
        return None

    supplier = match.group(1).strip().rstrip(" -").strip()
    po_number = match.group(2)
    payment_type = match.group(3).upper()
    usd_amount = float(match.group(4).replace(",", ""))

    currency_rate = None
    if line_amount_aud and usd_amount:
        try:
            currency_rate = round(usd_amount / abs(float(line_amount_aud)), 6)
        except ZeroDivisionError:
            pass

    return {
        "poNumber": po_number,
        "type": payment_type,
        "supplier": supplier,
        "usdAmount": usd_amount,
        "currencyRate": currency_rate,
    }


PAYMENT_PO_PATTERN = re.compile(r'PO(\d+)\s', re.IGNORECASE)


def fetch_payments_on_account(access_token, tenant_id):
    """Fetch all AUTHORISED payments from account 2010 since SYNC_FROM_DATE."""
    url = "https://api.xero.com/api.xro/2.0/Payments"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json",
    }
    y, m, d = SYNC_FROM_DATE.split("-")
    date_filter = f"DateTime({int(y)},{int(m)},{int(d)})"
    all_payments = []
    page = 1
    while True:
        params = {
            "where": f'Account.Code=="{ACCOUNT_CODE}" AND Status=="AUTHORISED" AND Date>={date_filter}',
            "page": page,
            "pageSize": 1000,
        }
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            print(f"Payments API error {response.status_code}: {response.text[:200]}")
            break
        payments = response.json().get("Payments", [])
        if not payments:
            break
        all_payments.extend(payments)
        if len(payments) < 1000:
            break
        page += 1
    return all_payments


def sync_allocations_from_xero(client, access_token, tenant_id):
    """Set allocatedDate from Xero Payments — catches manual allocations as well as script-created ones."""
    payments = fetch_payments_on_account(access_token, tenant_id)
    print(f"Fetched {len(payments)} payments from account {ACCOUNT_CODE}.")

    result = client.query(
        f"SELECT DISTINCT poNumber FROM `{TABLE_REF}` WHERE allocatedDate IS NULL AND poNumber IS NOT NULL"
    ).result()
    unallocated_pos = {row.poNumber for row in result}

    if not unallocated_pos:
        print("No unallocated POs to check.")
        return

    # Build a map of poNumber -> payment_date from Xero payments, filtered to unallocated POs only
    po_date_map = {}
    for payment in payments:
        reference = payment.get("Reference") or ""
        match = PAYMENT_PO_PATTERN.search(reference)
        if not match:
            continue
        po_number = match.group(1)
        if po_number not in unallocated_pos or po_number in po_date_map:
            continue
        payment_date = parse_xero_date(payment.get("Date", ""))
        if payment_date:
            po_date_map[po_number] = payment_date

    if not po_date_map:
        print("No allocations to update.")
        return

    # Single MERGE instead of one UPDATE per PO
    rows_sql = ", ".join(
        f"STRUCT('{po}' AS poNumber, DATE '{date}' AS allocatedDate)"
        for po, date in po_date_map.items()
    )
    client.query(f"""
        MERGE `{TABLE_REF}` T
        USING (SELECT * FROM UNNEST([{rows_sql}])) S
        ON T.poNumber = S.poNumber AND T.allocatedDate IS NULL
        WHEN MATCHED THEN
            UPDATE SET T.allocatedDate = S.allocatedDate
    """).result()

    print(f"Updated allocatedDate for {len(po_date_map)} PO(s) from Xero payments.")


def main():
    full_refresh = "--full-refresh" in sys.argv
    print("Starting syncPO..." + (" (full refresh)" if full_refresh else ""))

    try:
        access_token = getXeroAccessToken("H2COCO")
        tenant_id = XeroTenants(access_token)
    except Exception as e:
        print(f"Xero auth failed: {e}")
        sys.exit(1)

    client = get_bq_client()

    if full_refresh:
        try:
            client.delete_table(TABLE_REF)
            print("Table dropped for full refresh.")
        except Exception:
            pass

    ensure_table_exists(client)
    migrate_schema(client)

    empty = is_table_empty(client)
    seed_rows = []
    if empty:
        print("Table is empty — collecting seed rows from seedPrepayment.xlsx...")
        seed_rows = build_seed_rows(client)
        print(f"Collected {len(seed_rows)} seed rows.")

    existing_keys = get_existing_line_item_keys(client)
    print(f"{len(existing_keys)} existing line-item keys already in BQ.")

    txns = fetch_bank_transactions(access_token, tenant_id)
    print(f"Fetched {len(txns)} bank transactions from Xero (from {SYNC_FROM_DATE}).")

    new_rows = list(seed_rows)
    manual_review_refs = []

    for txn in txns:
        txn_id = txn.get("BankTransactionID")
        txn_type = txn.get("Type", "SPEND")
        txn_date_raw = txn.get("Date", "")
        txn_date = parse_xero_date(txn_date_raw) if txn_date_raw else None
        line_items = txn.get("LineItems", [])

        for li_idx, li in enumerate(line_items):
            if li.get("AccountCode") != ACCOUNT_CODE:
                continue
            if (txn_id, li_idx) in existing_keys:
                continue

            description = li.get("Description") or ""
            line_amount = li.get("LineAmount") or li.get("UnitAmount") or 0
            aud_amount = abs(float(line_amount)) if line_amount else None
            parsed = parse_reference(description, line_amount)

            if parsed:
                row = {
                    "xeroTransactionID": txn_id,
                    "lineItemIndex": li_idx,
                    "poNumber": parsed["poNumber"],
                    "type": parsed["type"],
                    "supplier": parsed["supplier"],
                    "date": txn_date,
                    "currencyRate": parsed["currencyRate"],
                    "usdAmount": parsed["usdAmount"],
                    "audAmount": aud_amount,
                    "transactionType": txn_type,
                    "rawReference": description,
                    "parseStatus": "OK",
                    "allocatedDate": None,
                    "syncedAt": datetime.now(timezone.utc).isoformat(),
                }
            else:
                manual_review_refs.append(description)
                row = {
                    "xeroTransactionID": txn_id,
                    "lineItemIndex": li_idx,
                    "poNumber": None,
                    "type": None,
                    "supplier": None,
                    "date": txn_date,
                    "currencyRate": None,
                    "usdAmount": None,
                    "audAmount": aud_amount,
                    "transactionType": txn_type,
                    "rawReference": description,
                    "parseStatus": "MANUAL_REVIEW",
                    "allocatedDate": None,
                    "syncedAt": datetime.now(timezone.utc).isoformat(),
                }

            new_rows.append(row)

    xero_rows = [r for r in new_rows if r not in seed_rows]
    if new_rows:
        df = pd.DataFrame(new_rows)
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        df["allocatedDate"] = pd.to_datetime(df["allocatedDate"], errors="coerce").dt.date
        df["syncedAt"] = pd.to_datetime(df["syncedAt"], errors="coerce", utc=True)
        job = client.load_table_from_dataframe(
            df, TABLE_REF,
            job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND")
        )
        job.result()
        if seed_rows:
            print(f"Seeded {len(seed_rows)} rows from seedPrepayment.xlsx.")
        ok_count = sum(1 for r in xero_rows if r["parseStatus"] == "OK")
        if xero_rows:
            print(f"Inserted {len(xero_rows)} Xero rows ({ok_count} OK, {len(manual_review_refs)} MANUAL_REVIEW).")
    else:
        print("No new rows to insert.")

    if manual_review_refs:
        print(f"\nManual review needed for {len(manual_review_refs)} references:")
        for ref in manual_review_refs:
            print(f"  - {ref}")

    sync_allocations_from_xero(client, access_token, tenant_id)

    print("syncPO complete.")


if __name__ == "__main__":
    main()
