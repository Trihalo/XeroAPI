import sys
import os
import re
import json
from datetime import datetime
from google.cloud import bigquery
from google.oauth2 import service_account
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from helpers.emailAttachment import sendEmail

PROJECT_ID = "h2dataservices"
SP_TABLE = f"{PROJECT_ID}.finance.supplierPrepayments"
STALE_THRESHOLD_DAYS = 60
ALERT_RECIPIENT = "leoshi@h2coconut.com"


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
    return bigquery.Client(credentials=credentials, project=PROJECT_ID)


def query_stale_prepayments(client):
    query = f"""
        SELECT
            COALESCE(supplier, '(unknown)') AS supplier,
            poNumber,
            COALESCE(type, '?') AS type,
            usdAmount,
            date,
            DATE_DIFF(CURRENT_DATE(), date, DAY) AS daysOutstanding
        FROM `{SP_TABLE}`
        WHERE parseStatus = 'OK'
          AND transactionType = 'SPEND'
          AND allocatedDate IS NULL
          AND date < DATE_SUB(CURRENT_DATE(), INTERVAL {STALE_THRESHOLD_DAYS} DAY)
        ORDER BY daysOutstanding DESC
    """
    return list(client.query(query).result())


def build_html_table(rows):
    headers = ["Supplier", "PO Number", "Type", "USD Amount", "Date", "Days Outstanding"]
    header_row = "".join(f"<th style='padding:8px 12px;text-align:left;border-bottom:2px solid #ddd;'>{h}</th>" for h in headers)

    data_rows = ""
    for i, row in enumerate(rows):
        bg = "#f9f9f9" if i % 2 == 0 else "#ffffff"
        cells = [
            row.supplier,
            row.poNumber,
            row.type,
            f"${row.usdAmount:,.2f}" if row.usdAmount else "-",
            str(row.date),
            str(row.daysOutstanding),
        ]
        data_rows += f"<tr style='background:{bg};'>" + "".join(
            f"<td style='padding:8px 12px;border-bottom:1px solid #eee;'>{c}</td>" for c in cells
        ) + "</tr>"

    return f"""
    <table style='border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px;width:100%;'>
        <thead><tr style='background:#f0f0f0;'>{header_row}</tr></thead>
        <tbody>{data_rows}</tbody>
    </table>
    """


def main():
    print("Running stale prepayment alert...")
    client = get_bq_client()
    rows = query_stale_prepayments(client)

    if not rows:
        print(f"No prepayments outstanding for more than {STALE_THRESHOLD_DAYS} days. No email sent.")
        return

    print(f"Found {len(rows)} stale prepayment(s). Sending alert to {ALERT_RECIPIENT}.")

    table_html = build_html_table(rows)
    today = datetime.now().strftime("%d %b %Y")

    body_html = f"""
    <html><body>
    <p>Hi,</p>
    <p>The following supplier prepayments (account 2010) have been outstanding for more than
    <strong>{STALE_THRESHOLD_DAYS} days</strong> as of <strong>{today}</strong>:</p>
    {table_html}
    <p style='margin-top:16px;color:#666;font-size:12px;'>
        This is an automated alert from the H2coco Supplier Prepayment system.
    </p>
    </body></html>
    """

    body_text = f"Stale prepayment alert ({today}): {len(rows)} PO(s) outstanding for more than {STALE_THRESHOLD_DAYS} days.\n\n"
    for row in rows:
        body_text += f"  PO{row.poNumber} | {row.supplier} | {row.type} | USD {row.usdAmount:,.2f} | {row.date} | {row.daysOutstanding} days\n"

    sendEmail(
        recipients=ALERT_RECIPIENT,
        subject=f"[H2coco] Stale Prepayments Alert — {len(rows)} PO(s) outstanding ({today})",
        body_text=body_text,
        provider="GMAIL",
        body_html=body_html,
    )

    print("Alert email sent.")


if __name__ == "__main__":
    main()
