"""
Fix a MANUAL_REVIEW row in h2dataservices.finance.supplierPrepayments.

Usage:
    python fixRow.py --list
    python fixRow.py <xeroTransactionID> <lineItemIndex> <poNumber> <type> <usdAmount> <audAmount> [supplier]

Arguments:
    xeroTransactionID   Xero BankTransaction ID (from --list output)
    lineItemIndex       Line item index (from --list output)
    poNumber            PO number to set (e.g. 5273)
    type                DP or FP
    usdAmount           USD amount (e.g. 9752)
    audAmount           AUD amount from the original bank transaction (e.g. 13842.50)
    supplier            Optional supplier name

Example:
    python fixRow.py abc-123-def 0 5273 DP 9752 13842.50 "Thaicoco"
"""
import sys
import os
import re
import json
from google.cloud import bigquery
from google.oauth2 import service_account
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = "h2dataservices"
TABLE_REF = f"{PROJECT_ID}.finance.supplierPrepayments"


def read_env_json(var_name):
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


def list_manual_review(client):
    rows = list(client.query(f"""
        SELECT xeroTransactionID, lineItemIndex, rawReference, audAmount, usdAmount, date
        FROM `{TABLE_REF}`
        WHERE parseStatus = 'MANUAL_REVIEW'
        ORDER BY date DESC
    """).result())

    if not rows:
        print("No MANUAL_REVIEW rows found.")
        return

    print(f"{'xeroTransactionID':<40} {'li':>3}  {'date':<12}  {'audAmount':>10}  rawReference")
    print("-" * 110)
    for r in rows:
        print(f"{r.xeroTransactionID:<40} {r.lineItemIndex:>3}  {str(r.date):<12}  {(r.audAmount or 0):>10.2f}  {r.rawReference}")


def fix_row(client, txn_id, li_idx, po_number, payment_type, usd_amount, aud_amount, supplier=None):
    payment_type = payment_type.upper()
    if payment_type not in ("DP", "FP"):
        print(f"Invalid type '{payment_type}' — must be DP or FP.")
        sys.exit(1)

    rows = list(client.query(f"""
        SELECT * FROM `{TABLE_REF}`
        WHERE xeroTransactionID = '{txn_id}' AND lineItemIndex = {li_idx}
    """).result())

    if not rows:
        print(f"No row found for xeroTransactionID={txn_id} lineItemIndex={li_idx}")
        sys.exit(1)

    row = rows[0]
    print("Current row:")
    print(f"  rawReference : {row.rawReference}")
    print(f"  parseStatus  : {row.parseStatus}")
    print(f"  poNumber     : {row.poNumber}")
    print(f"  type         : {row.type}")
    print(f"  usdAmount    : {row.usdAmount}")
    print(f"  audAmount    : {row.audAmount}")
    print(f"  currencyRate : {row.currencyRate}")
    print(f"  supplier     : {row.supplier}")
    print()

    currency_rate = round(usd_amount / aud_amount, 6)
    supplier_clause = f"supplier = '{supplier}'," if supplier else ""

    client.query(f"""
        UPDATE `{TABLE_REF}`
        SET poNumber = '{po_number}',
            type = '{payment_type}',
            usdAmount = {usd_amount},
            audAmount = {aud_amount},
            currencyRate = {currency_rate},
            {supplier_clause}
            parseStatus = 'OK'
        WHERE xeroTransactionID = '{txn_id}' AND lineItemIndex = {li_idx}
    """).result()

    print(f"Updated: PO{po_number} {payment_type} USD {usd_amount} / AUD {aud_amount} (rate {currency_rate})" + (f" | {supplier}" if supplier else ""))


def main():
    client = get_bq_client()

    if len(sys.argv) == 1 or sys.argv[1] == "--list":
        list_manual_review(client)
        return

    if len(sys.argv) < 7:
        print(__doc__)
        sys.exit(1)

    txn_id = sys.argv[1]
    li_idx = int(sys.argv[2])
    po_number = sys.argv[3]
    payment_type = sys.argv[4]
    usd_amount = float(sys.argv[5])
    aud_amount = float(sys.argv[6])
    supplier = sys.argv[7] if len(sys.argv) > 7 else None

    fix_row(client, txn_id, li_idx, po_number, payment_type, usd_amount, aud_amount, supplier)


if __name__ == "__main__":
    main()
