import requests
import os
import sys
import csv
from datetime import datetime, timezone, timedelta
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xeroAuth import XeroTenants
from xeroAuthHelper import getXeroAccessToken


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
}

def parse_xero_date(xero_date_str):
    match = re.search(r"/Date\((\d+)", xero_date_str)
    if match:
        timestamp_ms = int(match.group(1))
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).date()
    return None

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
            "page": page
        }

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            raise Exception(f"Error fetching manual journals: {response.status_code} - {response.text}")

        data = response.json().get("ManualJournals", [])
        if not data:
            break

        journals.extend(data)
        page += 1

    return journals

def parse_manual_journal_lines(journals, client_name):
    rows = []
    for journal in journals:
        journal_id = journal.get("ManualJournalID", "")
        date = parse_xero_date(journal.get("Date", ""))
        if not date:
            continue
        invoice_month = get_company_month(date)
        invoice_week = week_of_company_month(date)
        narration = journal.get("Narration", "")
        status = journal.get("Status", "")
        updated_date = parse_xero_date(journal.get("UpdatedDateUTC", ""))

        for line in journal.get("JournalLines", []):
            if client_name == "FUTUREYOU_RECRUITMENT" and str(line.get("AccountCode")) not in account_code_mapping:
                continue

            description = line.get("Description", "")
            contractor = ""
            if narration.startswith("Temp") and ":" in description:
                contractor = description.split(":", 1)[1].strip()

            tracking_data = line.get("Tracking", [])
            category = ""
            consultant = ""
            for item in tracking_data:
                if item.get("Name") == "Category":
                    category = item.get("Option", "")
                elif item.get("Name") == "Consultant":
                    consultant = item.get("Option", "")

            rows.append({
                "Journal ID": journal_id,
                "Date": date,
                "Year": date.year,
                "Month": invoice_month,
                "Week": invoice_week,
                "Key": f"{date.year}:{invoice_month}:{invoice_week}:{contractor}",
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
