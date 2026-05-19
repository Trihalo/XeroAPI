"""
BigQuery upsert helper for warehouse invoice charges.

Project:  H2DataServices
Dataset:  distribution
Table:    warehouse_charges

Deduplication: delete-by-invoice_no then insert.
  Re-processing the same invoice replaces it cleanly — no duplicates.
"""

import os
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

PROJECT_ID = "h2dataservices"
DATASET_ID = "distribution"
TABLE_ID   = "warehouse_charges"
TABLE_REF  = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

# Column rename: CSV header → BigQuery column name
_COL_RENAME = {
    "Invoice No":              "invoice_no",
    "Invoice Date":            "invoice_date",
    "Due Date":                "due_date",
    "Transport":               "transport",
    "Period Month":            "period_month",
    "Period Year":             "period_year",
    "State":                   "state",
    "Activity Period":         "activity_period",
    "Description":             "description",
    "Details":                 "details",
    "Qty":                     "qty",
    "Rate":                    "rate",
    "GST Y/N":                 "gst_yn",
    "Amount (Ex GST)":         "amount_ex_gst",
    "GST":                     "gst_amount",
    "Amount (Inc GST)":        "amount_inc_gst",
    "Container Numbers":       "container_numbers",
    "Invoice Total (Ex GST)":  "invoice_total_ex_gst",
    "Invoice Total (Inc GST)": "invoice_total_inc_gst",
}

_SCHEMA = [
    bigquery.SchemaField("invoice_no",              "STRING"),
    bigquery.SchemaField("invoice_date",            "DATE"),
    bigquery.SchemaField("due_date",                "DATE"),
    bigquery.SchemaField("transport",               "STRING"),
    bigquery.SchemaField("period_month",            "STRING"),
    bigquery.SchemaField("period_year",             "INTEGER"),
    bigquery.SchemaField("state",                   "STRING"),
    bigquery.SchemaField("activity_period",         "STRING"),
    bigquery.SchemaField("description",             "STRING"),
    bigquery.SchemaField("details",                 "STRING"),
    bigquery.SchemaField("qty",                     "FLOAT"),
    bigquery.SchemaField("rate",                    "FLOAT"),
    bigquery.SchemaField("gst_yn",                  "STRING"),
    bigquery.SchemaField("amount_ex_gst",           "FLOAT"),
    bigquery.SchemaField("gst_amount",              "FLOAT"),
    bigquery.SchemaField("amount_inc_gst",          "FLOAT"),
    bigquery.SchemaField("container_numbers",       "STRING"),
    bigquery.SchemaField("invoice_total_ex_gst",    "FLOAT"),
    bigquery.SchemaField("invoice_total_inc_gst",   "FLOAT"),
]


def _get_client():
    key_path = os.getenv("H2DATASERVICES_BQACCESS")
    if not key_path:
        raise EnvironmentError("H2DATASERVICES_BQACCESS environment variable is not set.")
    credentials = service_account.Credentials.from_service_account_file(
        key_path,
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )
    return bigquery.Client(credentials=credentials, project=PROJECT_ID)


def _prepare_df(rows):
    """Rename columns, cast types, and sanitise NaNs."""
    df = pd.DataFrame(rows) if not isinstance(rows, pd.DataFrame) else rows.copy()
    df = df.rename(columns=_COL_RENAME)

    # Keep only schema columns; ignore extras
    schema_cols = [f.name for f in _SCHEMA]
    df = df[[c for c in schema_cols if c in df.columns]]

    # Date columns
    for col in ("invoice_date", "due_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format="%d-%b-%y", errors="coerce").dt.date

    # Numeric coercions
    if "period_year" in df.columns:
        df["period_year"] = pd.to_numeric(df["period_year"], errors="coerce").astype("Int64")
    for col in ("qty", "rate", "amount_ex_gst", "gst_amount", "amount_inc_gst",
                "invoice_total_ex_gst", "invoice_total_inc_gst"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Replace NaN / NaT with None so BigQuery accepts them
    df = df.where(pd.notnull(df), None)

    return df


def ensure_table_exists(client):
    """Create the table if it doesn't already exist."""
    dataset_ref = client.dataset(DATASET_ID)
    table_ref   = dataset_ref.table(TABLE_ID)
    try:
        client.get_table(table_ref)
    except Exception:
        table = bigquery.Table(table_ref, schema=_SCHEMA)
        client.create_table(table)
        print(f"  Created table {TABLE_REF}")


def upsert_to_bigquery(rows):
    """
    Delete existing rows for the affected invoice numbers, then insert fresh rows.
    Safe to re-run — will not produce duplicates.
    """
    if not rows:
        print("  No rows to upsert.")
        return

    df = _prepare_df(rows)
    if df.empty:
        print("  DataFrame is empty after preparation.")
        return

    client = _get_client()
    ensure_table_exists(client)

    # Delete existing rows for all invoice numbers in this batch
    invoice_nos = df["invoice_no"].dropna().unique().tolist()
    if invoice_nos:
        placeholders = ", ".join(f"'{n}'" for n in invoice_nos)
        client.query(
            f"DELETE FROM `{TABLE_REF}` WHERE invoice_no IN ({placeholders})"
        ).result()
        print(f"  Deleted existing rows for {len(invoice_nos)} invoice(s).")

    # Insert
    job_config = bigquery.LoadJobConfig(
        schema        = _SCHEMA,
        write_disposition = bigquery.WriteDisposition.WRITE_APPEND,
    )
    job = client.load_table_from_dataframe(df, TABLE_REF, job_config=job_config)
    job.result()
    print(f"  Inserted {len(df)} row(s) into {TABLE_REF}.")
