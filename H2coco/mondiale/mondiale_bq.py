"""
BigQuery upsert helper for Mondiale/AFER freight invoice charges.

Project:  H2DataServices
Dataset:  distribution
Table:    freight_charges

Deduplication: delete-by-invoice_no then insert.
  Re-processing the same invoice replaces it cleanly — no duplicates.
"""

import os
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

PROJECT_ID = "h2dataservices"
DATASET_ID = "distribution"
TABLE_ID   = "freight_charges"
TABLE_REF  = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"


def normalize_invoice_no(value):
    """Canonical form for invoice_no comparisons: strip whitespace, uppercase.
    Returns None if value is None/empty/NaN."""
    if value is None:
        return None
    try:
        s = str(value).strip().upper()
    except Exception:
        return None
    return s or None

_COL_RENAME = {
    "Source":                   "source",
    "Invoice No":               "invoice_no",
    "Date":                     "invoice_date",
    "Due Date":                 "due_date",
    "Shipment":                 "shipment",
    "Consol":                   "consol",
    "PO":                       "po",
    "Containers":               "containers",
    "Consignor":                "consignor",
    "Origin":                   "origin",
    "Destination":              "destination",
    "ETA":                      "eta",
    "Total Pkgs":               "total_pkgs",
    "Charge Code":              "charge_code",
    "Description":              "description",
    "Standardised Description": "standardised_description",
    "Details":                  "details",
    "Qty":                      "qty",
    "Currency":                 "currency",
    "Rate":                     "rate",
    "Conversion Rate":          "conversion_rate",
    "GST Y/N":                  "gst_yn",
    "Amount (Ex GST)":          "amount_ex_gst",
    "GST":                      "gst_amount",
    "Amount (Inc GST)":         "amount_inc_gst",
    "Invoice Total (Ex GST)":   "invoice_total_ex_gst",
    "Invoice Total (Inc GST)":  "invoice_total_inc_gst",
}

_SCHEMA = [
    bigquery.SchemaField("source",                   "STRING"),
    bigquery.SchemaField("invoice_no",               "STRING"),
    bigquery.SchemaField("invoice_date",             "DATE"),
    bigquery.SchemaField("due_date",                 "DATE"),
    bigquery.SchemaField("shipment",                 "STRING"),
    bigquery.SchemaField("consol",                   "STRING"),
    bigquery.SchemaField("po",                       "STRING"),
    bigquery.SchemaField("containers",               "STRING"),
    bigquery.SchemaField("consignor",                "STRING"),
    bigquery.SchemaField("origin",                   "STRING"),
    bigquery.SchemaField("destination",              "STRING"),
    bigquery.SchemaField("eta",                      "DATE"),
    bigquery.SchemaField("total_pkgs",               "INTEGER"),
    bigquery.SchemaField("charge_code",              "STRING"),
    bigquery.SchemaField("description",              "STRING"),
    bigquery.SchemaField("standardised_description", "STRING"),
    bigquery.SchemaField("details",                  "STRING"),
    bigquery.SchemaField("qty",                      "FLOAT"),
    bigquery.SchemaField("currency",                 "STRING"),
    bigquery.SchemaField("rate",                     "FLOAT"),
    bigquery.SchemaField("conversion_rate",          "FLOAT"),
    bigquery.SchemaField("gst_yn",                   "STRING"),
    bigquery.SchemaField("amount_ex_gst",            "FLOAT"),
    bigquery.SchemaField("gst_amount",               "FLOAT"),
    bigquery.SchemaField("amount_inc_gst",           "FLOAT"),
    bigquery.SchemaField("invoice_total_ex_gst",     "FLOAT"),
    bigquery.SchemaField("invoice_total_inc_gst",    "FLOAT"),
]


def _get_client():
    key_path = os.getenv("H2DATASERVICES_BQACCESS")
    if not key_path:
        raise EnvironmentError("H2COCO_BQACCESS environment variable is not set.")
    credentials = service_account.Credentials.from_service_account_file(
        key_path,
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )
    return bigquery.Client(credentials=credentials, project=PROJECT_ID)


