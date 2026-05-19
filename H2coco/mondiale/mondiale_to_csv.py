import pdfplumber
import pandas as pd
import re
import os

# Maps substrings of raw Description values (from either source) to a standardised name.
# Matching is done in order — first match wins. Keys are case-insensitive substrings.
DESCRIPTION_MAP = [
    ("Freight Fee",                     "International Freight"),
    ("International Freight",           "International Freight"),
    ("Heavy Weight Surcharge",          "Heavy Weight Surcharge"),
    ("Customs Disbursements",           "Customs Disbursements"),
    ("Quarantine Processing",           "Customs Disbursements"),
    ("Import Processing",               "Customs Disbursements"),
    ("Customs Clearance",               "Customs Clearance Fee"),
    ("Port Service",                    "Port Service Charges"),
    ("Destination Port Charges",        "Port Service Charges"),
    ("Documentation Fee",               "Documentation Fee"),
    ("CMR Fee",                         "CMR Fee"),
    ("terminal infrastructure",         "Terminal Infrastructure Fee"),
    ("Intermodal Terminal Levy",        "Intermodal Terminal Levy"),
    ("Cartage via Yard",                "Cartage"),
    ("Cartage Fee",                     "Cartage"),
    ("Delivery Cartage Booking",        "Delivery Booking Fees"),
    ("Timeslot Booking Fee",            "Delivery Booking Fees"),
    ("Delivery Cartage",                "Cartage"),
    ("Cartage Fuel Levy",               "Cartage Fuel Levy"),
    ("Fuel Surcharge",                  "Cartage Fuel Levy"),
    ("Sea Cargo Automation",            "Sea Cargo Automation Fee"),
]


def normalise_description(desc):
    desc_lower = desc.lower()
    for key, standard in DESCRIPTION_MAP:
        if key.lower() in desc_lower:
            return standard
    return desc


def detect_source(p1_text):
    """Return 'AFER' if invoice number starts with S, else 'Mondiale'."""
    m = re.search(r'TAX INVOICE\s+([A-Z0-9]+)', p1_text)
    if m and m.group(1).startswith('S'):
        return "AFER"
    return "Mondiale"


# Matches an AFER charge line: <description> <GST annotation> <AUD amount>
_AFER_CHARGE_RE = re.compile(
    r'^(.+?)\s+'
    r'(Zero Rated|Exempt Rated|10%=[\d.]+)'
    r'\s+([\d,]+\.\d{2})$'
)

# Standardised descriptions that are charged per container in AFER invoices.
# For these lines: Qty = num_containers, Rate = AUD_amount / num_containers.
_PER_CONTAINER_DESCS = {
    "International Freight",
    "Heavy Weight Surcharge",
    "Port Service Charges",
    "Terminal Infrastructure Fee",
    "Intermodal Terminal Levy",
    "Cartage",
    "Delivery Booking Fees",
    "Sea Cargo Automation Fee",
}


def _count_containers(containers_str):
    """Count container IDs in a string like 'CMAU2893885 (20GP), CMAU2893967 (20GP)'."""
    return len(re.findall(r'[A-Z]{3,4}\d{6,7}', containers_str))


def _parse_afer_charges(p1_lines, header):
    rows = []
    in_charges     = False
    num_containers = _count_containers(header.get('Containers', ''))

    for line in p1_lines:
        line = line.strip()
        if "DESCRIPTION" in line and "CHARGES" in line:
            in_charges = True
            continue
        if not in_charges:
            continue
        if line.startswith(("SUBTOTAL", "ADD GST", "TOTAL", "Please contact")):
            break

        m = _AFER_CHARGE_RE.match(line)
        if not m:
            continue

        desc_raw   = m.group(1).strip()
        gst_ann    = m.group(2)
        amount_str = m.group(3)

        amount_ex  = float(amount_str.replace(',', ''))
        gst_flag   = "Y" if gst_ann.startswith("10%") else "N"
        gst_val    = round(amount_ex * 0.10, 2) if gst_flag == "Y" else 0.0
        amount_inc = round(amount_ex + gst_val, 2)

        if " - " in desc_raw:
            desc, details = desc_raw.split(" - ", 1)
            desc, details = desc.strip(), details.strip()
        else:
            desc, details = desc_raw, ""

        std_desc = normalise_description(desc)

        # Foreign currency amount embedded in description (e.g. "MAR FRT USD1450 OOCL")
        currency, fx_amount = "AUD", 0.0
        curr_m = re.search(r'\b(USD|EUR|GBP|CNY|NZD)([\d,]+(?:\.\d+)?)\b', desc_raw)
        if curr_m:
            currency  = curr_m.group(1)
            fx_amount = float(curr_m.group(2).replace(',', ''))

        # Qty and rate per unit
        if std_desc in _PER_CONTAINER_DESCS and num_containers > 0:
            qty = float(num_containers)
            # For foreign-currency freight, rate is the per-container FX amount (e.g. 700 USD);
            # for AUD charges the rate is the AUD amount split by container count.
            if currency != "AUD" and fx_amount > 0:
                rate = fx_amount
            else:
                rate = round(amount_ex / num_containers, 2)
        else:
            qty  = 1.0
            rate = round(amount_ex, 2)

        # Conversion rate: (qty * fx_rate) / aud_total  →  e.g. (2 * 700) / 2263.25 = 0.6185
        if currency != "AUD" and fx_amount > 0 and amount_ex > 0:
            conversion = round((qty * fx_amount) / amount_ex, 6)
        else:
            conversion = 1.0

        rows.append({
            **header,
            'Charge Code':             '',
            'Description':             desc,
            'Standardised Description': std_desc,
            'Details':                 details,
            'Qty':                     qty,
            'Currency':                currency,
            'Rate':                    rate,
            'Conversion Rate':         conversion,
            'GST Y/N':                 gst_flag,
            'Amount (Ex GST)':         round(amount_ex, 2),
            'GST':                     gst_val,
            'Amount (Inc GST)':        amount_inc,
        })

    return rows


