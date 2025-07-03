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
from manualJournalRequest import get_manual_journal_data
from databaseHelpers import parse_xero_date, get_company_month, get_financial_year, week_of_company_month
from databaseMappings import account_code_mapping, consultant_area_mapping
from dotenv import load_dotenv
load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xeroAuth import XeroTenants
from xeroAuthHelper import getXeroAccessToken

FULL_RESET = True 

quarters = {
    "Jan": "Q3", "Feb": "Q3", "Mar": "Q3",
    "Apr": "Q4", "May": "Q4", "Jun": "Q4",
    "Jul": "Q1", "Aug": "Q1", "Sep": "Q1",
    "Oct": "Q2", "Nov": "Q2", "Dec": "Q2"
}

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

# --- Utilities ---
def build_key(year, month, week, contractor):
    return f"{year}:{month}:{week}:{contractor.strip().lower()}"

def is_valid_line(line):
    tracking = line.get("Tracking", [])
    return any(t.get("Name") == "Category" for t in tracking) and any(t.get("Name") == "Consultant" for t in tracking)

def extract_contractor(invoice_type, line_description):
    def extract_between(text, start_kw, end_kw):
        start = text.find(start_kw)
        if start == -1: return None
        start += len(start_kw)
        end = text.find(end_kw, start)
        return text[start:end].strip() if end != -1 else None

    if invoice_type != "Temp": return None
    patterns = [("Public Holiday of ", " for the week"), ("personal leave of ", " for the week"),
                ("sick leave of ", " for the week"), ("contracting services of ", " for the week"),
                (" of ", " for the week"), (" of ", " on ")]
    
    if line_description.startswith("Base Wage -"):
        for start_kw, end_kw in patterns[:4]:
            if start_kw in line_description:
                return extract_between(line_description, start_kw, end_kw)

    if line_description.startswith("Annual Leave -"):
        return extract_between(line_description, " of ", " for the week")
    if line_description.startswith("Annual Leave Payout -"):
        return extract_between(line_description, " of ", " on ")
    return extract_between(line_description, "contracting services of ", " for the week")

def get_consultant_info_from_reference(reference):
    if not reference or "-" not in reference:
        return "", "", ""
    consultant_name = reference.split("-")[0].strip()
    for code, full_name in consultant_area_mapping.items():
        if consultant_name.lower() in code.lower() or consultant_name.lower() in full_name.lower():
            consultant_code = code
            consultant = code.split(" ", 1)[1].strip(",") if " " in code else consultant_name.strip(",")
            area = consultant_area_mapping.get(code, "")
            return consultant_code, consultant, area
    return "", consultant_name, ""

def get_office_from_consultant_code(code):
    if not code: return ""
    return "Sydney" if code.startswith("S") else "Perth" if code.startswith("P") else "Unknown"

