import sys
import os
import requests
import csv
import pandas as pd
from datetime import datetime, timezone, timedelta
import re
import pyodbc
import numpy as np
from manualJournalRequest import get_manual_journal_data
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xeroAuth import XeroTenants
from xeroAuthHelper import getXeroAccessToken

# --- SQL ---
def export_to_azure_sql(rows):
    if not rows: return
    df = pd.DataFrame(rows)

    df["Invoice Date"] = pd.to_datetime(df["Invoice Date"], errors="coerce", dayfirst=True)
    df["Updated Date"] = pd.to_datetime(df["Updated Date"], errors="coerce", dayfirst=True)
    float_fields = ["Invoice Total", "EX GST", "Margin", "# Placement", "Currency Rate"]
    for field in float_fields:
        df[field] = pd.to_numeric(df[field], errors="coerce").replace([np.inf, -np.inf], None).round(6)
    # --- Rename columns to match SQL table ---
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

    # --- Ensure None instead of NaN for SQL compatibility ---
    df = df.where(pd.notnull(df), None)
    
    server_password = os.getenv("FUTUREYOU_DATABASE_PASSWORD")

    conn_str = (
        "Driver={ODBC Driver 17 for SQL Server};"
        "Server=tcp:futureyou-trihalo.database.windows.net,1433;"
        "Database=FutureYou Database;"
        "Uid=CloudSAb09ebc32;"
        f"Pwd={server_password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    try:
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM FutureYouInvoices;")
            for i, row in df.iterrows():
                try:
                    values = [
                        int(row["Year"]) if pd.notnull(row["Year"]) else None,
                        str(row["Month"]) if row["Month"] else None,
                        str(row["FutureYouMonth"]) if row["FutureYouMonth"] else None,
                        int(row["Week"]) if pd.notnull(row["Week"]) else None,
                        str(row["InvoiceNumber"]) if row["InvoiceNumber"] else None,
                        str(row["Type"]) if row["Type"] else None,
                        str(row["ToClient"]) if row["ToClient"] else None,
                        str(row["KeyVal"]) if row["KeyVal"] else None,
                        str(row["Description"]) if row["Description"] else None,
                        str(row["Contractor"]) if row["Contractor"] else None,
                        row["InvoiceDate"].to_pydatetime().date() if pd.notnull(row["InvoiceDate"]) else None,
                        float(row["InvoiceTotal"]) if pd.notnull(row["InvoiceTotal"]) else None,
                        float(row["EXGST"]) if pd.notnull(row["EXGST"]) else None,
                        float(row["Margin"]) if pd.notnull(row["Margin"]) else None,
                        str(row["Office"]) if row["Office"] else None,
                        str(row["ConsultantCode"]) if row["ConsultantCode"] else None,
                        str(row["Consultant"]) if row["Consultant"] else None,
                        str(row["Area"]) if row["Area"] else None,
                        str(row["Account"]) if row["Account"] else None,
                        str(row["AccountName"]) if row["AccountName"] else None,
                        float(row["PlacementCount"]) if pd.notnull(row["PlacementCount"]) else None,
                        str(row["CurrencyCode"]) if row["CurrencyCode"] else None,
                        float(row["CurrencyRate"]) if pd.notnull(row["CurrencyRate"]) else None,
                        row["UpdatedDate"].to_pydatetime().date() if pd.notnull(row["UpdatedDate"]) else None,
                        str(row["FinancialYear"]) if row.get("FinancialYear") else None
                    ]

                    cursor.execute("""
                        INSERT INTO FutureYouInvoices (
                            [Year], [Month], [FutureYouMonth], [Week], [InvoiceNumber], [Type],
                            [ToClient], [KeyVal], [Description], [Contractor], [InvoiceDate],
                            [InvoiceTotal], [EXGST], [Margin], [Office], [ConsultantCode],
                            [Consultant], [Area], [Account], [AccountName], [PlacementCount],
                            [CurrencyCode], [CurrencyRate], [UpdatedDate], [FinancialYear]
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, values)
                except Exception as row_err:
                    print(f"❌ Row {i} failed: {row_err}")

            conn.commit()
            print(f"✅ Successfully uploaded {len(df)} rows to Azure SQL.")

    except Exception as e:
        print(f"❌ Upload failed: {e}")


# --- Area Mapping ---
consultant_area_mapping = {
    "SMC003 Neha Jain": "Accounting & Finance",
    "SMB002 Kate Stephenson": "Accounting & Finance",
    "SMC005 Bianca Hirschowitz": "Accounting & Finance",
    "SCB010 Ashley Duffy": "Business Support",
    "SCE010 Matthew Walker": "SC, Eng & Manufacturing",
    "SEA001 Emily Wilson": "Executive",
    "SEL001 Suzie Large": "Legal",
    "SRM001 Lisa Chesterman": "Sales, Marketing & Digital",
    "SRA002 Dale Hackney": "Sales, Marketing & Digital",
    "SCA001 Corin Roberts": "Technology",
    "SCA002 Tamsin Clark": "Business Support",
    "SEL007 Emma McGuigan": "Legal",
    "SMC008 Julien Dreschel": "Accounting & Finance",
    "SEL009 Tarryn Kaufmann": "Executive",
    "SRM006 Tarryn Kaufmann": "Sales, Marketing & Digital",
    "SEL010 Shazer Barino": "Legal",
    "SMB007 Samaira Bohjani": "Accounting & Finance",
    "PEK002 Tapiwa Utete": "Technology",
    "SMC010 Chloe Crewdson": "Accounting & Finance",
    "SMC004 Melise Hasip": "Accounting & Finance",
    "SMC004 Mel Hasip": "Accounting & Finance",
    "SMA001 Chris Martin": "Accounting & Finance",
    "SCB013 Sharon Callaghan": "Business Support",
    "PEK001 Kevin Howell": "Technology",
}

# --- Account Mapping ---
account_code_mapping = {
    "200": "Revenue - Permanent",
    "210": "Revenue - Temporary and contracts",
    "215": "Revenue - Temp to Perm",
    "220": "Revenue - Fixed term contract",
    "225": "Revenue - Retained - Initial",
    "226": "Revenue - Retained - Shortlist",
    "227": "Revenue - Retained - Completion",
    "228": "Revenue - internal",
    "229": "Perm Candidate Reimbursement",
    "230": "Advertising revenue",
    "240": "Revenue - Advisory Consulting HR",
    "241": "Revenue - Advisory HR outsourced services",
    "245": "Revenue - Advisory - EVP",
    "249": "Revenue - Advisory Search",
    "250": "Revenue - Advisory Transition Services",
    "251": "Revenue - Advisory Leadership Program",
    "260": "Revenue - Other Revenue",
    "611": "Doubtful Debts Provision",
}

# --- Utilities ---
def get_month_cutoffs(year):
    if year == 2025:
        return {
            "Jan": datetime(year, 1, 26),
            "Feb": datetime(year, 2, 23),
            "Mar": datetime(year, 3, 31),
            "Apr": datetime(year, 4, 27),
            "May": datetime(year, 5, 25),
            "Jun": datetime(year, 6, 30),
            "Jul": datetime(year, 7, 27),
            "Aug": datetime(year, 8, 24),
            "Sep": datetime(year, 9, 30),
            "Oct": datetime(year, 10, 26),
            "Nov": datetime(year, 11, 23),
            "Dec": datetime(year, 12, 31),
        }
    elif year == 2024:
        return {
            "Jan": datetime(year, 1, 28),
            "Feb": datetime(year, 2, 25),
            "Mar": datetime(year, 3, 31),
            "Apr": datetime(year, 4, 28),
            "May": datetime(year, 5, 26),
            "Jun": datetime(year, 6, 30),
            "Jul": datetime(year, 7, 28),
            "Aug": datetime(year, 8, 25),
            "Sep": datetime(year, 9, 30),
            "Oct": datetime(year, 10, 27),
            "Nov": datetime(year, 11, 24),
            "Dec": datetime(year, 12, 31),     
        }

def get_company_month(invoice_date):
    cutoffs = get_month_cutoffs(invoice_date.year)
    for month, cutoff in cutoffs.items():
        if invoice_date <= cutoff.date():
            return month
    return "Dec"

def get_financial_year(date):
    if date.month >= 7: return f"FY{str(date.year + 1)[-2:]}"
    else: return f"FY{str(date.year)[-2:]}"


def parse_xero_date(xero_date_str):
    match = re.search(r"/Date\((\d+)", xero_date_str)
    if match:
        timestamp_ms = int(match.group(1))
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).date()
    return None

def build_key(year, month, week, contractor):
    return f"{year}:{month}:{week}:{contractor.strip().lower()}"

def week_of_company_month(date):
    year = date.year
    cutoffs = get_month_cutoffs(year)

    company_month = get_company_month(date)

    # Determine the start of the business month (day after previous cutoff)
    month_names = list(cutoffs.keys())
    current_index = month_names.index(company_month)

    if current_index == 0:  # If it's January, go back to previous year's Dec cutoff
        prev_cutoffs = get_month_cutoffs(year - 1)
        start_date = prev_cutoffs["Dec"].date() + timedelta(days=1)
    else:
        prev_month = month_names[current_index - 1]
        start_date = cutoffs[prev_month].date() + timedelta(days=1)

    # Now calculate the week number relative to start_date
    delta_days = (date - start_date).days
    adjusted_day = delta_days + start_date.weekday()
    no = (adjusted_day // 7) + 1
    return no if no < 6 else 5

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
        return rows

    invoice_number = invoice.get("InvoiceNumber", "")
    invoice_type = "Temp" if invoice_number.startswith("TC-") else "Perm"
    contact = invoice.get("Contact", {})
    parsed_date = parse_xero_date(invoice.get("Date", ""))
    if not parsed_date:
        return rows

    invoice_month = parsed_date.strftime("%B")
    invoice_week = week_of_company_month(parsed_date)
    company_month = get_company_month(parsed_date)
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
                    "# Placement": 1 / 3 if account_code in ["225", "226", "227"] else 1,
                    "Currency Code": currency_code,
                    "Currency Rate": currency_rate,
                    "Updated Date": updated_date_str
                })

    else:
        # Perm invoice - same as before
        for line in line_items:
            if not is_valid_line(line):
                continue

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

            margin = subtotal

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
                "# Placement": 1 / 3 if account_code in ["225", "226", "227"] else 1,
                "Currency Code": currency_code,
                "Currency Rate": currency_rate,
                "Updated Date": updated_date_str
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
            "Type": "Perm" if len(cn.get("CreditNoteNumber", ""),) == 8 else "Temp",
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
            "Updated Date": parse_xero_date(cn.get("UpdatedDateUTC", "")).strftime("%-d/%-m/%Y") if cn.get("UpdatedDateUTC") else ""
        })

    return rows


# --- API Fetch ---
def fetch_all(endpoint, access_token, tenant_id, params=None):
    all_results = []
    params = params or {"page": 1, "pageSize": 100}
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

# # --- Export ---
# def export_to_csv(rows, filename="all_clients_formatted_invoices.csv"):
#     if not rows:
#         print("❌ No rows to export")
#         return
#     df = pd.DataFrame(rows)
#     df["Invoice Date (Sortable)"] = pd.to_datetime(df["Invoice Date"], format="%d/%m/%Y")
#     df.sort_values("Invoice Date (Sortable)", inplace=True)
#     df.drop(columns=["Invoice Date (Sortable)"], inplace=True)
#     df.to_csv(filename, index=False)
#     print(f"✅ Exported {len(df)} rows to {filename}")

# --- Main ---
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


    for client in clients:
        access_token = getXeroAccessToken(client)
        tenant_id = XeroTenants(access_token)

        invoice_params = {"where": 'Type=="ACCREC" AND Date>=DateTime(2024, 7, 1)', "page": 1, "pageSize": 100}
        credit_params = {"where": 'Date>=DateTime(2024, 7, 1)', "page": 1, "pageSize": 100}

        invoices = fetch_all("Invoices", access_token, tenant_id, invoice_params)
        credit_notes = fetch_all("CreditNotes", access_token, tenant_id, credit_params)

        for inv in invoices:
            all_rows.extend(extract_invoice_lines(inv, journal_totals))
        for cn in credit_notes:
            all_rows.extend(extract_credit_note_lines(cn))
            
    for row in add_on_lines:
        date = row.get("Date")
        if isinstance(date, str):
            date = pd.to_datetime(date, dayfirst=True, errors="coerce")
        if pd.isna(date):
            continue
        
        financial_year = get_financial_year(date)
        currency_rate = 1
        subtotal = float(row["Line Amount"] or 0)
        total = subtotal
        if subtotal == 0:
            continue

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
            "Updated Date": pd.to_datetime(row["Updated Date"]).strftime("%-d/%-m/%Y") if pd.notna(row["Updated Date"]) else ""
        })

    # export_to_csv(all_rows)
    export_to_azure_sql(all_rows)

if __name__ == "__main__":
    main()

