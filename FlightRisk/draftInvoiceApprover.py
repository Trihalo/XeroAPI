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


def approveInvoiceAndBills(inv, related_bills, accessToken, xeroTenantId):
    inv["Status"] = "AUTHORISED"

    total_adjustment = 0.0
    rounding_line = None
    first_account_code = None
    
    for line in inv.get("LineItems", []):
        if "AccountCode" not in line or not line["AccountCode"]:
            line["AccountCode"] = "PLACEHOLDER_CODE"
        
        # Capture the first account code to use for rounding if needed
        if not first_account_code and line.get("AccountCode"):
            first_account_code = line["AccountCode"]
        
        description = line.get("Description", "")
        if description.startswith("Invoice Comments:"):
            inv["LineItems"].remove(line)
            continue
        
        if description == "Rounding":
            rounding_line = line
            continue
        
        if "UnitAmount" in line and "Quantity" in line:
            unit_amount = float(line["UnitAmount"])
            quantity = float(line["Quantity"])
            expected_line_amount = round(unit_amount * quantity, 2)
            if "LineAmount" in line:
                current_line_amount = float(line["LineAmount"])
                if current_line_amount != expected_line_amount:
                    diff = expected_line_amount - current_line_amount
                    print(f"Adjusting LineAmount for {description} from {current_line_amount} to {expected_line_amount} (Diff: {diff})")
                    line["LineAmount"] = expected_line_amount
                    total_adjustment += diff

    # Apply the inverse of the total adjustment to the Rounding line
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
                "AccountCode": first_account_code if first_account_code else "PLACEHOLDER_CODE",
                "TaxType": "BASEXCLUDED"
            }
            if inv.get("LineItems"):
                 new_rounding_line["TaxType"] = inv["LineItems"][0].get("TaxType", "OUTPUT")

            inv["LineItems"].append(new_rounding_line)

    for line in inv.get("LineItems", []): line.pop("TaxAmount", None)
    for line in bill.get("LineItems", []): line.pop("TaxAmount", None)

    print(f"Approving Invoice: {inv['InvoiceNumber']} with {len(related_bills)} related bills.")
    
    invoiceResponse = xeroAPIUpdateBill(inv, accessToken, xeroTenantId)
    if invoiceResponse:
        print(f"Invoice {inv['InvoiceNumber']} updated successfully.")
        for bill in related_bills:
            print(f"Approving Bill: {bill.get('InvoiceNumber', 'No Invoice Number')}")
            
            bill["Status"] = "AUTHORISED"
            for line in bill.get("LineItems", []): line["TaxType"] = "BASEXCLUDED"
            invoiceDate = inv.get("Date", None)
            if invoiceDate:
                bill["Date"] = invoiceDate
                bill["DueDate"] = invoiceDate

            billResponse = xeroAPIUpdateBill(bill, accessToken, xeroTenantId)
            if billResponse:
                print(f"Bill {bill.get('InvoiceNumber')} approved successfully.")
            else:
                print(f"Bill {bill.get('InvoiceNumber')} approval failed.")
    else:
        print(f"Invoice {inv['InvoiceNumber']} approval failed. Related bills will not be approved.")
    
    print("--------------------------------------------------")


def main():
    
    client = "FLIGHT_RISK"
    invoiceStatus = "DRAFT"
    try:
        invoices, accessToken, xeroTenantId = fetchInvoicesForClient(client, invoiceStatus)
    except Exception as e:
        logging.error(f"Error fetching data: {e}")
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
        invNumber = invoice.get("InvoiceNumber", "No Invoice Number")
        base_inv_number = invNumber.split('/')[0]
        
        search_term = None
        
        if base_inv_number.startswith("FRC#"): search_term = base_inv_number
        elif base_inv_number.startswith("SI-"):
            parts = base_inv_number.split("-")
            if len(parts) > 1: search_term = "SO-" + parts[1]
        if not search_term:
            logging.warning(f"Skipping invoice with unexpected format: {invNumber}")
            continue
        related_bills = [
            bill for bill in draftBills 
            if search_term in bill.get("InvoiceNumber", "")
        ]
        
        if related_bills:
            approveInvoiceAndBills(invoice, related_bills, accessToken, xeroTenantId)
        else:
            print(f"Invoice {invNumber} (Search: {search_term}) found but no matching bills. Skipping.")
                
    
if __name__ == "__main__":
    main()