def _prepare_df(rows):
    df = pd.DataFrame(rows) if not isinstance(rows, pd.DataFrame) else rows.copy()
    df = df.rename(columns=_COL_RENAME)

    schema_cols = [f.name for f in _SCHEMA]
    df = df[[c for c in schema_cols if c in df.columns]]

    if "invoice_no" in df.columns:
        df["invoice_no"] = df["invoice_no"].map(normalize_invoice_no)

    for col in ("invoice_date", "due_date", "eta"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format="%d-%b-%y", errors="coerce").dt.date

    if "total_pkgs" in df.columns:
        df["total_pkgs"] = pd.to_numeric(df["total_pkgs"], errors="coerce").astype("Int64")

    for col in ("qty", "rate", "conversion_rate", "amount_ex_gst", "gst_amount",
                "amount_inc_gst", "invoice_total_ex_gst", "invoice_total_inc_gst"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.where(pd.notnull(df), None)
    return df


def ensure_table_exists(client):
    dataset_ref = client.dataset(DATASET_ID)
    table_ref   = dataset_ref.table(TABLE_ID)
    try:
        client.get_table(table_ref)
    except Exception:
        table = bigquery.Table(table_ref, schema=_SCHEMA)
        client.create_table(table)
        print(f"  Created table {TABLE_REF}")


def truncate_from_date(from_date):
    """Delete all rows from freight_charges where invoice_date >= from_date.

    Returns the number of rows deleted. from_date should be 'YYYY-MM-DD'."""
    client = _get_client()
    ensure_table_exists(client)
    job = client.query(
        f"DELETE FROM `{TABLE_REF}` WHERE invoice_date >= DATE('{from_date}')"
    )
    job.result()
    return job.num_dml_affected_rows or 0


def load_existing_invoice_numbers():
    """Return set of normalized invoice_no values already in BigQuery.

    Raises if the query fails — silent empty-set returns previously masked auth
    and query errors, causing every invoice to be re-processed."""
    client = _get_client()
    ensure_table_exists(client)
    rows = client.query(f"SELECT DISTINCT invoice_no FROM `{TABLE_REF}`").result()
    result = set()
    for row in rows:
        n = normalize_invoice_no(row.invoice_no)
        if n:
            result.add(n)
    return result


def upsert_to_bigquery(rows):
    if not rows:
        print("  No rows to upsert.")
        return

    df = _prepare_df(rows)
    if df.empty:
        print("  DataFrame is empty after preparation.")
        return

    client = _get_client()
    ensure_table_exists(client)

    invoice_nos = df["invoice_no"].dropna().unique().tolist()

    # Safety check: refuse to overwrite any invoice whose new row count is LESS
    # than its existing row count in BQ. Prevents silent data loss when a
    # re-parse extracts fewer lines than the original import (e.g. parser
    # regression, PDF edge case).
    refused = []
    if invoice_nos:
        escaped = [n.replace("'", "''") for n in invoice_nos]
        placeholders = ", ".join(f"'{n}'" for n in escaped)
        existing_counts_query = client.query(
            f"SELECT UPPER(TRIM(invoice_no)) AS k, COUNT(*) AS c "
            f"FROM `{TABLE_REF}` "
            f"WHERE UPPER(TRIM(invoice_no)) IN ({placeholders}) "
            f"GROUP BY k"
        )
        existing_counts = {row.k: row.c for row in existing_counts_query.result()}

        new_counts = df.groupby("invoice_no").size().to_dict()
        for inv_no, new_count in new_counts.items():
            old_count = existing_counts.get(inv_no, 0)
            if old_count > new_count:
                refused.append((inv_no, old_count, new_count))

        if refused:
            print(f"\n  ⚠️  REFUSING to upsert {len(refused)} invoice(s) — new row count is less than existing:")
            for inv_no, old_count, new_count in refused:
                print(f"    - {inv_no}: BQ has {old_count} row(s), new parse only has {new_count}")
            print("    These invoices will be skipped to prevent data loss. Investigate the parser.\n")

            refused_set = {r[0] for r in refused}
            df = df[~df["invoice_no"].isin(refused_set)].copy()
            invoice_nos = [n for n in invoice_nos if n not in refused_set]

    if df.empty:
        print("  Nothing left to upsert after safety check.")
        return

    if invoice_nos:
        escaped = [n.replace("'", "''") for n in invoice_nos]
        placeholders = ", ".join(f"'{n}'" for n in escaped)
        delete_job = client.query(
            f"DELETE FROM `{TABLE_REF}` "
            f"WHERE UPPER(TRIM(invoice_no)) IN ({placeholders})"
        )
        delete_job.result()
        deleted = delete_job.num_dml_affected_rows or 0
        print(f"  Deleted {deleted} existing row(s) across {len(invoice_nos)} invoice(s).")

    job_config = bigquery.LoadJobConfig(
        schema            = _SCHEMA,
        write_disposition = bigquery.WriteDisposition.WRITE_APPEND,
    )
    job = client.load_table_from_dataframe(df, TABLE_REF, job_config=job_config)
    job.result()
    print(f"  Inserted {len(df)} row(s) into {TABLE_REF}.")

    if refused:
        print(f"\n  ⚠️  {len(refused)} invoice(s) were NOT upserted — see above. Existing BQ data was preserved.")
