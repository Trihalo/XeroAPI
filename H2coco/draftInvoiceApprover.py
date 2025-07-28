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
    
    # Make sure that the invoice has account codes on each line item
    for line in inv.get("LineItems", []):
        if "AccountCode" not in line or not line["AccountCode"]:
            line["AccountCode"] = "5000" if not newZealand else "5001"
    
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
    
    # update the invoice and bill using Xero API
    print(f"Approving Invoice: {inv['InvoiceNumber']} and Bill: {bill['InvoiceNumber']}")
    invoiceResponse = xeroAPIUpdateBill(inv, accessToken, xeroTenantId)
    
    # only approve the bill if the invoice update was successful
    if invoiceResponse:
        print(f"Invoice {inv['InvoiceNumber']} updated successfully.")
        billResponse = xeroAPIUpdateBill(bill, accessToken, xeroTenantId)
        if billResponse:
            print(f"Invoice {bill['InvoiceNumber']} updated successfully.")
        else: print("Bill update failed.")
    else: print(f"Invoice: {inv.get("InvoiceNumber", "")} approval failed, bill not updated.")
    
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
    
    for invoice in draftInvoices:
        # if Costco Australia, skip the invoice
        if "Costco Wholesale Australia" in invoice.get("Contact", "")["Name"]:
            print(f"Skipping invoice for Costco Australia: {invoice.get('InvoiceNumber', 'No Invoice Number')}")
            continue
        
        # get the matching billID for each draft invoice
        invNumber = invoice.get("InvoiceNumber", "No Invoice Number")
        if not invNumber.startswith("SI-"):
            logging.warning(f"Skipping invoice with unexpected format: {invNumber}")
            continue
        soNumber = "SO-" + invNumber.split("-")[1]
        # print(f"Draft Invoice: {invNumber} - SO Number: {soNumber}")
        for bill in draftBills:
            if soNumber in bill.get("InvoiceNumber", ""):
                # Approve the draft invoice and draft bill, matching the bill date to the invoice date
                approveDraftInvoiceAndBill(invoice, bill, accessToken, xeroTenantId)
                

        
if __name__ == "__main__":
    main()