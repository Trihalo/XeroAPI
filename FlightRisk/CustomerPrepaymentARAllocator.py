import sys
import os
import requests
import logging
import csv
import argparse
import time
import pandas as pd
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from helpers.fetchInvoicesForClient import fetchInvoicesForClient
from helpers.emailAttachment import sendEmail

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

PREPAYMENT_ACCOUNT_CODE = "2010"
PAYMENT_URL = "https://api.xero.com/api.xro/2.0/Payments"
CLIENT = "FLIGHT_RISK"


def write_allocated_csv(output_dir, rows, dry_run=False):
    filename = "prepayment_allocations_dry_run.csv" if dry_run else "prepayment_allocations.csv"
    file_path = os.path.join(output_dir, filename)
    with open(file_path, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["SalesOrderNumber", "InvoiceDate", "AmountAllocated", "PaymentDate", "Status"])
        writer.writerows(rows)
    logging.info(f"Allocated payments written to {file_path}")
    return file_path


def write_unapplied_csv(output_dir, rows):
    file_path = os.path.join(output_dir, "prepayment_unapplied.csv")
    with open(file_path, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["SalesOrderNumber", "PrepaymentAmount", "Reason"])
        writer.writerows(rows)
    logging.info(f"Unapplied prepayments written to {file_path}")
    return file_path


