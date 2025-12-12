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
        if description == "Rounding":
            rounding_line = line
            continue
        
        if not first_account_code and line.get("AccountCode"):
            first_account_code = line["AccountCode"]

        if "UnitAmount" in line and "Quantity" in line:
            unit_amount = float(line["UnitAmount"])
            quantity = float(line["Quantity"])
            discount_rate = float(line.get("DiscountRate", 0))
            
            subtotal = unit_amount * quantity
            discount_multiplier = 1 - (discount_rate / 100)
            expected_line_amount = round(subtotal * discount_multiplier, 2)
            
            if "LineAmount" in line:
                current_line_amount = float(line["LineAmount"])
                if current_line_amount != expected_line_amount:
                    diff = expected_line_amount - current_line_amount
                    print(f"Adjusting LineAmount for {description} from {current_line_amount} to {expected_line_amount} (Diff: {diff})")
                    line["LineAmount"] = expected_line_amount
                    total_adjustment += diff

    if total_adjustment != 0:
        adjustment_amount = round(-total_adjustment, 2)
        
        rounding_account_code = first_account_code if first_account_code else "PLACEHOLDER_CODE"

        if rounding_line:
            current_rounding = float(rounding_line.get("LineAmount", 0))
            new_rounding = round(current_rounding + adjustment_amount, 2)
            print(f"Adjusting existing Rounding line from {current_rounding} to {new_rounding}")
            rounding_line["LineAmount"] = new_rounding
            rounding_line["UnitAmount"] = new_rounding
            rounding_line["AccountCode"] = rounding_account_code
        else:
            print(f"Creating new Rounding line with amount {adjustment_amount}")
            new_rounding_line = {
                "Description": "Rounding",
                "Quantity": 1.0,
                "UnitAmount": adjustment_amount,
                "LineAmount": adjustment_amount,
                "AccountCode": rounding_account_code,
                "TaxType": "BASEXCLUDED"
            }
            if inv.get("LineItems"):
                 new_rounding_line["TaxType"] = inv["LineItems"][0].get("TaxType", "OUTPUT")

            inv["LineItems"].append(new_rounding_line)

    for line in inv.get("LineItems", []): line.pop("TaxAmount", None)
    for bill in related_bills:
        for line in bill.get("LineItems", []): line.pop("TaxAmount", None)

    print(f"Approving Invoice...")
    
    invoiceResponse = xeroAPIUpdateBill(inv, accessToken, xeroTenantId)
    if invoiceResponse:
        updated_invoice = invoiceResponse.get("Invoices", [{}])[0]
        pre_total = inv.get("Total")
        post_total = updated_invoice.get("Total")
        print(f"  [✓] Invoice Approved. Total: {pre_total} -> {post_total}")
        
        for i, bill in enumerate(related_bills, 1):
            bill_num = bill.get('InvoiceNumber', 'No Invoice Number')
            print(f"  > Processing Bill {i}/{len(related_bills)}: {bill_num}")
            
            bill["Status"] = "AUTHORISED"
            for line in bill.get("LineItems", []): line["TaxType"] = "BASEXCLUDED"
            invoiceDate = inv.get("Date", None)
            if invoiceDate:
                bill["Date"] = invoiceDate
                bill["DueDate"] = invoiceDate

            billResponse = xeroAPIUpdateBill(bill, accessToken, xeroTenantId)
            if billResponse: print(f"    [✓] Bill Approved")
            else: print(f"    [X] Bill Approval Failed")
    else: print(f"  [X] Invoice Approval Failed. Related bills will not be approved.")


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
        print(f"\n{'='*60}")
        print(f"PROCESSING INVOICE: {invNumber}")
        print(f"{'-'*60}")

        if not search_term:
            logging.warning(f"Skipping invoice with unexpected format: {invNumber}")
            print("ACTION: SKIPPING (Reason: Unexpected invoice format)")
            continue
        
        related_bills = [
            bill for bill in draftBills 
            if search_term in bill.get("InvoiceNumber", "")
        ]
        
        if related_bills:
            bill_count = len(related_bills)
            split_msg = " (SPLIT SHIPMENT)" if bill_count > 1 else ""
            print(f"Found {bill_count} related bill(s){split_msg}")

            # Check for Marketing Loan in related bills
            is_marketing_loan = False
            is_giveaways = False
            for bill in related_bills:
                bill_inv_num = bill.get("InvoiceNumber", "").upper()
                if "MARKETING" in bill_inv_num: is_marketing_loan = True
                if "GIVEAWAYS" in bill_inv_num: is_giveaways = True
            
            if is_marketing_loan:
                print(f"ACTION: SKIPPING (Reason: Bill is Marketing Loan, manually process)")
                continue

            if is_giveaways:
                print(f"ACTION: PROCESSING AS GIVEAWAYS")                
                for bill in related_bills:
                     for line in bill.get("LineItems", []):
                        if line.get("AccountCode") == "5001": 
                            print(f"  -> Updating Bill Line AccountCode from 5001 to 5560")
                            line["AccountCode"] = "5560"

            approveInvoiceAndBills(invoice, related_bills, accessToken, xeroTenantId)
        else:
            print(f"No matching bills found for search term: {search_term}")
            print("ACTION: SKIPPING")
                
    
if __name__ == "__main__":
    main()
