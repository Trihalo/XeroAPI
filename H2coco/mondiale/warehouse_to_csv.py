import pdfplumber
import pandas as pd
import re
from pathlib import Path

INVOICE_DIR = Path(__file__).parent / "warehouse_invoices"
OUTPUT_CSV  = Path(__file__).parent / "warehouse_invoices_combined.csv"

MONTH_MAP = {
    'JANUARY':   'Jan', 'JAN': 'Jan',
    'FEBRUARY':  'Feb', 'FEB': 'Feb',
    'MARCH':     'Mar', 'MAR': 'Mar',
    'APRIL':     'Apr', 'APR': 'Apr',
    'MAY':       'May',
    'JUNE':      'Jun', 'JUN': 'Jun',
    'JULY':      'Jul', 'JUL': 'Jul',
    'AUGUST':    'Aug', 'AUG': 'Aug',
    'SEPTEMBER': 'Sep', 'SEP': 'Sep',
    'OCTOBER':   'Oct', 'OCT': 'Oct',
    'NOVEMBER':  'Nov', 'NOV': 'Nov',
    'DECEMBER':  'Dec', 'DEC': 'Dec',
}

# Normalise location names extracted from goods description → standard state code
STATE_NORM = {
    'SYD':     'NSW', 'SYDNEY':    'NSW',
    'ALTONA':  'VIC', 'MEL':       'VIC', 'MELBOURNE': 'VIC',
    'BNE':     'QLD', 'BRISBANE':  'QLD',
    'PERTH':   'WA',
    'ADL':     'SA',  'ADELAIDE':  'SA',
}

CONTAINER_RE = re.compile(r'^[A-Z]{3,4}\d{6,7}$')
CHARGE_RE    = re.compile(r'^(.+?)\s+10%=([\d.]+)\s+([\d,]+\.\d{2})$')
RATE_RE      = re.compile(r'@\s*\$?\s*([\d,]+\.?\d*)ea', re.IGNORECASE)

# Matches goods description lines such as:
#   APRIL 2026 WA WHS BILLING
#   DEC 2025 SYD WAREHOUSE BILLING
#   DEC 2025 - SYDNEY WAREHOUSE BILLING
_PERIOD_RE = re.compile(
    r'([A-Z]+)\s+(\d{4})\s*-?\s*([A-Z]+)\s+(?:WHS|WAREHOUSE)\b',
    re.IGNORECASE,
)

# Matches activity date ranges in two formats:
#   13.04 - 19.04.2026            (WA/BNE/MEL style)
#   01.12.2025 - 07.12.2025       (SYD/Altona style)
_ACTIVITY_RE = re.compile(
    r'ACTIVITIES\s+([\d.]+\s*-\s*[\d.]+)',
    re.IGNORECASE,
)


def _normalise_state(raw):
    return STATE_NORM.get(raw.upper(), raw.upper())


def _parse_period(line):
    """Return (month_abbr, year_str, state_code) from a goods description line."""
    m = _PERIOD_RE.search(line)
    if not m:
        return '', '', ''
    month = MONTH_MAP.get(m.group(1).upper(), m.group(1)[:3].capitalize())
    year  = m.group(2)
    state = _normalise_state(m.group(3))
    return month, year, state


def _parse_activity_period(p1_text, p1_lines):
    """Find activity date range from the invoicing note."""
    for line in p1_lines:
        m = _ACTIVITY_RE.search(line)
        if m:
            return m.group(1).strip()
    # Fallback: look for "PERTAIN TO <LOCATION> WAREHOUSE\n<dates>"
    m = re.search(r'PERTAIN TO \w+ WAREHOUSE\s+([\d.]+ - [\d.]+)', p1_text)
    if m:
        return m.group(1).strip()
    return ''


def _state_from_invoicing_note(p1_text):
    """Fallback: extract state from 'PERTAIN TO <LOCATION> WAREHOUSE'."""
    m = re.search(r'PERTAIN TO ([A-Z]+) WAREHOUSE', p1_text, re.IGNORECASE)
    if m:
        return _normalise_state(m.group(1))
    return ''


def _parse_description(charge_text):
    """Return (desc, details) by splitting at the meaningful ' - ' separator."""
    # Greedy: find last ' - ' before qty-start patterns (incl. PALLET(S))
    m = re.search(
        r'^(.+)\s+-\s+(?:less than\s+)?'
        r'(?:PALLET\(S\)|PALLETS?|CARTONS?|LABELS?|ORDERS?|[\d,@])',
        charge_text,
    )
    if m:
        desc    = m.group(1).strip()
        details = charge_text[m.end(1):].lstrip(' -').strip()
        return desc, details

    # Fallback: "DESC N @" with no dash (e.g. OUTBOUND LABELLING 265 @ $0.30ea)
    m = re.search(r'^(.+?)\s+([\d,]+)\s*@', charge_text)
    if m:
        return m.group(1).strip(), charge_text[m.start(2):].strip()

    return charge_text.strip(), ''