def _parse_mondiale_charges(p1_lines, header):
    rows = []
    amount_pattern = re.compile(r'(\d{1,3}(?:,\d{3})*\.\d{2})$')

    i = 0
    while i < len(p1_lines):
        line = p1_lines[i].strip()
        if not re.match(r'^[A-Z]{4}', line):
            i += 1
            continue

        amount_match = amount_pattern.search(line)
        if not amount_match:
            i += 1
            continue

        amount_str = amount_match.group(1)
        amount_ex  = float(amount_str.replace(',', ''))
        rest_line  = line[:amount_match.start()].strip()
        parts      = rest_line.split('-')

        if len(parts) < 2:
            i += 1
            continue

        code      = parts[0].strip()
        remainder = "-".join(parts[1:]).strip()

        if " - " in remainder:
            rem_parts   = remainder.split(" - ", 1)
            desc        = rem_parts[0].strip()
            details     = rem_parts[1].strip()
        else:
            desc, details = remainder, ""

        qty = 1.0
        text_for_qty = details if details else desc
        qty_m = re.search(r'^(\d+)\s', text_for_qty)
        if qty_m:
            qty = float(qty_m.group(1))

        currency, rate, rate_unit = "AUD", 0.0, ""
        rate_m = re.search(r'@\s+([A-Z]{3})\s+([\d,]+\.\d{2})(?:/(\w+))?', text_for_qty)
        if rate_m:
            currency  = rate_m.group(1)
            rate      = float(rate_m.group(2).replace(',', ''))
            rate_unit = rate_m.group(3) or ""
        else:
            curr_m = re.search(r'@\s+([A-Z]{3})', text_for_qty)
            if curr_m:
                currency = curr_m.group(1)
            if i + 1 < len(p1_lines):
                next_line = p1_lines[i + 1].strip()
                rate_next = re.match(r'^([\d,]+\.\d{2})/(\w+)', next_line)
                if rate_next:
                    rate      = float(rate_next.group(1).replace(',', ''))
                    rate_unit = rate_next.group(2)

        conversion_rate = 1.0
        if currency != "AUD" and i + 1 < len(p1_lines):
            next_line = p1_lines[i + 1].strip()
            if re.match(r'^\d+\.\d+$', next_line):
                conversion_rate = float(next_line)

        details = re.sub(r'\s*10%=[\d.]+', '', details).strip()
        if rate_unit and f'{rate:.2f}/{rate_unit}' not in details:
            details = f"{details} {rate:.2f}/{rate_unit}".strip()

        gst_flag = "Y" if "10%" in rest_line else "N"
        gst_val  = round(amount_ex * 0.10, 2) if gst_flag == "Y" else 0.0
        amount_inc = round(amount_ex + gst_val, 2)

        rows.append({
            **header,
            'Charge Code':              code,
            'Description':              desc,
            'Standardised Description': normalise_description(desc),
            'Details':                  details,
            'Qty':                      qty,
            'Currency':                 currency,
            'Rate':                     rate,
            'Conversion Rate':          conversion_rate,
            'GST Y/N':                  gst_flag,
            'Amount (Ex GST)':          round(amount_ex, 2),
            'GST':                      gst_val,
            'Amount (Inc GST)':         amount_inc,
        })

        i += 1

    return rows


