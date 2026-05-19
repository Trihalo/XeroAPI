"""
One-off script: upload warehouse_invoices_combined.csv → BigQuery.

Uses WRITE_TRUNCATE (full replace) so it is safe to re-run — it will
always produce an exact copy of the CSV in the table, with no duplicates.
"""

import os
import sys
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from warehouse_bq import (
    PROJECT_ID, DATASET_ID, TABLE_ID, TABLE_REF,
    _SCHEMA, _get_client, _prepare_df,
)

CSV_PATH = Path(__file__).parent / "warehouse_invoices_combined.csv"


def main():
    if not CSV_PATH.exists():
        print(f"CSV not found: {CSV_PATH}")
        return

    df_raw = pd.read_csv(CSV_PATH, dtype=str)
    print(f"Loaded {len(df_raw)} rows from {CSV_PATH.name}")

    df = _prepare_df(df_raw)
    print(f"Prepared {len(df)} rows for upload")

    client = _get_client()

    job_config = bigquery.LoadJobConfig(
        schema            = _SCHEMA,
        write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    print(f"Uploading to {TABLE_REF} (WRITE_TRUNCATE — replaces entire table)...")
    job = client.load_table_from_dataframe(df, TABLE_REF, job_config=job_config)
    job.result()
    print(f"Done. {len(df)} rows written to {TABLE_REF}.")


if __name__ == "__main__":
    main()