def build_email_html(recipient_name, allocated, unapplied, dry_run=False):
    mode_badge = (
        '<span style="background:#f59e0b;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;">DRY RUN</span>'
        if dry_run else ""
    )
    run_date = datetime.now().strftime("%d %b %Y")

    def table_rows(rows, cols):
        if not rows:
            return f'<tr><td colspan="{len(cols)}" style="text-align:center;color:#6b7280;padding:12px;">None</td></tr>'
        return "".join(
            "<tr>" + "".join(f'<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;">{c}</td>' for c in row) + "</tr>"
            for row in rows
        )

    allocated_display = [
        (r[0], f"${float(r[2]):,.2f}", r[3])
        for r in allocated
    ]
    unapplied_display = [
        (r[0], f"${float(r[1]):,.2f}" if r[1] != "" else "N/A", r[2])
        for r in unapplied
    ]

    def header_row(cols):
        return "<tr>" + "".join(
            f'<th style="padding:8px 12px;background:#f3f4f6;text-align:left;font-weight:600;">{c}</th>'
            for c in cols
        ) + "</tr>"

    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#111827;max-width:680px;margin:0 auto;padding:24px;">
      <h2 style="margin-bottom:4px;">Customer Prepayment AR Allocator {mode_badge}</h2>
      <p style="color:#6b7280;margin-top:0;">{run_date}</p>
      <p>Hi {recipient_name},</p>
      <p>The prepayment allocation run has completed. Please find the summary below and the full CSV reports attached.</p>

      <div style="display:flex;gap:16px;margin:20px 0;">
        <div style="flex:1;background:#d1fae5;border-radius:8px;padding:16px;text-align:center;">
          <div style="font-size:32px;font-weight:700;color:#065f46;">{len(allocated)}</div>
          <div style="color:#065f46;font-weight:600;">Allocated</div>
        </div>
        <div style="flex:1;background:#fee2e2;border-radius:8px;padding:16px;text-align:center;">
          <div style="font-size:32px;font-weight:700;color:#991b1b;">{len(unapplied)}</div>
          <div style="color:#991b1b;font-weight:600;">Unapplied</div>
        </div>
      </div>

      <h3 style="margin-bottom:8px;">Allocated Payments</h3>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        {header_row(["Sales Order", "Amount", "Payment Date"])}
        {table_rows(allocated_display, ["Sales Order", "Amount", "Payment Date"])}
      </table>

      <h3 style="margin-bottom:8px;margin-top:24px;">Unapplied Prepayments</h3>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        {header_row(["Sales Order", "Prepayment Amount", "Reason"])}
        {table_rows(unapplied_display, ["Sales Order", "Prepayment Amount", "Reason"])}
      </table>

      {"<p style='background:#fef3c7;border-left:4px solid #f59e0b;padding:10px 14px;margin-top:20px;'><strong>Note:</strong> This was a dry run. No payments were allocated in Xero.</p>" if dry_run else ""}
      <p style="margin-top:24px;color:#6b7280;font-size:13px;">This email was generated automatically by the FlightRisk Prepayment AR Allocator.</p>
    </body></html>
    """


def send_results_email(recipient_name, recipient_email, allocated, unapplied, attachments, dry_run=False):
    mode = " [DRY RUN]" if dry_run else ""
    subject = f"FlightRisk Prepayment Allocation Report{mode}"
    body_text = (
        f"Hi {recipient_name},\n\n"
        f"Prepayment allocation complete: {len(allocated)} allocated, {len(unapplied)} unapplied.\n"
        "Please see the attached CSV files for full details.\n\n"
        "This email was generated automatically."
    )
    body_html = build_email_html(recipient_name, allocated, unapplied, dry_run)

    try:
        sendEmail(
            recipients=[recipient_email],
            subject=subject,
            body_text=body_text,
            provider="GMAIL",
            body_html=body_html,
            attachments=attachments,
        )
    except Exception as e:
        logging.error(f"Failed to send results email: {e}")


def write_github_summary(allocated, unapplied, dry_run=False):
    """Write a markdown summary to the GitHub Actions job summary page."""
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return

    mode = " (DRY RUN)" if dry_run else ""
    with open(summary_file, "a") as f:
        f.write(f"## Customer Prepayment AR Allocator{mode}\n\n")

        f.write(f"### ✅ Allocated: {len(allocated)}\n\n")
        if allocated:
            f.write("| Sales Order | Amount Allocated | Payment Date |\n")
            f.write("|---|---|---|\n")
            for row in allocated:
                f.write(f"| {row[0]} | ${float(row[2]):,.2f} | {row[3]} |\n")
        else:
            f.write("_No payments allocated._\n")

        f.write(f"\n### ⚠️ Unapplied: {len(unapplied)}\n\n")
        if unapplied:
            f.write("| Sales Order | Prepayment Amount | Reason |\n")
            f.write("|---|---|---|\n")
            for row in unapplied:
                amount = f"${float(row[1]):,.2f}" if row[1] != "" else "N/A"
                f.write(f"| {row[0]} | {amount} | {row[2]} |\n")
        else:
            f.write("_All prepayments were applied._\n")


def main():
    parser = argparse.ArgumentParser(description="Allocate customer prepayments to AR invoices in Xero.")
    parser.add_argument("--dry-run", action="store_true", help="Run without making actual API calls")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of rows to process")
    parser.add_argument("--output-dir", type=str, default=None, help="Directory for output CSV files (default: script directory)")
    parser.add_argument("--name", type=str, default=None, help="Recipient name for the results email")
    parser.add_argument("--email", type=str, default=None, help="Recipient email address for the results email")
    args = parser.parse_args()

    dry_run = args.dry_run
    output_dir = args.output_dir or os.path.dirname(os.path.abspath(__file__))
    recipient_name = args.name
    recipient_email = args.email
    os.makedirs(output_dir, exist_ok=True)

    if dry_run:
        logging.info("DRY-RUN MODE — no payments will be allocated.")

    # 1. Load Excel
    excel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CustomerPrepayment.xlsx")
    if not os.path.exists(excel_path):
        logging.error(f"Excel file not found: {excel_path}")
        return

    logging.info(f"Reading {excel_path}...")
    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        logging.error(f"Failed to read Excel file: {e}")
        return

    df.columns = [c.strip() for c in df.columns]
    required_cols = ["Sales Order Number", "Prepayment $"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        logging.error(f"Missing required columns: {missing}. Found: {df.columns.tolist()}")
        return

    # 2. Fetch Xero invoices
    logging.info(f"Fetching AUTHORISED invoices for {CLIENT}...")
    try:
        invoices_list, access_token, xero_tenant_id = fetchInvoicesForClient(CLIENT, "AUTHORISED")
    except Exception as e:
        logging.error(f"Error fetching invoices: {e}")
        return

    invoices_map = {
        inv["InvoiceNumber"]: inv
        for inv in invoices_list
        if inv.get("Type") == "ACCREC" and inv.get("InvoiceNumber")
    }
    logging.info(f"Fetched {len(invoices_map)} ACCREC invoices.")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": xero_tenant_id,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # 3. Process rows
    rows_to_process = df.iloc[: args.limit] if args.limit else df
    allocated_rows = []
    unapplied_rows = []

    for index, row in rows_to_process.iterrows():
        row_num = index + 2
        sales_order = str(row["Sales Order Number"]).strip()

        try:
            prepayment_amount = float(row["Prepayment $"])
        except (ValueError, TypeError):
            logging.warning(f"Row {row_num}: {sales_order} — invalid prepayment amount '{row['Prepayment $']}', skipping.")
            unapplied_rows.append((sales_order, "", "Invalid prepayment amount"))
            continue

        if prepayment_amount <= 0:
            logging.info(f"Row {row_num}: {sales_order} — prepayment is {prepayment_amount}, skipping.")
            continue

        invoice = invoices_map.get(sales_order)
        if not invoice:
            logging.info(f"Row {row_num}: {sales_order} — not found in Xero as AUTHORISED ACCREC, skipping.")
            unapplied_rows.append((sales_order, prepayment_amount, "Invoice not found in Xero"))
            continue

        amount_due = float(invoice.get("AmountDue", 0))
        amount_paid = float(invoice.get("AmountPaid", 0))
        invoice_id = invoice["InvoiceID"]
        date_str = invoice.get("DateString", "")

        if amount_paid > 0:
            logging.info(f"Row {row_num}: {sales_order} — already has payment (AmountPaid: {amount_paid}), skipping.")
            unapplied_rows.append((sales_order, prepayment_amount, f"Already has payment of {amount_paid}"))
            continue

        if amount_due <= 0:
            logging.info(f"Row {row_num}: {sales_order} — fully paid (AmountDue: {amount_due}), skipping.")
            unapplied_rows.append((sales_order, prepayment_amount, "Invoice fully paid"))
            continue

        if prepayment_amount > amount_due:
            logging.warning(f"Row {row_num}: {sales_order} — prepayment ({prepayment_amount}) exceeds amount due ({amount_due}), skipping.")
            unapplied_rows.append((sales_order, prepayment_amount, f"Prepayment exceeds amount due ({amount_due})"))
            continue

        if not date_str:
            logging.warning(f"Row {row_num}: {sales_order} — missing DateString, skipping.")
            unapplied_rows.append((sales_order, prepayment_amount, "Missing invoice date"))
            continue

        payment_date = date_str.split("T")[0]
        logging.info(f"Row {row_num}: Allocating ${prepayment_amount:,.2f} to {sales_order} (payment date: {payment_date})")

        if not dry_run:
            payload = {
                "Payments": [{
                    "Invoice": {"InvoiceID": invoice_id},
                    "Account": {"Code": PREPAYMENT_ACCOUNT_CODE},
                    "Date": payment_date,
                    "Amount": prepayment_amount,
                    "Reference": f"{sales_order} {payment_date}",
                }]
            }
            try:
                response = requests.put(PAYMENT_URL, headers=headers, json=payload)
                if response.status_code in [200, 201]:
                    logging.info(f"  [SUCCESS] Payment allocated for {sales_order}")
                else:
                    logging.error(f"  [FAILED] {sales_order} — HTTP {response.status_code}: {response.text}")
                    unapplied_rows.append((sales_order, prepayment_amount, f"API error {response.status_code}"))
                    continue
            except Exception as e:
                logging.error(f"  [ERROR] {sales_order}: {e}")
                unapplied_rows.append((sales_order, prepayment_amount, f"Exception: {e}"))
                continue
            time.sleep(1.1)

        status = "DRY_RUN" if dry_run else "ALLOCATED"
        allocated_rows.append((sales_order, payment_date, prepayment_amount, payment_date, status))

    # 4. Write output files
    allocated_file = write_allocated_csv(output_dir, allocated_rows, dry_run)
    unapplied_file = write_unapplied_csv(output_dir, unapplied_rows)
    write_github_summary(allocated_rows, unapplied_rows, dry_run)

    # 5. Email results if recipient provided
    if recipient_email:
        send_results_email(
            recipient_name=recipient_name or recipient_email,
            recipient_email=recipient_email,
            allocated=allocated_rows,
            unapplied=unapplied_rows,
            attachments=[allocated_file, unapplied_file],
            dry_run=dry_run,
        )

    logging.info(f"Done — {len(allocated_rows)} allocated, {len(unapplied_rows)} unapplied.")


if __name__ == "__main__":
    main()
