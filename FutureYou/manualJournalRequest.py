import requests
import os
import sys
import csv
from databaseMappings import journal_account_code_mapping

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from helpers.databaseHelpers import parse_xero_date, get_company_month, week_of_company_month
from xeroAuth import XeroTenants
from xeroAuthHelper import getXeroAccessToken

def fetch_manual_journals(access_token, xero_tenant_id):
    url = "https://api.xero.com/api.xro/2.0/ManualJournals"
    headers = {
        "Authorization": f"Bearer " + access_token,
        "Xero-tenant-id": xero_tenant_id,
        "Accept": "application/json"
    }
    journals = []
    page = 1
    while True:
        params = {
            "where": 'Date>=DateTime(2024, 7, 1) AND Status=="POSTED"',
            "page": page,
            "pageSize": 1000,
        }
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            raise Exception(f"Error fetching manual journals: {response.status_code} - {response.text}")

        data = response.json().get("ManualJournals", [])
        if not data: break
        journals.extend(data)
        page += 1
    return journals

def parse_manual_journal_lines(journals, client_name):
    rows = []
    for journal in journals:
        journal_id = journal.get("ManualJournalID", "")
        date = parse_xero_date(journal.get("Date", ""))
        if not date: continue
        invoice_month = get_company_month(date)
        invoice_week = week_of_company_month(date)
        narration = journal.get("Narration", "")
        status = journal.get("Status", "")
        updated_date = parse_xero_date(journal.get("UpdatedDateUTC", ""))

        for line in journal.get("JournalLines", []):
            if client_name == "FUTUREYOU_RECRUITMENT" and str(line.get("AccountCode")) not in journal_account_code_mapping: continue
            description = line.get("Description", "")
            contractor = ""
            units_worked = 0.0
            if narration.startswith("Temp") and ":" in description:
                parts = description.split(":")
                contractor = parts[1].strip() if len(parts) > 1 else None
                units_worked = parts[2].strip() if len(parts) > 2 else None

            tracking_data = line.get("Tracking", [])
            category = ""
            consultant = ""
            for item in tracking_data:
                if item.get("Name") == "Category": category = item.get("Option", "")
                elif item.get("Name") == "Consultant": consultant = item.get("Option", "")

            rows.append({
                "Journal ID": journal_id,
                "Date": date,
                "Year": date.year,
                "Month": invoice_month,
                "Week": invoice_week,
                "Key": f"{date.year}:{invoice_month}:{invoice_week}:{contractor}",
                "Units Worked": units_worked,
                "Narration": narration,
                "Status": status,
                "Updated Date": updated_date,
                "Account Code": line.get("AccountCode", ""),
                "Line Amount": -line.get("LineAmount", 0),
                "Description": description,
                "Contractor": contractor,
                "Tax Type": line.get("TaxType", ""),
                "Category": category,
                "Consultant": consultant
            })
    return rows

def get_manual_journal_data():
    clients = ["FUTUREYOU_CONTRACTING", "FUTUREYOU_RECRUITMENT"]
    all_journal_data = {}

    for client in clients:
        access_token = getXeroAccessToken(client)
        tenant_id = XeroTenants(access_token)
        journals = fetch_manual_journals(access_token, tenant_id)
        parsed_rows = parse_manual_journal_lines(journals, client)
        all_journal_data[client] = parsed_rows
        print(f"Processed {client}'s manual journals: {len(parsed_rows)} entries")
    return all_journal_data

if __name__ == "__main__":
    journal_data = get_manual_journal_data()
    for client, rows in journal_data.items():
        with open(f"{client}_manual_journals.csv", "w", newline='') as csvfile:
            fieldnames = rows[0].keys() if rows else []
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        print(f"Saved {client} manual journals to CSV.")