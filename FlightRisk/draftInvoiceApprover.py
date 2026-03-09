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
    inv_number = inv.get("InvoiceNumber", "Unknown")
    results = []

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
        results.append((inv_number, "Invoice", "✅ Approved"))

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
            if billResponse:
                print(f"    [✓] Bill Approved")
                results.append((bill_num, "Bill", "✅ Approved"))
            else:
                print(f"    [X] Bill Approval Failed")
                results.append((bill_num, "Bill", "❌ Failed"))
    else:
        print(f"  [X] Invoice Approval Failed. Related bills will not be approved.")
        results.append((inv_number, "Invoice", "❌ Failed"))

    return results


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


def queryUnleashedPurchaseOrder(orderNumber, apiId, apiKey):
    """Query Unleashed for a purchase order by exact order number. Returns the order dict or None."""
    query_string = f"orderNumber={orderNumber}"
    signature = base64.b64encode(
        hmac.new(apiKey.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")

    url = f"https://api.unleashedsoftware.com/PurchaseOrders?{query_string}"
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


def processPOBills(bills, accessToken, xeroTenantId, unleashedApiId, unleashedApiKey):
    """PO bills (PO-XXXXXXXX[/N]): query Unleashed for completion date,
    shorten reference (strip first 4 digits), prepend full PO to descriptions, save as DRAFT.
    Skips bills prefixed with 'Cost#'."""
    pattern = re.compile(r"^(PO-(\d{8})(\/\d+)?)( - .+)?$")
    print(f"processPOBills: checking {len(bills)} bill(s) for PO pattern.")
    results = []

    for bill in bills:
        inv_number = bill.get("InvoiceNumber", "")
        if inv_number.startswith("Cost#"):
            continue
        match = pattern.match(inv_number)
        if not match:
            if inv_number.startswith("PO-"):
                print(f"  -> PO bill skipped (pattern mismatch): {inv_number}")
            continue

        full_po = match.group(1)              # e.g. PO-00000086/2 or PO-00005132
        numeric = match.group(2)              # e.g. 00000086 or 00005132
        suffix = match.group(3) or ""         # e.g. /2 or ""
        trailing = match.group(4) or ""       # e.g. " - PO-04-05 FIX CHANGE OF COLORS" or ""
        short_po = f"PO-{numeric[4:]}{suffix}{trailing}"  # e.g. PO-0086/2 - PO-04-05 FIX CHANGE OF COLORS

        order = queryUnleashedPurchaseOrder(full_po, unleashedApiId, unleashedApiKey)
        if order:
            order_status = order.get("OrderStatus", "")
            if order_status in ("Completed", "Complete"):
                completed_date = parseUnleashedDate(order.get("CompletedDate"))
                if completed_date:
                    bill["Date"] = completed_date
                    bill["DueDate"] = completed_date
                    print(f"Date updated from Unleashed: {completed_date}")
            else:
                print(f"Unleashed: {full_po} not completed (status: {order_status}), date not updated.")
        else:
            print(f"Unleashed: {full_po} not found, date not updated.")

        bill["InvoiceNumber"] = short_po
        for line in bill.get("LineItems", []):
            desc = line.get("Description", "")
            line["Description"] = f"{full_po} {desc}"
            if "UnitAmount" in line and "Quantity" in line:
                unit_amount = float(line["UnitAmount"])
                quantity = float(line["Quantity"])
                discount_rate = float(line.get("DiscountRate", 0))
                expected = round(unit_amount * quantity * (1 - discount_rate / 100), 2)
                if "LineAmount" in line and float(line["LineAmount"]) != expected:
                    print(f"  Adjusting LineAmount: {line['LineAmount']} → {expected}")
                    line["LineAmount"] = expected
            line.pop("TaxAmount", None)

        time.sleep(1)
        print(f"Saving PO bill: {inv_number} → {short_po}")
        response = xeroAPIUpdateBill(bill, accessToken, xeroTenantId)
        if response:
            print(f"PO bill {short_po} saved successfully.")
            results.append((inv_number, short_po, "✅ Saved"))
        else:
            print(f"PO bill {short_po} save failed.")
            results.append((inv_number, short_po, "❌ Failed"))
        print("--------------------------------------------------")
    return results


def processStockAdjustmentJournals(bills, accessToken, xeroTenantId):
    """Stock Adjustment Journals (Journal-SA-*): set BAS Excluded + account 5010, approve."""
    results = []
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
            results.append((inv_number, "✅ Approved"))
        else:
            print(f"Stock adjustment journal {inv_number} approval failed.")
            results.append((inv_number, "❌ Failed"))
        print("--------------------------------------------------")
    return results


def processRecostJournals(bills, accessToken, xeroTenantId):
    """Recost Journals (Journal - PO-*[ReCost]): set BAS Excluded + account 5020, approve."""
    results = []
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
            results.append((inv_number, "✅ Approved"))
        else:
            print(f"Recost journal {inv_number} approval failed.")
            results.append((inv_number, "❌ Failed"))
        print("--------------------------------------------------")
    return results


def write_github_summary(invoice_results, sa_results, recost_results, po_results):
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return

    def section(title, rows, headers):
        lines = [f"\n### {title} ({len(rows)})\n"]
        if not rows:
            lines.append("_None processed._\n")
            return "".join(lines)
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows:
            lines.append("| " + " | ".join(str(c) for c in row) + " |")
        lines.append("")
        return "\n".join(lines)

    with open(summary_file, "a") as f:
        f.write("## FlightRisk Draft Invoice & Bill Approver\n")
        f.write(section(
            "Invoices & Bills",
            invoice_results,
            ["Number", "Type", "Result"],
        ))
        f.write(section(
            "Stock Adjustment Journals",
            sa_results,
            ["Journal", "Result"],
        ))
        f.write(section(
            "Recost Journals",
            recost_results,
            ["Journal", "Result"],
        ))
        f.write(section(
            "PO Bills",
            po_results,
            ["Original", "Renamed", "Result"],
        ))


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

    invoice_results = []

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
            invoice_results.append((invNumber, "Invoice", "⚠️ Skipped (unexpected format)"))
            continue

        completed_date = None
        if base_inv_number.startswith("SI-"):
            order = queryUnleashedSalesOrder(search_term, unleashed_api_id, unleashed_api_key)
            if not order:
                print(f"Unleashed: no order found for {search_term}, skipping.")
                invoice_results.append((invNumber, "Invoice", "⚠️ Skipped (not in Unleashed)"))
                continue
            order_status = order.get("OrderStatus", "")
            if order_status not in ("Completed", "Complete"):
                print(f"Unleashed: {search_term} not completed (status: {order_status}), skipping.")
                invoice_results.append((invNumber, "Invoice", f"⚠️ Skipped (order {order_status})"))
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

            is_marketing_loan = False
            is_giveaways = False
            for bill in related_bills:
                bill_inv_num = bill.get("InvoiceNumber", "").upper()
                if "MARKETING" in bill_inv_num: is_marketing_loan = True
                if "GIVEAWAYS" in bill_inv_num: is_giveaways = True

            if is_marketing_loan:
                print(f"ACTION: SKIPPING (Reason: Bill is Marketing Loan, manually process)")
                invoice_results.append((invNumber, "Invoice", "⚠️ Skipped (marketing loan)"))
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

            invoice_results.extend(approveInvoiceAndBills(invoice, related_bills, accessToken, xeroTenantId))
        else:
            print(f"No matching bills found for search term: {search_term}")
            print("ACTION: SKIPPING")
            invoice_results.append((invNumber, "Invoice", "⚠️ Skipped (no matching bills)"))

    sa_results = processStockAdjustmentJournals(draftBills, accessToken, xeroTenantId)
    recost_results = processRecostJournals(draftBills, accessToken, xeroTenantId)
    po_results = processPOBills(draftBills, accessToken, xeroTenantId, unleashed_api_id, unleashed_api_key)

    write_github_summary(invoice_results, sa_results, recost_results, po_results)

if __name__ == "__main__":
    main()