def _parse_qty(charge_text):
    """Extract quantity from the charge text."""
    # "ea X N" — HAND UNPACK: "@$520.00ea X 2"
    m = re.search(r'ea\s+[Xx]\s+(\d+)', charge_text)
    if m:
        return float(m.group(1))

    # "N x Containers" — DTRN: "4 x Containers"
    m = re.search(r'(\d+)\s+[xX]\s+Containers?', charge_text, re.IGNORECASE)
    if m:
        return float(m.group(1))

    # N before UNIT keyword — case-sensitive (real units are UPPERCASE)
    m = re.search(r'([\d,]+)\s+(?:PALLETS?|CARTONS?|LABELS?|ORDERS?)\b', charge_text)
    if m:
        return float(m.group(1).replace(',', ''))

    # N before @ (handles "134 @$", "134@$", "265 @ $")
    m = re.search(r'([\d,]+)\s*@', charge_text)
    if m:
        return float(m.group(1).replace(',', ''))

    return 1.0


def parse_invoice(path):
    print(f"Parsing {path}...")
    with pdfplumber.open(path) as pdf:
        p1_text  = pdf.pages[0].extract_text() or ''
        p1_lines = p1_text.split('\n')

    # Header fields
    m = re.search(r'TAX INVOICE\s+(\d+)', p1_text)
    invoice_num = m.group(1) if m else ''

    m = re.search(r'INVOICE DATE:(\d{1,2}-[A-Za-z]+-\d{2})', p1_text)
    invoice_date = m.group(1) if m else ''

    m = re.search(r'DUE DATE:(\d{1,2}-[A-Za-z]+-\d{2})', p1_text)
    due_date = m.group(1) if m else ''

    m = re.search(r'TRANSPORT:(\w+)', p1_text)
    transport = m.group(1) if m else ''

    # Period and state from GOODS DESCRIPTION line
    period_month = period_year = state = ''
    for line in p1_lines:
        if _PERIOD_RE.search(line):
            period_month, period_year, state = _parse_period(line.strip())
            if period_month:
                break

    # Fallback: derive state from invoicing note if still missing
    if not state:
        state = _state_from_invoicing_note(p1_text)

    activity_period = _parse_activity_period(p1_text, p1_lines)

    rows       = []
    in_charges = False

    for i, raw_line in enumerate(p1_lines):
        line = raw_line.strip()

        if 'DESCRIPTION' in line and 'CHARGES IN AUD' in line:
            in_charges = True
            continue

        if not in_charges:
            continue

        if line.startswith(('SUBTOTAL', 'ADD GST', 'TOTAL', 'All business', 'Please contact')):
            break

        m = CHARGE_RE.match(line)
        if not m:
            continue

        charge_text = m.group(1)
        amount_ex   = float(m.group(3).replace(',', ''))
        gst_val     = round(amount_ex * 0.10, 2)
        amount_inc  = round(amount_ex + gst_val, 2)

        # Rate: try current line, then look at next line
        rate_m = RATE_RE.search(charge_text)
        if rate_m:
            rate = float(rate_m.group(1).replace(',', ''))
        else:
            next_line = p1_lines[i + 1].strip() if i + 1 < len(p1_lines) else ''
            rate_m2   = RATE_RE.search(next_line)
            rate      = float(rate_m2.group(1).replace(',', '')) if rate_m2 else 0.0

        qty  = _parse_qty(charge_text)
        desc, details = _parse_description(charge_text)

        # Container numbers for HAND UNPACK lines only
        containers = []
        if 'HAND UNPACK' in charge_text.upper():
            j = i + 1
            while j < len(p1_lines):
                next_line = p1_lines[j].strip()
                if next_line in ('CONTAINERS', 'CONTAINER'):
                    j += 1
                    continue
                if CONTAINER_RE.match(next_line):
                    containers.append(next_line)
                    j += 1
                else:
                    break

        rows.append({
            'Invoice No':        invoice_num,
            'Invoice Date':      invoice_date,
            'Due Date':          due_date,
            'Transport':         transport,
            'Period Month':      period_month,
            'Period Year':       period_year,
            'State':             state,
            'Activity Period':   activity_period,
            'Description':       desc,
            'Details':           details,
            'Qty':               qty,
            'Rate':              rate,
            'GST Y/N':           'Y',
            'Amount (Ex GST)':   amount_ex,
            'GST':               gst_val,
            'Amount (Inc GST)':  amount_inc,
            'Container Numbers': ' | '.join(containers),
        })

    if rows:
        total_ex  = round(sum(r['Amount (Ex GST)']  for r in rows), 2)
        total_inc = round(sum(r['Amount (Inc GST)'] for r in rows), 2)
        for r in rows:
            r['Invoice Total (Ex GST)']  = total_ex
            r['Invoice Total (Inc GST)'] = total_inc

    return rows


def main():
    pdfs = sorted(INVOICE_DIR.glob('*.PDF')) + sorted(INVOICE_DIR.glob('*.pdf'))
    if not pdfs:
        print(f"No PDFs found in {INVOICE_DIR}")
        return

    all_rows = []
    for pdf_path in pdfs:
        all_rows.extend(parse_invoice(pdf_path))

    if not all_rows:
        print("No charge rows extracted.")
        return

    df = pd.DataFrame(all_rows)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nWrote {len(df)} rows to {OUTPUT_CSV}")
    print(df[['Invoice No', 'Invoice Date', 'Description', 'Qty', 'Rate',
              'Amount (Ex GST)', 'Container Numbers']].to_string(index=False))


if __name__ == '__main__':
    main()
