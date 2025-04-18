# --- helpers.py (new shared utilities module) ---
from datetime import datetime, timezone, timedelta
import re

# Xero timestamp parser
def parse_xero_date(xero_date_str):
    match = re.search(r"/Date\((\d+)", xero_date_str)
    if match:
        timestamp_ms = int(match.group(1))
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).date()
    return None

# Custom business month cutoffs
def get_month_cutoffs(year):
    return {
        "Jan": datetime(year, 1, 26 if year == 2025 else 28),
        "Feb": datetime(year, 2, 23 if year == 2025 else 25),
        "Mar": datetime(year, 3, 31),
        "Apr": datetime(year, 4, 27 if year == 2025 else 28),
        "May": datetime(year, 5, 25 if year == 2025 else 26),
        "Jun": datetime(year, 6, 30),
        "Jul": datetime(year, 7, 27 if year == 2025 else 28),
        "Aug": datetime(year, 8, 24 if year == 2025 else 25),
        "Sep": datetime(year, 9, 30),
        "Oct": datetime(year, 10, 26 if year == 2025 else 27),
        "Nov": datetime(year, 11, 23 if year == 2025 else 24),
        "Dec": datetime(year, 12, 31)
    }

# Determine which company month a date belongs to
def get_company_month(invoice_date):
    cutoffs = get_month_cutoffs(invoice_date.year)
    for month, cutoff in cutoffs.items():
        if invoice_date <= cutoff.date():
            return month
    return "Dec"

# Determine company-specific week number
def week_of_company_month(date):
    year = date.year
    cutoffs = get_month_cutoffs(year)
    company_month = get_company_month(date)

    month_names = list(cutoffs.keys())
    current_index = month_names.index(company_month)

    if current_index == 0:
        prev_cutoffs = get_month_cutoffs(year - 1)
        start_date = prev_cutoffs["Dec"].date() + timedelta(days=1)
    else:
        prev_month = month_names[current_index - 1]
        start_date = cutoffs[prev_month].date() + timedelta(days=1)

    delta_days = (date - start_date).days
    adjusted_day = delta_days + start_date.weekday()
    no = (adjusted_day // 7) + 1
    return no if no < 6 else 5

# Financial year label
def get_financial_year(date):
    return f"FY{str(date.year + 1)[-2:]}" if date.month >= 7 else f"FY{str(date.year)[-2:]}"

def delete_existing_records(cursor, invoice_ids, manual_journal_ids):
    if invoice_ids:
        for i in range(0, len(invoice_ids), 1000):
            chunk = invoice_ids[i:i + 1000]
            placeholders = ",".join(["?"] * len(chunk))
            cursor.execute(
                f"DELETE FROM FutureYouInvoices WHERE InvoiceID IN ({placeholders})",
                chunk
            )
    if manual_journal_ids:
        for i in range(0, len(manual_journal_ids), 1000):
            chunk = manual_journal_ids[i:i + 1000]
            placeholders = ",".join(["?"] * len(chunk))
            cursor.execute(
                f"DELETE FROM FutureYouInvoices WHERE ManualJournalID IN ({placeholders})",
                chunk
            )