# --- Extractors ---
def extract_invoice_lines(invoice, journal_totals):
    rows = []
    if invoice.get("Status") in ["DELETED", "VOIDED"]:
        return [{
            "InvoiceID": invoice.get("InvoiceID"),
            "Status": invoice.get("Status"),
            "Updated Date": parse_xero_date(invoice.get("UpdatedDateUTC", "")),
            "__deleted__": True
        }]

    invoice_number = invoice.get("InvoiceNumber", "")
    invoice_type = "Temp" if invoice_number.startswith("TC-") else "Perm"
    contact = invoice.get("Contact", {})
    parsed_date = parse_xero_date(invoice.get("Date", ""))
    if not parsed_date:
        return rows

    invoice_month = parsed_date.strftime("%B")
    invoice_week = week_of_company_month(parsed_date)
    company_month = get_company_month(parsed_date)
    company_quarter = quarters[company_month]
    currency_rate = invoice.get("CurrencyRate", 1)
    currency_code = invoice.get("CurrencyCode", "")
    updated_date = parse_xero_date(invoice.get("UpdatedDateUTC", ""))
    updated_date_str = updated_date.strftime("%-d/%-m/%Y") if updated_date else ""

    line_items = invoice.get("LineItems", [])

    if invoice_type == "Temp":
        # Group lines by Key (contractor + week)
        grouped_lines = {}
        for line in line_items:
            if not is_valid_line(line): continue
            description = line.get("Description", "")
            contractor = (extract_contractor(invoice_type, description) or "").lower()
            key = build_key(parsed_date.year, company_month, invoice_week, contractor)
            grouped_lines.setdefault(key, []).append(line)

        for key, lines in grouped_lines.items():
            total_exgst = sum(line.get("LineAmount", 0) for line in lines)
            journal_deduction = journal_totals.get(key, 0)
            for line in lines:
                tracking = line.get("Tracking", [])
                office = consultant_code = consultant = area = ""
                for t in tracking:
                    if t.get("Name") == "Category": office = t.get("Option")
                    elif t.get("Name") == "Consultant":
                        consultant_code = t.get("Option")
                        if consultant_code and " " in consultant_code: consultant = consultant_code.split(" ", 1)[1]

                area = consultant_area_mapping.get(consultant_code, "")
                subtotal = line.get("LineAmount", 0)
                description = line.get("Description", "")
                tax = line.get("TaxAmount", 0)
                total = subtotal + tax
                contractor = (extract_contractor(invoice_type, description) or "").lower()

                proportion = subtotal / total_exgst if total_exgst != 0 else 0
                if "program fee" in description.lower():
                    margin = subtotal
                elif journal_deduction != 0:
                    margin = subtotal + (proportion * journal_deduction)
                else:
                    margin = ""

                if currency_rate and currency_rate != 1:
                    subtotal /= currency_rate
                    total /= currency_rate
                    margin /= currency_rate

                account_code = str(line.get("AccountCode", ""))
                if account_code not in account_code_mapping:
                    print(f"⚠️ Unknown account code: {account_code} in invoice {invoice_number}")
                    continue

                rows.append({
                    "Year": parsed_date.year,
                    "FinancialYear": get_financial_year(parsed_date),
                    "Month": invoice_month,
                    "FutureYou Month": company_month,
                    "Week": invoice_week,
                    "Invoice #": invoice_number,
                    "Type": invoice_type,
                    "To": contact.get("Name", ""),
                    "Key": key,
                    "Description": description,
                    "Contractor": contractor,
                    "Invoice Date": parsed_date.strftime("%-d/%-m/%Y"),
                    "Invoice Total": round(total, 2),
                    "EX GST": round(subtotal, 2),
                    "Margin": round(margin, 2) if isinstance(margin, (int, float)) else "",
                    "Office": office,
                    "Consultant Code": consultant_code,
                    "Consultant": consultant,
                    "Area": area,
                    "Account": account_code,
                    "Account Name": account_code_mapping.get(account_code, ""),
                    "# Placement": 0,
                    "Currency Code": currency_code,
                    "Currency Rate": currency_rate,
                    "Updated Date": updated_date_str,
                    "InvoiceID": invoice.get("InvoiceID", ""),
                    "Quarter": company_quarter,
                })
    else:
        valid_lines = [line for line in line_items if is_valid_line(line)]
        if not valid_lines:
            return rows

        account_code = str(valid_lines[0].get("AccountCode", ""))
        if account_code in ["225", "226","227"]: placement_total = 1/3
        elif account_code == "240": placement_total = 0
        else: placement_total = 1
        total_exgst = sum(line.get("LineAmount", 0) for line in valid_lines)

        for line in valid_lines:
            tracking = line.get("Tracking", [])
            office = consultant_code = consultant = area = ""
            for t in tracking:
                if t.get("Name") == "Category":
                    office = t.get("Option")
                elif t.get("Name") == "Consultant":
                    consultant_code = t.get("Option")
                    if consultant_code and " " in consultant_code:
                        consultant = consultant_code.split(" ", 1)[1]
            area = consultant_area_mapping.get(consultant_code, "")

            subtotal = line.get("LineAmount", 0)
            description = line.get("Description", "")
            tax = line.get("TaxAmount", 0)
            total = subtotal + tax
            contractor = ""  # not used for perm
            key = f"{parsed_date.year}:{company_month}:{invoice_week}:{contractor}"

            # placement proportion
            proportion = subtotal / total_exgst if total_exgst != 0 else 0
            placement = proportion * placement_total
            margin = subtotal

            if currency_rate and currency_rate != 1:
                subtotal /= currency_rate
                total /= currency_rate
                margin /= currency_rate

            if account_code not in account_code_mapping:
                print(f"⚠️ Unknown account code: {account_code} in invoice {invoice_number}")
                continue

            rows.append({
                "Year": parsed_date.year,
                "FinancialYear": get_financial_year(parsed_date),
                "Month": invoice_month,
                "FutureYou Month": company_month,
                "Week": invoice_week,
                "Invoice #": invoice_number,
                "Type": invoice_type,
                "To": contact.get("Name", ""),
                "Key": key,
                "Description": description,
                "Contractor": contractor,
                "Invoice Date": parsed_date.strftime("%-d/%-m/%Y"),
                "Invoice Total": round(total, 2),
                "EX GST": round(subtotal, 2),
                "Margin": round(margin, 2),
                "Office": office,
                "Consultant Code": consultant_code,
                "Consultant": consultant,
                "Area": area,
                "Account": account_code,
                "Account Name": account_code_mapping.get(account_code, ""),
                "# Placement": round(placement, 6),
                "Currency Code": currency_code,
                "Currency Rate": currency_rate,
                "Updated Date": updated_date_str,
                "InvoiceID": invoice.get("InvoiceID", ""),
                "Quarter": company_quarter,
            })
    return rows