def parse_invoice(path):
    print(f"Parsing {path}...")

    with pdfplumber.open(path) as pdf:
        p1_text  = pdf.pages[0].extract_text()
        p1_lines = p1_text.split('\n')

        source = detect_source(p1_text)

        # --- Invoice number ---
        # Capture suffixes like "/A" on amended invoices — S00006192 and
        # S00006192/A are different invoices and must not collide.
        match_inv = re.search(r'TAX INVOICE(?:\s+-\s+\w+)?\s+([A-Z0-9]+(?:/[A-Z0-9]+)?)', p1_text)
        invoice_num = match_inv.group(1) if match_inv else ""

        # --- Dates ---
        m = re.search(r'INVOICE DATE:(\d{1,2}-[A-Za-z]{3}-\d{2})', p1_text)
        invoice_date = m.group(1) if m else ""

        m = re.search(r'DUE DATE:(\d{1,2}-[A-Za-z]{3}-\d{2})', p1_text)
        due_date = m.group(1) if m else ""

        # --- Shipment / Consol ---
        m = re.search(r'SHIPMENT:([A-Z0-9]+)', p1_text)
        shipment_ref = m.group(1) if m else ""

        m = re.search(r'CONSOL:([A-Z0-9]+)', p1_text)
        consol_ref = m.group(1) if m else ""

        # --- PO ---
        if source == "Mondiale":
            po_matches = re.findall(r'PO_0*(\d+)', p1_text)
            po_number = " / ".join(m[-4:] for m in po_matches)
        else:
            # AFER: "CLIENT / ORDER REFERENCE\nS00007518 / 5147"
            po_number = ""
            for i, line in enumerate(p1_lines):
                if "CLIENT" in line and "ORDER REFERENCE" in line:
                    if i + 1 < len(p1_lines):
                        ref_line = p1_lines[i + 1].strip()
                        ref_m = re.search(r'/\s*(\d+)\s*$', ref_line)
                        if ref_m:
                            po_number = ref_m.group(1)
                    break

        # --- Containers ---
        containers = ""
        for i, line in enumerate(p1_lines):
            if "CONTAINER NUMBER" in line:
                if i + 1 < len(p1_lines):
                    containers = p1_lines[i + 1].strip()
                break

        # --- Consignor ---
        consignor = ""
        for i, line in enumerate(p1_lines):
            if "CONSIGNOR" in line and "CONSIGNEE" in line:
                if i + 1 < len(p1_lines):
                    consignor = p1_lines[i + 1].strip()
                break

        # --- Origin / Destination / ETA ---
        origin = destination = eta = ""
        for i, line in enumerate(p1_lines):
            if "ORIGIN" in line and "DESTINATION" in line:
                eta_m = re.search(r'ETA\s+(\d{1,2}-[A-Za-z]{3}-\d{2})', line)
                if eta_m:
                    eta = eta_m.group(1)
                for j in range(1, 4):
                    if i + j < len(p1_lines):
                        loc_line = p1_lines[i + j].strip()
                        if "=" in loc_line:
                            loc_m = re.search(r'([A-Z0-9]{3,5})\s*=\s*(.+?)\s+([A-Z0-9]{3,5})\s*=\s*(.+)', loc_line)
                            if loc_m:
                                origin      = loc_m.group(2).split(',')[0].strip()
                                destination = loc_m.group(4).split(',')[0].strip()
                                break
                break

        # --- Packages ---
        packages = ""
        for page in pdf.pages:
            pkg_m = re.search(r'TOTAL NUMBER OF PACKAGES:\s*(\d+)', page.extract_text())
            if pkg_m:
                packages = pkg_m.group(1)
                break
        if not packages:
            # Column crop: pdfplumber separates the interleaved multi-column header text,
            # exposing the CTN/PKG count that appears garbled in plain extract_text().
            # Mondiale invoices use \d+CTN; AFER invoices use \d+PKG.
            for x0, x1 in [(470, 535), (440, 560)]:   # try narrow then wider crop
                col       = pdf.pages[0].crop((x0, 0, x1, pdf.pages[0].height))
                col_words = col.extract_words()
                ctn_idx   = next(
                    (i for i, w in enumerate(col_words) if re.match(r'^\d+(?:CTN|PKG)$', w['text'])),
                    None,
                )
                if ctn_idx is not None:
                    ctn_word = col_words[ctn_idx]
                    prefix   = ""
                    if ctn_idx > 0:
                        prev = col_words[ctn_idx - 1]
                        if abs(prev['top'] - ctn_word['top']) <= 5 and re.match(r'^\d+$', prev['text']):
                            prefix = prev['text']
                    raw_num = prefix + re.match(r'^(\d+)', ctn_word['text']).group(1)
                    n       = int(raw_num)
                    # Sanity check: guard against the crop picking up garbled non-CTN numbers
                    # (seen in AFER invoices whose header columns sit at different x positions).
                    # 100,000 CTN is far above any realistic single-invoice carton count.
                    if n < 100_000:
                        packages = str(n)
                        break

    header = {
        'Source':      source,
        'Invoice No':  invoice_num,
        'Date':        invoice_date,
        'Due Date':    due_date,
        'Shipment':    shipment_ref,
        'Consol':      consol_ref,
        'PO':          po_number,
        'Containers':  containers,
        'Consignor':   consignor,
        'Origin':      origin,
        'Destination': destination,
        'ETA':         eta,
        'Total Pkgs':  packages,
    }

    if source == "AFER":
        data = _parse_afer_charges(p1_lines, header)
    else:
        data = _parse_mondiale_charges(p1_lines, header)

    if data:
        total_ex  = sum(r['Amount (Ex GST)'] for r in data)
        total_inc = sum(r['Amount (Inc GST)'] for r in data)
        for r in data:
            r['Invoice Total (Ex GST)'] = round(total_ex, 2)
            r['Invoice Total (Inc GST)'] = round(total_inc, 2)

    return data
