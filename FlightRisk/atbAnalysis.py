import os
import sys
import pandas as pd
from datetime import date, datetime
from google.cloud import bigquery

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def buildLineItemsText(line_items):
    parts = []
    for line in line_items:
        qty = float(line.get("Quantity", 0) or 0)
        if qty == 0:
            continue
        description = line.get("Description", "").strip()
        unit_amount = float(line.get("UnitAmount", 0) or 0)
        parts.append(f"{description} | Qty: {qty:g} | ${unit_amount:.2f}")
    return "; ".join(parts)


def buildAtbRows(invoices):
    rows = []
    for invoice in invoices:
        if not (isinstance(invoice, dict) and invoice.get("Type") == "ACCREC"):
            continue

        try:
            invoice_date = datetime.strptime(invoice["DateString"], "%Y-%m-%dT%H:%M:%S").date()
            due_date = datetime.strptime(invoice["DueDateString"], "%Y-%m-%dT%H:%M:%S").date()
        except (KeyError, ValueError):
            continue

        rows.append({
            "InvoiceNumber": invoice.get("InvoiceNumber", ""),
            "Contact": invoice.get("Contact", {}).get("Name", ""),
            "InvoiceDate": invoice_date,
            "DueDate": due_date,
            "Total": float(invoice.get("Total", 0) or 0),
            "AmountPaid": float(invoice.get("AmountPaid", 0) or 0),
            "AmountDue": float(invoice.get("AmountDue", 0) or 0),
            "LineItems": buildLineItemsText(invoice.get("LineItems", [])),
        })
    return rows


def writeGithubSummary(df, table_ref):
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")

    today = date.today()
    df = df.copy()
    df["DaysOutstanding"] = df["InvoiceDate"].apply(lambda d: (today - d).days)

    def bucket(days):
        if days <= 30:   return "0–30 days (1 month)"
        if days <= 60:   return "31–60 days (2 months)"
        if days <= 90:   return "61–90 days (3 months)"
        if days <= 120:  return "91–120 days (4 months)"
        return "> 120 days (4+ months)"

    order = [
        "0–30 days (1 month)",
        "31–60 days (2 months)",
        "61–90 days (3 months)",
        "91–120 days (4 months)",
        "> 120 days (4+ months)",
    ]

    df["AgeBucket"] = df["DaysOutstanding"].apply(bucket)
    aging = df.groupby("AgeBucket")["AmountDue"].sum().reindex(order, fill_value=0)

    lines = [
        "## FlightRisk ATB Report\n",
        f"**Invoices uploaded:** {len(df)}  ",
        f"**Total outstanding:** ${df['AmountDue'].sum():,.2f}  ",
        f"**BigQuery table:** `{table_ref}`\n",
        "### Aged Receivables\n",
        "| Age Bracket | Amount Outstanding |",
        "| --- | --- |",
    ]
    for bracket, amount in aging.items():
        lines.append(f"| {bracket} | ${amount:,.2f} |")

    output = "\n".join(lines) + "\n"
    print(output)  # Always print to console

    if summary_file:
        with open(summary_file, "a") as f:
            f.write(output)


def exportAtbData(invoices):
    """Local testing mode: export to Excel instead of uploading to BigQuery."""
    rows = buildAtbRows(invoices)
    df = pd.DataFrame(rows)
    output_path = os.path.join(os.path.dirname(__file__), "ATB_Local_Export.xlsx")
    df.to_excel(output_path, index=False)
    print(f"Exported {len(df)} rows to {output_path}")
    return output_path


def processAtbData(invoices):
    rows = buildAtbRows(invoices)
    df = pd.DataFrame(rows)

    project_id = os.getenv("FLIGHT_RISK_BQ_PROJECT", "flight-risk-485101")
    dataset_id = "InvoiceData"
    table_id = "ATBEnquiry"
    table_ref = f"{project_id}.{dataset_id}.{table_id}"

    # ADC picks up WIF credentials automatically in GitHub Actions
    client = bigquery.Client(project=project_id)

    # Clear existing rows without dropping the table (skip if table doesn't exist yet)
    try:
        client.query(f"DELETE FROM `{table_ref}` WHERE TRUE").result()
        print(f"Cleared existing rows in {table_ref}")
    except Exception:
        pass  # Table doesn't exist yet; first upload will create it

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True,
    )
    client.load_table_from_dataframe(df, table_ref, job_config=job_config).result()

    print(f"Uploaded {len(df)} rows to {table_ref}")
    writeGithubSummary(df, table_ref)
    return table_ref