def extract_credit_note_lines(cn):
    rows = []
    if cn.get("Status") in ["DELETED", "VOIDED"]:
        return rows

    parsed_date = parse_xero_date(cn.get("Date", ""))
    if not parsed_date:
        return rows

    currency_rate = cn.get("CurrencyRate", 1)
    currency_code = cn.get("CurrencyCode", "")

    for line in cn.get("LineItems", []):
        subtotal = line.get("LineAmount", 0)
        if round(subtotal, 2) == 0:
            continue

        account_code = str(line.get("AccountCode", ""))
        if not account_code or account_code not in account_code_mapping:
            continue

        tracking = line.get("Tracking", [])
        consultant_code = consultant = area = office = ""

        for t in tracking:
            if t.get("Name") == "Consultant":
                consultant_code = t.get("Option")
                if consultant_code and " " in consultant_code:
                    consultant = consultant_code.split(" ", 1)[1].strip(",")
            elif t.get("Name") == "Category":
                office = t.get("Option")

        if not consultant_code and not office:
            continue
        
        area = consultant_area_mapping.get(consultant_code, "")
        tax = line.get("TaxAmount", 0)
        total = subtotal + tax

        # Apply currency conversion if needed
        if currency_rate and currency_rate != 1:
            subtotal /= currency_rate
            total /= currency_rate

        rows.append({
            "Year": parsed_date.year,
            "FinancialYear": get_financial_year(parsed_date),
            "Month": parsed_date.strftime("%B"),
            "FutureYou Month": get_company_month(parsed_date),
            "Week": week_of_company_month(parsed_date),
            "Invoice #": cn.get("CreditNoteNumber", ""),
            "Type": "Perm" if len(cn.get("CreditNoteNumber", "")) == 8 else "Temp",
            "To": cn.get("Contact", {}).get("Name", ""),
            "Key": "",
            "Description": line.get("Description", ""),
            "Contractor": "",
            "Invoice Date": parsed_date.strftime("%-d/%-m/%Y"),
            "Invoice Total": -round(total, 2),
            "EX GST": -round(subtotal, 2),
            "Margin": -round(subtotal, 2),
            "Office": office,
            "Consultant Code": consultant_code,
            "Consultant": consultant,
            "Area": area,
            "Account": account_code,
            "Account Name": account_code_mapping.get(account_code, ""),
            "# Placement": "",
            "Currency Code": currency_code,
            "Currency Rate": currency_rate,
            "Updated Date": parse_xero_date(cn.get("UpdatedDateUTC", "")).strftime("%-d/%-m/%Y") if cn.get("UpdatedDateUTC") else "",
            "InvoiceID": cn.get("CreditNoteID", ""),
            "Quarter": quarters.get(get_company_month(parsed_date), ""),
        })

    return rows


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

