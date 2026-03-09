import sys
import time
import logging
import os
import re
import hmac
import hashlib
import base64
import requests
from datetime import datetime, timezone
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
                wait_time = 10 * (attempt + 1)
            
            print(f"Hit rate limit (429). Waiting {wait_time}s before retry ({attempt+1}/{max_retries})...")
            time.sleep(wait_time)
            continue
        else:
            print("Failed to update invoice:", response.status_code, response.text)
            return None

    print(f"Failed to update invoice after {max_retries} attempts.")
    return None


def approveInvoiceAndBills(inv, related_bills, accessToken, xeroTenantId):
    inv["Status"] = "AUTHORISED"

    total_adjustment = 0.0
    rounding_line = None
    first_account_code = None
    
    for line in inv.get("LineItems", []):        
        description = line.get("Description", "")
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


def queryUnleashedSalesOrder(orderNumber, apiId, apiKey):
    """Query Unleashed for a sales order by order number. Returns the order dict or None."""
    query_string = f"orderNumber={orderNumber}"
    signature = base64.b64encode(
        hmac.new(apiKey.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")

    url = f"https://api.unleashedsoftware.com/SalesOrders?{query_string}"
    headers = {
        "api-auth-id": apiId,
        "api-auth-signature": signature,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        items = response.json().get("Items", [])
        return items[0] if items else None
    else:
        print(f"Failed to query Unleashed for {orderNumber}: {response.status_code} - {response.text}")
        return None


def parseUnleashedDate(date_str):
    """Parse an Unleashed date to a YYYY-MM-DD string Xero accepts.

    Handles both ISO 8601 ('2021-03-01T00:00:00') and
    JSON.NET ('/Date(1614556800000)/') formats.
    """
    if not date_str:
        return None
    s = str(date_str)
    match = re.search(r"/Date\((\d+)\)/", s)
    if match:
        dt = datetime.fromtimestamp(int(match.group(1)) / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    return s.split("T")[0]


def processStockAdjustmentJournals(bills, accessToken, xeroTenantId):
    """Stock Adjustment Journals (Journal-SA-*): set BAS Excluded + account 5010, approve."""
    for bill in bills:
        if bill.get("Contact", {}).get("Name", "") != "Stock Journal":
            continue
        inv_number = bill.get("InvoiceNumber", "")
        if not inv_number.startswith("Journal-SA-"):
            continue

        bill["Status"] = "AUTHORISED"
        for line in bill.get("LineItems", []):
            line["TaxType"] = "BASEXCLUDED"
            if line.get("AccountCode") == "5000":
                line["AccountCode"] = "5010"
            line.pop("TaxAmount", None)

        time.sleep(1)
        print(f"Approving stock adjustment journal: {inv_number}")
        response = xeroAPIUpdateBill(bill, accessToken, xeroTenantId)
        if response:
            print(f"Stock adjustment journal {inv_number} approved successfully.")
        else:
            print(f"Stock adjustment journal {inv_number} approval failed.")
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
        cn_type = cn.get("Type", "")
        is_bill_credit = cn_type == "ACCPAYCREDIT"

        if is_bill_credit:
            cn["Status"] = "AUTHORISED"

        for line in cn.get("LineItems", []):
            line["TaxType"] = "BASEXCLUDED"
            line.pop("TaxAmount", None)

        time.sleep(1)
        if is_bill_credit:
            print(f"Approving credit note (bill): {cn_number}")
        else:
            print(f"Saving credit note (invoice, draft): {cn_number}")
        response = xeroAPIUpdateCreditNote(cn, accessToken, xeroTenantId)
        if response:
            print(f"Credit note {cn_number} {'approved' if is_bill_credit else 'saved'} successfully.")
        else:
            print(f"Credit note {cn_number} {'approval' if is_bill_credit else 'save'} failed.")
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

    unleashed_api_id = os.getenv("FLIGHT_RISK_API_ID")
    unleashed_api_key = os.getenv("FLIGHT_RISK_API_KEY")

    print("--------------------------------------------------")
    for invoice in draftInvoices:
        time.sleep(1)
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

        completed_date = None
        if base_inv_number.startswith("SI-"):
            order = queryUnleashedSalesOrder(search_term, unleashed_api_id, unleashed_api_key)
            if not order:
                print(f"Unleashed: no order found for {search_term}, skipping.")
                continue
            order_status = order.get("OrderStatus", "")
            if order_status != "Completed":
                print(f"Unleashed: {search_term} not completed (status: {order_status}), skipping.")
                continue
            completed_date = parseUnleashedDate(order.get("CompletedDate"))
            print(f"Unleashed: {search_term} completed on {completed_date}.")

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

            if completed_date:
                invoice["Date"] = completed_date
                invoice["DueDate"] = completed_date
                print(f"Date set to Unleashed completed date: {completed_date}")

            approveInvoiceAndBills(invoice, related_bills, accessToken, xeroTenantId)
        else:
            print(f"No matching bills found for search term: {search_term}")
            print("ACTION: SKIPPING")

    processStockAdjustmentJournals(draftBills, accessToken, xeroTenantId)
    processRecostJournals(draftBills, accessToken, xeroTenantId)
    processSunRoadBills(draftBills, accessToken, xeroTenantId)
    processStockJournalCreditNotes(accessToken, xeroTenantId)

if __name__ == "__main__":
    main()
