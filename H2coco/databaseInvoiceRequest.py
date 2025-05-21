import sys
import os
import requests
import csv
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from google.cloud import bigquery
from google.oauth2 import service_account
import pandas_gbq
from dotenv import load_dotenv
load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xeroAuth import XeroTenants
from xeroAuthHelper import getXeroAccessToken

FULL_RESET = True 

# --- BigQuery Functions ---
def export_to_bigquery(rows):
    if not rows:
        print("❌ No rows to upload")
        return

    # Path to your service account key file
    key_path = os.getenv("BQACCESS")
    project_id = "futureyou-458212"
    dataset_id = "InvoiceData"
    table_id = "InvoiceEnquiry"

    # Full table reference
    table_ref = f"{project_id}.{dataset_id}.{table_id}"

    try:
        # Create credentials and client
        credentials = service_account.Credentials.from_service_account_file(
            key_path, 
            scopes=["https://www.googleapis.com/auth/bigquery"]
        )
        client = bigquery.Client(credentials=credentials, project=project_id)

        # --- 1. Handle deletions first ---
        deleted_ids = [
            r["InvoiceID"] for r in rows
            if r.get("__deleted__") and r.get("InvoiceID")
        ]
        if deleted_ids:
            # Construct a DELETE query for BigQuery
            placeholders = ", ".join(f"'{id}'" for id in deleted_ids)
            query = f"DELETE FROM `{table_ref}` WHERE InvoiceID IN ({placeholders})"
            
            # Execute the deletion query
            query_job = client.query(query)
            query_job.result()  # Wait for query to complete
            print(f"🗑️ Deleted {len(deleted_ids)} voided/deleted invoices from BigQuery.")

        # --- 2. Filter out deleted rows before continuing ---
        filtered_rows = [r for r in rows if not r.get("__deleted__")]
        if not filtered_rows:
            print("ℹ️ No valid rows to upload after filtering.")
            return

        df = pd.DataFrame(filtered_rows)

        # --- 3. Parse and clean up ---
        df["Invoice Date"] = pd.to_datetime(df["Invoice Date"], errors="coerce", dayfirst=True)
        df["Updated Date"] = pd.to_datetime(df["Updated Date"], errors="coerce", dayfirst=True)

        float_fields = ["Invoice Total", "EX GST", "Margin", "# Placement", "Currency Rate"]
        for field in float_fields:
            df[field] = pd.to_numeric(df[field], errors="coerce").replace([np.inf, -np.inf], None).round(6)

        df.rename(columns={
            "FutureYou Month": "FutureYouMonth",
            "Invoice #": "InvoiceNumber",
            "# Placement": "PlacementCount",
            "Invoice Date": "InvoiceDate",
            "Updated Date": "UpdatedDate",
            "Invoice Total": "InvoiceTotal",
            "EX GST": "EXGST",
            "Consultant Code": "ConsultantCode",
            "Account Name": "AccountName",
            "Currency Code": "CurrencyCode",
            "Currency Rate": "CurrencyRate",
            "To": "ToClient",
            "Key": "KeyVal"
        }, inplace=True)

        # Replace NaNs with None for BigQuery compatibility
        df = df.where(pd.notnull(df), None)

        # --- 4. Handle full reset or delete existing records by InvoiceID ---
        if FULL_RESET:
            query = f"DELETE FROM `{table_ref}` WHERE 1=1"
            query_job = client.query(query)
            query_job.result()  # Wait for query to complete
            print("⚠️ Full reset: all rows deleted.")
        else:
            updated_ids = df["InvoiceID"].dropna().astype(str).tolist()
            if updated_ids:
                # Construct a DELETE query for BigQuery
                placeholders = ", ".join(f"'{id}'" for id in updated_ids)
                query = f"DELETE FROM `{table_ref}` WHERE InvoiceID IN ({placeholders})"
                
                # Execute the deletion query
                query_job = client.query(query)
                query_job.result()  # Wait for query to complete
                print(f"✅ Deleted {len(updated_ids)} updated invoices from BigQuery.")

        # --- 5. Insert fresh data ---
        # Convert date columns to datetime format for proper BigQuery loading
        if "InvoiceDate" in df.columns and df["InvoiceDate"].dtype != 'datetime64[ns]':
            df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors='coerce')
            
        if "UpdatedDate" in df.columns and df["UpdatedDate"].dtype != 'datetime64[ns]':
            df["UpdatedDate"] = pd.to_datetime(df["UpdatedDate"], errors='coerce')
            
        # Upload dataframe to BigQuery
        pandas_gbq.to_gbq(
            df, 
            f"{dataset_id}.{table_id}", 
            project_id=project_id,
            credentials=credentials,
            if_exists="append"
        )
        
        print(f"✅ Successfully uploaded {len(df)} rows to BigQuery.")

    except Exception as e:
        print(f"❌ Upload failed: {e}")

# --- API Fetch ---
def fetch_all(endpoint, access_token, tenant_id, params=None):
    all_results = []
    params = params or {"page": 1, "pageSize": 1000}
    while True:
        res = requests.get(f"https://api.xero.com/api.xro/2.0/{endpoint}",
                           headers={"Authorization": f"Bearer {access_token}", "Xero-tenant-id": tenant_id, "Accept": "application/json"},
                           params=params)
        if res.status_code != 200:
            raise Exception(f"Fetch failed for {endpoint}: {res.status_code} - {res.text}")
        data = res.json().get(endpoint, [])
        if not data: break
        all_results.extend(data)
        params["page"] += 1
    return all_results

# --- Export to CSV ---
def export_to_csv(rows, filename="xero_export.csv"):
    if not rows:
        print("❌ No rows to export")
        return

    df = pd.DataFrame(rows)
    df.to_csv(filename, index=False)
    print(f"📄 Exported {len(df)} rows to {filename}")


# --- Main Function ---
def main():
    client = "H2COCO"

    updated_since = datetime.now(timezone.utc) - timedelta(days=1)
    updated_date_str = f'DateTime({updated_since.year},{updated_since.month:02},{updated_since.day:02})'
    access_token = getXeroAccessToken(client)
    tenant_id = XeroTenants(access_token)
    if FULL_RESET:
        invoice_params = {
            "where": 'Type=="ACCREC" AND Date>=DateTime(2024,07,01)',
            "page": 1,
            "pageSize": 1000
        }
        credit_params = {
            "where": 'Date>=DateTime(2024,07,01)',
            "page": 1,
            "pageSize": 1000
        }
    else:
        invoice_params = {
            "where": f'Type=="ACCREC" AND UpdatedDateUTC>={updated_date_str}',
            "page": 1,
            "pageSize": 1000
        }
        credit_params = {
            "where": f'UpdatedDateUTC>={updated_date_str}',
            "page": 1,
            "pageSize": 1000
        }

    invoices = fetch_all("Invoices", access_token, tenant_id, invoice_params)
    credit_notes = fetch_all("CreditNotes", access_token, tenant_id, credit_params)
    
    print(f"Fetched {len(invoices)} invoices and {len(credit_notes)} credit notes.")


    # You can keep or remove the CSV export
    all_rows = invoices + credit_notes
    export_to_csv(all_rows)
    # export_to_bigquery(all_rows)

if __name__ == "__main__":
    main()