# --- Main Function ---
def main():
    clients = ["FUTUREYOU_CONTRACTING", "FUTUREYOU_RECRUITMENT"]
    all_rows = []
    manual_data = get_manual_journal_data()
    # FUTUREYOU_CONTRACTING -> journal_totals dict by key
    journal_totals = {}
    for row in manual_data["FUTUREYOU_CONTRACTING"]:
        key = build_key(row["Year"], row["Month"], row["Week"], row.get("Contractor", ""))
        amt = float(row.get("Line Amount", 0) or 0)
        journal_totals[key] = journal_totals.get(key, 0) + amt

    # FUTUREYOU_RECRUITMENT -> add_on_lines as list of dicts
    add_on_lines = manual_data["FUTUREYOU_RECRUITMENT"]
    updated_since = datetime.now(timezone.utc) - timedelta(days=1)
    updated_date_str = f'DateTime({updated_since.year},{updated_since.month:02},{updated_since.day:02})'
    for client in clients:
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

        for inv in invoices: all_rows.extend(extract_invoice_lines(inv, journal_totals))
        for cn in credit_notes: all_rows.extend(extract_credit_note_lines(cn))
            
    for row in add_on_lines:
        if not FULL_RESET and row.get("Updated Date") and row["Updated Date"] < updated_since.date():
            continue
        date = row.get("Date")
        if isinstance(date, str): date = pd.to_datetime(date, dayfirst=True, errors="coerce")
        if pd.isna(date): continue
        
        financial_year = get_financial_year(date)
        currency_rate = 1
        subtotal = float(row["Line Amount"] or 0)
        total = subtotal
        if subtotal == 0: continue
        all_rows.append({
            "Year": row["Year"],
            "FinancialYear": financial_year,
            "Month": row["Month"],
            "FutureYou Month": get_company_month(date),
            "Week": row["Week"],
            "Invoice #": "",
            "Type": "Perm",
            "To": "",
            "Key": row["Key"],
            "Description": row["Description"],
            "Contractor": row["Contractor"] or "",
            "Invoice Date": date,
            "Invoice Total": round(total, 2),
            "EX GST": round(subtotal, 2),
            "Margin": round(subtotal, 2),
            "Office": row.get("Category", ""),
            "Consultant Code": row.get("Consultant", ""),
            "Consultant": row.get("Consultant", "").split(" ", 1)[1] if " " in row.get("Consultant", "") else row.get("Consultant", ""),
            "Area": consultant_area_mapping.get(row.get("Consultant", ""), ""),
            "Account": row.get("Account Code", ""),
            "Account Name": account_code_mapping.get(str(row.get("Account Code", "")), ""),
            "# Placement": "",
            "Currency Code": "AUD",
            "Currency Rate": currency_rate,
            "Updated Date": pd.to_datetime(row["Updated Date"]).strftime("%-d/%-m/%Y") if pd.notna(row["Updated Date"]) else "",
            "InvoiceID": row.get("InvoiceID", ""),
            "Quarter": quarters.get(get_company_month(date), ""),
        })

    # You can keep or remove the CSV export
    # export_to_csv(all_rows)
    export_to_bigquery(all_rows)

if __name__ == "__main__":
    main()