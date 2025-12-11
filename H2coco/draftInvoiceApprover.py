import sys
import logging
import os
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
        "Type", "Date", "DueDate", "Status", "LineItems",
    ]

    payload = {k: v for k, v in invoice.items() if k in update_fields and v is not None}

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code in [200, 201]:        
        return response.json()
    else:
        print("Failed to update invoice:", response.status_code, response.text)
        return None
    

def approveDraftInvoiceAndBill(inv, bill, accessToken, xeroTenantId):
    newZealand = False
    marketing = False
    if "New Zealand" in bill.get("InvoiceNumber", ""): newZealand = True
    if "Marketing" in bill.get("InvoiceNumber", ""): marketing = True
        
    # change the status of the invoice and bill to AUTHORISED
    inv["Status"] = "AUTHORISED"
    bill["Status"] = "AUTHORISED"
    
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
                    print(f"Adjusting LineAmount for {description} from {current_line_amount} to {expected_line_amount} (Diff: {diff})")
                    line["LineAmount"] = expected_line_amount
                    total_adjustment += diff

    if total_adjustment != 0:
        adjustment_amount = round(-total_adjustment, 2)
        
        if rounding_line:
            current_rounding = float(rounding_line.get("LineAmount", 0))
            new_rounding = round(current_rounding + adjustment_amount, 2)
            print(f"Adjusting existing Rounding line from {current_rounding} to {new_rounding}")
            rounding_line["LineAmount"] = new_rounding
            rounding_line["UnitAmount"] = new_rounding
        else:
            print(f"Creating new Rounding line with amount {adjustment_amount}")
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
            
    for line in inv.get("LineItems", []): line.pop("TaxAmount", None)
    for line in bill.get("LineItems", []): line.pop("TaxAmount", None)
    
    print(f"Approving Invoice: {inv['InvoiceNumber']} and Bill: {bill['InvoiceNumber']}")
    invoiceResponse = xeroAPIUpdateBill(inv, accessToken, xeroTenantId)
    
    if invoiceResponse:
        updated_invoice = invoiceResponse.get("Invoices", [{}])[0]
        pre_total = inv.get("Total")
        post_total = updated_invoice.get("Total")
        print(f"Invoice {inv['InvoiceNumber']} updated successfully. Pre-Total: {pre_total}, Post-Total: {post_total}")
        
        billResponse = xeroAPIUpdateBill(bill, accessToken, xeroTenantId)
        if billResponse:
            print(f"Invoice {bill['InvoiceNumber']} updated successfully.")
        else: print("Bill update failed.")
    else:
        invoice_number = inv.get("InvoiceNumber", "")
        print(f"Invoice: {invoice_number} approval failed, bill not updated.")

    
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
        # get the matching billID for each draft invoice
        invNumber = invoice.get("InvoiceNumber", "No Invoice Number")
        if not invNumber.startswith("SI-"):
            logging.warning(f"Skipping invoice with unexpected format: {invNumber}")
            continue
        soNumber = "SO-" + invNumber.split("-")[1]
        for bill in draftBills:
            if soNumber in bill.get("InvoiceNumber", ""):
                # Approve the draft invoice and draft bill, matching the bill date to the invoice date
                approveDraftInvoiceAndBill(invoice, bill, accessToken, xeroTenantId)
                

        
if __name__ == "__main__":
    main()