import sys
import time
import logging
import os
import re
import requests
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from helpers.fetchInvoicesForClient import fetchInvoicesForClient


def xeroAPIUpdateBill(invoice, accessToken, xeroTenantId):
    url = f"https://api.xero.com/api.xro/2.0/Invoices/{invoice.get('InvoiceID')}"
    headers = {
        "Authorization": f"Bearer {accessToken}",
        "Xero-tenant-id": xeroTenantId,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    update_fields = [
        "Type", "Date", "DueDate", "Status", "LineItems", "InvoiceNumber",
    ]

    payload = {k: v for k, v in invoice.items() if k in update_fields and v is not None}

    max_retries = 5
    for attempt in range(max_retries):
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code in [200, 201]:        
            return response.json()
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                wait_time = int(retry_after) + 1
            else:
                wait_time = 10 * (attempt + 1) # simple backoff
            
            print(f"Rate limit (429): waiting {wait_time}s before retry ({attempt+1}/{max_retries})...")
            time.sleep(wait_time)
            continue
        else:
            print(f"Failed to update invoice: {response.status_code} - {response.text}")
            return None

    print(f"Failed to update invoice after {max_retries} attempts.")
    return None
    

def approveDraftInvoiceAndBills(inv, related_bills, accessToken, xeroTenantId):
    newZealand = False
    marketing = False
    
    # Check flags across ALL related bills
    for bill in related_bills:
        if "New Zealand" in bill.get("InvoiceNumber", ""): newZealand = True
        if "Marketing" in bill.get("InvoiceNumber", ""): marketing = True
        
    # change the status of the invoice and bill to AUTHORISED
    inv["Status"] = "AUTHORISED"
    
    total_adjustment = 0.0
    rounding_line = None
    first_account_code = None

    for line in inv.get("LineItems", []):
        if "AccountCode" not in line or not line["AccountCode"]: line["AccountCode"] = "5000" if not newZealand else "5001"
        if not first_account_code and line.get("AccountCode"): first_account_code = line["AccountCode"]

        description = line.get("Description", "")
        if description.startswith("Invoice Comments:"):
            inv["LineItems"].remove(line)
            continue
        
        if description == "Rounding":
            rounding_line = line
            continue
        # Recalculate LineAmount to avoid rounding errors
        # Xero expects LineAmount = round(UnitAmount * Quantity * (1 - DiscountRate/100), 2)
        if "UnitAmount" in line and "Quantity" in line:
            unit_amount = float(line["UnitAmount"])
            quantity = float(line["Quantity"])
            discount_rate = float(line.get("DiscountRate", 0))
            
            subtotal = unit_amount * quantity
            discount_multiplier = 1 - (discount_rate / 100)
            expected_line_amount = round(subtotal * discount_multiplier, 2)
            
            # If there's a mismatch, update the LineAmount
            if "LineAmount" in line:
                current_line_amount = float(line["LineAmount"])
                if current_line_amount != expected_line_amount:
                    diff = expected_line_amount - current_line_amount
                    print(f"Adjusting line amount for '{description}': {current_line_amount} → {expected_line_amount} (diff: {diff})")
                    line["LineAmount"] = expected_line_amount
                    total_adjustment += diff

    if total_adjustment != 0:
        adjustment_amount = round(-total_adjustment, 2)
        
        if rounding_line:
            current_rounding = float(rounding_line.get("LineAmount", 0))
            new_rounding = round(current_rounding + adjustment_amount, 2)
            print(f"Adjusting rounding line: {current_rounding} → {new_rounding}")
            rounding_line["LineAmount"] = new_rounding
            rounding_line["UnitAmount"] = new_rounding
        else:
            print(f"Adding rounding line: {adjustment_amount}")
            new_rounding_line = {
                "Description": "Rounding",
                "Quantity": 1.0,
                "UnitAmount": adjustment_amount,
                "LineAmount": adjustment_amount,
                "AccountCode": first_account_code if first_account_code else ("5000" if not newZealand else "5001"),
                "TaxType": "BASEXCLUDED"
            }

            if inv.get("LineItems"):
                 new_rounding_line["TaxType"] = inv["LineItems"][0].get("TaxType", "OUTPUT")

            inv["LineItems"].append(new_rounding_line)
    
    # Process modifications for ALL matching bills
    for bill in related_bills:
        bill["Status"] = "AUTHORISED"
        
        # change the Tax account to "BAS Excluded" for bill for both line items
        for line in bill.get("LineItems", []): line["TaxType"] = "BASEXCLUDED"
            
        # set the bill date & date string to match the invoice date
        invoiceDate = inv.get("Date", None)
        if invoiceDate:
            bill["Date"] = invoiceDate
            bill["DueDate"] = invoiceDate
        
        # Case 1: NZL Invoice - change 5000 account code to 5001
        if newZealand:
            for line in bill.get("LineItems", []):
                if line.get("AccountCode") == "5000": line["AccountCode"] = "5001"
                
        # Case 2: Marketing Invoice - change 5000 account code to 5465
        if marketing:
            for line in bill.get("LineItems", []):
                if line.get("AccountCode") == "5000": line["AccountCode"] = "5465"

        for line in bill.get("LineItems", []): line.pop("TaxAmount", None)
            
    for line in inv.get("LineItems", []): line.pop("TaxAmount", None)
    
    
    print(f"Approving invoice: {inv['InvoiceNumber']} ({len(related_bills)} bill(s))")
    invoiceResponse = xeroAPIUpdateBill(inv, accessToken, xeroTenantId)

    if invoiceResponse:
        updated_invoice = invoiceResponse.get("Invoices", [{}])[0]
        pre_total = inv.get("Total")
        post_total = updated_invoice.get("Total")
        print(f"Invoice {inv['InvoiceNumber']} approved successfully. Pre-total: {pre_total}, Post-total: {post_total}")

        for bill in related_bills:
            billResponse = xeroAPIUpdateBill(bill, accessToken, xeroTenantId)
            if billResponse:
                print(f"Bill {bill['InvoiceNumber']} approved successfully.")
            else:
                print(f"Bill {bill['InvoiceNumber']} approval failed.")
    else:
        invoice_number = inv.get("InvoiceNumber", "")
        print(f"Invoice {invoice_number} approval failed, bills not updated.")

    
    print("--------------------------------------------------")


def processStockAdjustmentJournals(bills, accessToken, xeroTenantId):
    """Stock Adjustment Journals (Journal-SA-*): set BAS Excluded + account 5010, keep DRAFT."""
    for bill in bills:
        if bill.get("Contact", {}).get("Name", "") != "Stock Journal":
            continue
        inv_number = bill.get("InvoiceNumber", "")
        if not inv_number.startswith("Journal-SA-"):
            continue

        for line in bill.get("LineItems", []):
            line["TaxType"] = "BASEXCLUDED"
            if line.get("AccountCode") == "5000":
                line["AccountCode"] = "5010"
            line.pop("TaxAmount", None)

        time.sleep(1)
        print(f"Saving stock adjustment journal: {inv_number}")
        response = xeroAPIUpdateBill(bill, accessToken, xeroTenantId)
        if response:
            print(f"Stock adjustment journal {inv_number} saved successfully.")
        else:
            print(f"Stock adjustment journal {inv_number} save failed.")
        print("--------------------------------------------------")


def processRecostJournals(bills, accessToken, xeroTenantId):
    """Recost Journals (Journal - PO-*[ReCost]): set BAS Excluded + account 5020, approve."""
    for bill in bills:
        if bill.get("Contact", {}).get("Name", "") != "Stock Journal":
            continue
        inv_number = bill.get("InvoiceNumber", "")
        if not (inv_number.startswith("Journal - PO-") and inv_number.endswith("[ReCost]")):
            continue

        bill["Status"] = "AUTHORISED"
        for line in bill.get("LineItems", []):
            line["TaxType"] = "BASEXCLUDED"
            if line.get("AccountCode") == "5000":
                line["AccountCode"] = "5020"
            line.pop("TaxAmount", None)

        time.sleep(1)
        print(f"Approving recost journal: {inv_number}")
        response = xeroAPIUpdateBill(bill, accessToken, xeroTenantId)
        if response:
            print(f"Recost journal {inv_number} approved successfully.")
        else:
            print(f"Recost journal {inv_number} approval failed.")
        print("--------------------------------------------------")


def processSunRoadBills(bills, accessToken, xeroTenantId):
    """Stock Journals with 'Sun Road Food & Beverage - CDS' in reference: set BAS Excluded, approve."""
    for bill in bills:
        if bill.get("Contact", {}).get("Name", "") != "Stock Journal":
            continue
        inv_number = bill.get("InvoiceNumber", "")
        if "Sun Road Food & Beverage - CDS" not in inv_number:
            continue

        bill["Status"] = "AUTHORISED"
        for line in bill.get("LineItems", []):
            line["TaxType"] = "BASEXCLUDED"
            line.pop("TaxAmount", None)

        time.sleep(1)
        print(f"Approving Sun Road bill: {inv_number}")
        response = xeroAPIUpdateBill(bill, accessToken, xeroTenantId)
        if response:
            print(f"Sun Road bill {inv_number} approved successfully.")
        else:
            print(f"Sun Road bill {inv_number} approval failed.")
        print("--------------------------------------------------")


def fetchStockJournalCreditNotes(accessToken, xeroTenantId):
    """Fetch draft credit notes from the Xero CreditNotes endpoint."""
    url = "https://api.xero.com/api.xro/2.0/CreditNotes"
    headers = {
        "Authorization": f"Bearer {accessToken}",
        "Xero-tenant-id": xeroTenantId,
        "Accept": "application/json",
    }
    response = requests.get(url, headers=headers, params={"Statuses": ["DRAFT"], "pageSize": 1000})
    if response.status_code == 200:
        return response.json().get("CreditNotes", [])
    else:
        print(f"Failed to fetch credit notes: {response.status_code} - {response.text}")
        return []


def xeroAPIUpdateCreditNote(credit_note, accessToken, xeroTenantId):
    """POST an update to a Xero CreditNote."""
    url = f"https://api.xero.com/api.xro/2.0/CreditNotes/{credit_note.get('CreditNoteID')}"
    headers = {
        "Authorization": f"Bearer {accessToken}",
        "Xero-tenant-id": xeroTenantId,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    update_fields = ["Type", "Date", "Status", "LineItems"]
    payload = {k: v for k, v in credit_note.items() if k in update_fields and v is not None}

    max_retries = 5
    for attempt in range(max_retries):
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            return response.json()
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait_time = int(retry_after) + 1 if retry_after else 10 * (attempt + 1)
            print(f"Rate limit (429): waiting {wait_time}s before retry ({attempt+1}/{max_retries})...")
            time.sleep(wait_time)
            continue
        else:
            print(f"Failed to update credit note: {response.status_code} - {response.text}")
            return None

    print(f"Failed to update credit note after {max_retries} attempts.")
    return None


def processStockJournalCreditNotes(accessToken, xeroTenantId):
    """Stock Journal credit notes: set BAS Excluded, approve."""
    credit_notes = fetchStockJournalCreditNotes(accessToken, xeroTenantId)
    for cn in credit_notes:
        if cn.get("Contact", {}).get("Name", "") != "Stock Journal":
            continue

        cn_number = cn.get("CreditNoteNumber", cn.get("InvoiceNumber", ""))
        cn["Status"] = "AUTHORISED"
        for line in cn.get("LineItems", []):
            line["TaxType"] = "BASEXCLUDED"
            line.pop("TaxAmount", None)

        time.sleep(1)
        print(f"Approving credit note: {cn_number}")
        response = xeroAPIUpdateCreditNote(cn, accessToken, xeroTenantId)
        if response:
            print(f"Credit note {cn_number} approved successfully.")
        else:
            print(f"Credit note {cn_number} approval failed.")
        print("--------------------------------------------------")


def processPOBills(bills, accessToken, xeroTenantId):
    """PO bills (PO-XXXXXXXX - PO-XXXXXXXX): shorten reference and prepend full PO to line item descriptions, save as DRAFT."""
    pattern = re.compile(r"^(PO-(\d{8})) - PO-\d{8}$")

    for bill in bills:
        inv_number = bill.get("InvoiceNumber", "")
        match = pattern.match(inv_number)
        if not match:
            continue

        full_po = match.group(1)                      # e.g. PO-00005132
        short_po = f"PO-{int(match.group(2))}"        # e.g. PO-5132

        bill["InvoiceNumber"] = short_po
        for line in bill.get("LineItems", []):
            desc = line.get("Description", "")
            line["Description"] = f"{full_po} {desc}"

        time.sleep(1)
        print(f"Saving PO bill: {inv_number} → {short_po}")
        response = xeroAPIUpdateBill(bill, accessToken, xeroTenantId)
        if response:
            print(f"PO bill {short_po} saved successfully.")
        else:
            print(f"PO bill {short_po} save failed.")
        print("--------------------------------------------------")


def main():
    
    client = "H2COCO"
    invoiceStatus = "DRAFT"
    try:
        invoices, accessToken, xeroTenantId = fetchInvoicesForClient(client, invoiceStatus)
    except Exception as e:
        logging.error(f"Error fetching invoices: {e}")
        return
    
    draftInvoices = [
        invoice for invoice in invoices
        if isinstance(invoice, dict) and invoice.get("Type") == "ACCREC"
    ]
    
    draftBills = [
        invoice for invoice in invoices
        if isinstance(invoice, dict) and invoice.get("Type") == "ACCPAY"
    ]
    print("--------------------------------------------------")
    for invoice in draftInvoices:
        time.sleep(1)
        # get the matching billID for each draft invoice
        invNumber = invoice.get("InvoiceNumber", "No Invoice Number")
        if not invNumber.startswith("SI-"):
            logging.warning(f"Skipping invoice with unexpected format: {invNumber}")
            continue
        
        soNumber = "SO-" + invNumber.split("-")[1]
        
        related_bills = []
        for bill in draftBills:
            if soNumber in bill.get("InvoiceNumber", ""):
                related_bills.append(bill)
        
        if related_bills:
            approveDraftInvoiceAndBills(invoice, related_bills, accessToken, xeroTenantId)

    processStockAdjustmentJournals(draftBills, accessToken, xeroTenantId)
    processRecostJournals(draftBills, accessToken, xeroTenantId)
    processSunRoadBills(draftBills, accessToken, xeroTenantId)
    processStockJournalCreditNotes(accessToken, xeroTenantId)
    processPOBills(draftBills, accessToken, xeroTenantId)

if __name__ == "__main__":
    main()