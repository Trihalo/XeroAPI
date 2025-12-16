import pdfplumber
import pandas as pd
import re
import os

import glob

invoices_dir = '/Users/leo/Github/XeroAPI/H2coco/mondiale/invoices'
pdf_files = glob.glob(os.path.join(invoices_dir, '*.PDF'))
csv_output_path = '/Users/leo/Github/XeroAPI/H2coco/mondiale/mondiale_invoices_combined.csv'

if not pdf_files: print(f"ERROR: No PDFs found in {invoices_dir}")
else: print(f"Found {len(pdf_files)} PDFs in {invoices_dir}")


def parse_invoice(path):
    print(f"Parsing {path}...")
    data = []
    
    invoice_num = ""
    invoice_date = ""
    due_date = ""
    shipment_ref = ""
    consol_ref = ""
    consignor = ""
    origin = ""
    destination = ""
    eta = ""
    packages = ""

    with pdfplumber.open(path) as pdf:
        p1_text = pdf.pages[0].extract_text()
        p1_lines = p1_text.split('\n')
        
        match_inv = re.search(r'TAX INVOICE\s+(\d+)', p1_text)
        if match_inv: invoice_num = match_inv.group(1)
        
        match_date = re.search(r'INVOICE DATE:(\d{1,2}-[A-Za-z]{3}-\d{2})', p1_text)
        if match_date: invoice_date = match_date.group(1)
        
        match_due = re.search(r'DUE DATE:(\d{1,2}-[A-Za-z]{3}-\d{2})', p1_text)
        if match_due: due_date = match_due.group(1)
        
        match_ship = re.search(r'SHIPMENT:([A-Z0-9]+)', p1_text)
        if match_ship: shipment_ref = match_ship.group(1)
        
        match_consol = re.search(r'CONSOL:([A-Z0-9]+)', p1_text)
        if match_consol: consol_ref = match_consol.group(1)
        
        po_number = ""
        for i, line in enumerate(p1_lines):
            if "ORDER REFERENCE" in line: 
                if i + 1 < len(p1_lines):
                    raw_ref = p1_lines[i+1].strip()
                    match_po = re.search(r'PO_0*(\d+)', raw_ref)
                    if match_po:
                        full_digits = match_po.group(1)
                        po_number = full_digits[-4:]
                break
        
        for i, line in enumerate(p1_lines):
            if "CONSIGNOR" in line and "CONSIGNEE" in line:
                if i + 1 < len(p1_lines):
                    consignor = p1_lines[i+1].strip()
                break

        for i, line in enumerate(p1_lines):
            if "ORIGIN" in line and "DESTINATION" in line:
                match_eta = re.search(r'ETA\s+(\d{1,2}-[A-Za-z]{3}-\d{2})', line)
                if match_eta: eta = match_eta.group(1)
                
                for j in range(1, 4):
                    if i + j < len(p1_lines):
                        loc_line = p1_lines[i+j].strip()
                        if "=" in loc_line:
                            match_loc = re.search(r'([A-Z0-9]{3,5})\s*=\s*(.+?)\s+([A-Z0-9]{3,5})\s*=\s*(.+)', loc_line)
                            if match_loc:
                                origin = match_loc.group(2).split(',')[0].strip()
                                destination = match_loc.group(4).split(',')[0].strip()
                                break
                break

        # --- Page 2 Analysis ---
        if len(pdf.pages) > 1:
            p2_text = pdf.pages[1].extract_text()
            match_pkg = re.search(r'TOTAL NUMBER OF PACKAGES:\s*(\d+)', p2_text)
            if match_pkg:
                packages = match_pkg.group(1)

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
            amount_ex = float(amount_str.replace(',', ''))
            rest_line = line[:amount_match.start()].strip()
            parts = rest_line.split('-')
            
            if len(parts) < 2:
                i += 1
                continue
                
            code = parts[0].strip()
            remainder = "-".join(parts[1:]).strip()
            
            desc = ""
            details = ""
            if " - " in remainder:
                rem_parts = remainder.split(" - ", 1)
                desc = rem_parts[0].strip()
                details = rem_parts[1].strip()
            else:
                desc = remainder
                details = ""
            
            qty = 1.0
            text_for_qty = details if details else desc
            qty_match = re.search(r'^(\d+)\s', text_for_qty)
            if qty_match: qty = float(qty_match.group(1))

            currency = "AUD"
            rate = 0.0

            rate_match = re.search(r'@\s+([A-Z]{3})\s+([\d,]+\.\d{2})', text_for_qty)
            if rate_match:
                currency = rate_match.group(1)
                rate = float(rate_match.group(2).replace(',', ''))
            elif re.search(r'@\s+AUD\s+', text_for_qty): currency = "AUD"
                 
            conversion_rate = 1.0
            if currency == "AUD": conversion_rate = 1.0
            elif i + 1 < len(p1_lines):
                next_line = p1_lines[i+1].strip()
                if re.match(r'^\d+\.\d+$', next_line): conversion_rate = float(next_line)

            # GST Logic
            gst_applies = "10%" in (details + desc)
            gst_flag = "Y" if gst_applies else "N"
            
            gst_val = 0.0
            if gst_applies:
                gst_val = amount_ex * 0.10
                amount_inc = amount_ex + gst_val
            else:
                amount_inc = amount_ex

            data.append({
                'Invoice No': invoice_num,
                'Date': invoice_date,
                'Due Date': due_date,
                'Shipment': shipment_ref,
                'Consol': consol_ref,
                'PO': po_number,
                'Consignor': consignor,
                'Origin': origin,
                'Destination': destination,
                'ETA': eta,
                'Total Pkgs': packages,
                
                'Charge Code': code,
                'Description': desc,
                'Details': details,
                'Qty': qty,
                'Currency': currency,
                'Rate': rate,
                'Conversion Rate': conversion_rate,
                'GST Y/N': gst_flag,
                'Amount (Ex GST)': round(amount_ex, 2),
                'GST': round(gst_val, 2),
                'Amount (Inc GST)': round(amount_inc, 2)
            })
            
            i += 1
            
    if data:
        total_ex = sum(item['Amount (Ex GST)'] for item in data)
        total_inc = sum(item['Amount (Inc GST)'] for item in data)
        for item in data:
            item['Invoice Total (Ex GST)'] = round(total_ex, 2)
            item['Invoice Total (Inc GST)'] = round(total_inc, 2)

    return data


if __name__ == "__main__":
    all_data = []
    
    for pdf_file in pdf_files:
        try:
            invoice_data = parse_invoice(pdf_file)
            if invoice_data:
                all_data.extend(invoice_data)
        except Exception as e:
            print(f"Failed to parse {pdf_file}: {e}")
            
    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv(csv_output_path, index=False)
        print(f"Successfully converted all invoices. {len(df)} rows written to {csv_output_path}")
        print(df[['Invoice No', 'Invoice Total (Inc GST)', 'PO']].drop_duplicates())
    else:
        print("No data extracted from any invoice.")
