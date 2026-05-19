"""
Fix International Freight rows in BigQuery.

For each freight row where currency != 'AUD':
  - rate            = FX amount extracted from details  (e.g. USD700 → 700)
  - conversion_rate = (qty * rate) / amount_ex_gst
"""
import os
from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account

load_dotenv()

PROJECT_ID = "h2dataservices"
DATASET_ID = "distribution"
TABLE_ID   = "freight_charges"
TABLE_REF  = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

UPDATE_SQL = f"""
UPDATE `{TABLE_REF}`
SET
  rate = CAST(
    REGEXP_EXTRACT(details, r'(?:USD|EUR|GBP|CNY|NZD)([\\d,]+(?:\\.\\d+)?)') AS FLOAT64
  ),
  conversion_rate = ROUND(
    qty
    * CAST(REGEXP_EXTRACT(details, r'(?:USD|EUR|GBP|CNY|NZD)([\\d,]+(?:\\.\\d+)?)') AS FLOAT64)
    / amount_ex_gst,
    6
  )
WHERE
  standardised_description = 'International Freight'
  AND currency != 'AUD'
  AND REGEXP_CONTAINS(details, r'(?:USD|EUR|GBP|CNY|NZD)[\\d,]+(?:\\.\\d+)?')
  AND amount_ex_gst > 0
"""

VERIFY_SQL = f"""
SELECT
  invoice_no,
  details,
  qty,
  currency,
  rate,
  conversion_rate,
  amount_ex_gst
FROM `{TABLE_REF}`
WHERE
  standardised_description = 'International Freight'
  AND currency != 'AUD'
ORDER BY invoice_no
"""


def _get_client():
    key_path = os.getenv("H2DATASERVICES_BQACCESS")
    if not key_path:
        raise EnvironmentError("H2DATASERVICES_BQACCESS environment variable is not set.")
    credentials = service_account.Credentials.from_service_account_file(
        key_path,
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )
    return bigquery.Client(credentials=credentials, project=PROJECT_ID)


def main():
    client = _get_client()

    print("Running UPDATE on freight_charges...")
    job = client.query(UPDATE_SQL)
    job.result()
    print(f"  Rows affected: {job.num_dml_affected_rows}")

    print("\nVerifying updated rows:")
    rows = list(client.query(VERIFY_SQL).result())
    for r in rows:
        print(
            f"  {r.invoice_no} | {r.details} | qty={r.qty:.0f} | "
            f"rate={r.rate} | conv={r.conversion_rate} | amount_ex={r.amount_ex_gst}"
        )


if __name__ == "__main__":
    main()
