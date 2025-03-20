import sys
import os
import json
import requests
import shutil
import datetime
from dotenv import load_dotenv

# Ensure the script can find modules in the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xeroAuthHelper import getXeroAccessToken
from xeroAuth import XeroTenants
from helpers.fetchXeroInvoices import fetchXeroInvoices
from helpers.fetchInvoiceAttachment import (
    fetchXeroInvoiceAttachmentsIds,
    fetchXeroInvoiceAttachmentsPDF,
)
from helpers.extractInvoiceNumberFromPDF import extractInvoiceNumberFromPDF
from helpers.extractInvoiceAmountFromPDF import extractInvoiceAmountAndGSTFromPDF
from helpers.emailAttachment import sendEmailWithAttachment

XERO_API_URL = "https://api.xero.com/api.xro/2.0/Invoices"
DOWNLOAD_FOLDER = "downloadedInvoices"
LOG_FOLDER = "logs"

load_dotenv()

# Generate a timestamp for log file
timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = os.path.join(LOG_FOLDER, f"log_{timestamp}.txt")

# Ensure log directory exists
os.makedirs(LOG_FOLDER, exist_ok=True)


def writeLog(message, isFirstEntry=False):
    """Write log messages to a file, adding date/time info on the first entry"""
    with open(LOG_FILE, "a") as logFile:
        if isFirstEntry:
            currentTime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logFile.write(
                f"==== LOG STARTED ====\nDate: {currentTime.split()[0]}\nTime: {currentTime.split()[1]}\n=====================\n\n"
            )
        logFile.write(message + "\n")


def getXeroTenant(client):
    """Authenticate and return Xero Tenant ID"""
    print(client)
    accessToken = getXeroAccessToken(client)
    xeroTenantId = XeroTenants(accessToken)

    if not xeroTenantId: raise Exception("Could not retrieve Xero tenant ID.")

    return accessToken, xeroTenantId


def fetchInvoices(accessToken, xeroTenantId, status="DRAFT"):
    """Fetch all invoices from Xero where Type is 'ACCPAY'"""
    try:
        invoices = fetchXeroInvoices(accessToken, xeroTenantId, status)
    except Exception as e:
        writeLog(f"Error fetching invoices: {e}")
        return []

    if "Invoices" not in invoices or not isinstance(invoices["Invoices"], list):
        writeLog("No invoices found.")
        return []

    # Filter invoices to only include those with Type = "ACCPAY"
    accPayInvoices = [invoice for invoice in invoices["Invoices"] if invoice.get("Type") == "ACCPAY"]

    if not accPayInvoices:
        writeLog("No ACCPAY invoices found.")
        return []

    return accPayInvoices


def downloadInvoiceAttachments(accessToken, xeroTenantId, invoiceIds):
    """Download invoice attachments from Xero and save locally"""
    attachmentIds = fetchXeroInvoiceAttachmentsIds(accessToken, xeroTenantId, invoiceIds)
    if not attachmentIds:
        writeLog("No attachments found.")
        return {}

    extractedFiles = {}

    for invoiceId, attachments in attachmentIds.items():
        for attachmentId in attachments:
            filePath = os.path.join(DOWNLOAD_FOLDER, f"{invoiceId}_{attachmentId}.pdf")
            attachmentData = fetchXeroInvoiceAttachmentsPDF(accessToken, xeroTenantId, invoiceId, attachmentId)

            if not attachmentData:
                writeLog(f"⚠️ Failed to fetch attachment {attachmentId} for Invoice ID {invoiceId}")
                continue

            # Save the file locally
            os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
            with open(filePath, "wb") as file:
                file.write(attachmentData)

            extractedFiles[invoiceId] = filePath

    return extractedFiles


def updateInvoiceNumberOnly(accessToken, xeroTenantId, invoiceId, newInvoiceNumber, oldInvoiceNumber, contactName):
    """Update only the invoice number in Xero (without approving)"""
    url = f"{XERO_API_URL}/{invoiceId}"
    headers = {
        "Authorization": f"Bearer {accessToken}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Xero-Tenant-Id": xeroTenantId,
    }
    payload = {
        "Invoices": [
            {
                "InvoiceID": invoiceId,
                "InvoiceNumber": newInvoiceNumber if newInvoiceNumber else oldInvoiceNumber,
            }
        ]
    }
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code in [200, 201]:
        writeLog(f"✅ Updated invoice number from {oldInvoiceNumber} to {newInvoiceNumber} for {contactName}.")
    else:
        writeLog(f"❌ Failed to update invoice number for {oldInvoiceNumber} (Contact: {contactName}): {response.text}")
    writeLog("---------------------------\n")


def updateInvoiceApproval(accessToken, xeroTenantId, invoiceId, invoiceNumber, contactName):
    """Update invoice status to 'AUTHORISED' in Xero (using the current invoice number)"""
    url = f"{XERO_API_URL}/{invoiceId}"
    headers = {
        "Authorization": f"Bearer {accessToken}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Xero-Tenant-Id": xeroTenantId,
    }
    payload = {
        "Invoices": [
            {
                "InvoiceID": invoiceId,
                "InvoiceNumber": invoiceNumber,
                "Status": "AUTHORISED",
            }
        ]
    }
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code in [200, 201]:
        writeLog(f"✅ Approved Invoice {invoiceNumber} (Contact: {contactName}).")
    else:
        writeLog(f"❌ Failed to approve Invoice {invoiceNumber} (Contact: {contactName}): {response.text}")
    writeLog("---------------------------\n")


def processHDInvoices(accessToken, xeroTenantId, invoices, extractedFiles):
    """
    For invoices with an invoice number that starts with 'HD',
    extract the proper invoice number from the PDF and update Xero.
    """
    for invoice in invoices:
        invoiceId = invoice["InvoiceID"]
        invoiceNumber = invoice["InvoiceNumber"]
        contactName = invoice.get("Contact", {}).get("Name", "Unknown Contact")
        if invoiceId not in extractedFiles:
            writeLog(f"⚠️ No attachment found for Invoice {invoiceNumber} (Contact: {contactName}, ID: {invoiceId}) for HD update")
            writeLog("---------------------------\n")
            continue

        if invoiceNumber.startswith("HD"):
            pdfFile = extractedFiles[invoiceId]
            newInvoiceNumber = extractInvoiceNumberFromPDF(pdfFile)
            # Update invoice number regardless of totals/GST validation outcome.
            updateInvoiceNumberOnly(accessToken, xeroTenantId, invoiceId, newInvoiceNumber, invoiceNumber, contactName)


def validateAndApproveInvoices(accessToken, xeroTenantId, invoices, extractedFiles):
    """
    For every invoice, compare the extracted total and GST from the PDF to the Xero values.
    If they match, update the invoice status to 'AUTHORISED'.
    If they do not match, log the discrepancy.
    Note: For HD invoices the invoice number has already been updated.
    """
    for invoice in invoices:
        invoiceId = invoice["InvoiceID"]
        invoiceNumber = invoice["InvoiceNumber"]
        contactName = invoice.get("Contact", {}).get("Name", "Unknown Contact")
        expectedAmount = float(invoice["Total"])
        expectedGST = float(invoice.get("TotalTax", 0))

        if invoiceId not in extractedFiles:
            writeLog(f"⚠️ No attachment found for Invoice {invoiceNumber} (Contact: {contactName}, ID: {invoiceId})")
            writeLog("---------------------------\n")
            continue

        pdfFile = extractedFiles[invoiceId]

        # If the invoice was an HD invoice, assume its new number has been updated.
        # Still extract for logging purposes.
        if invoiceNumber.startswith("HD"): extractedNumber = extractInvoiceNumberFromPDF(pdfFile)
        else: extractedNumber = invoiceNumber

        extractedAmount, extractedGST = extractInvoiceAmountAndGSTFromPDF(pdfFile)
        if extractedAmount is not None and extractedGST is not None:
            extractedAmountFloat = float(extractedAmount)
            extractedGSTFloat = float(extractedGST)

            amountMatches = (extractedAmountFloat == expectedAmount)
            gstMatches = abs(extractedGSTFloat - expectedGST) <= 0.025

            if amountMatches and gstMatches:
                writeLog(f"✅ Invoice {invoiceNumber} (Contact: {contactName}) approved: Amount & GST match!")
                updateInvoiceApproval(accessToken, xeroTenantId, invoiceId, extractedNumber, contactName)
            else:
                mismatchReasons = []
                if not amountMatches:
                    mismatchReasons.append(f"Expected Amount: {expectedAmount}, Found: {extractedAmountFloat}")
                if not gstMatches:
                    mismatchReasons.append(f"Expected GST: {expectedGST}, Found: {extractedGSTFloat}")
                writeLog(f"⚠️ Invoice {invoiceNumber} (Contact: {contactName}) validation failed: {', '.join(mismatchReasons)}.\n"
                         f"Invoice number has been updated but NOT approved.")
        else:
            writeLog(f"⚠️ Could not extract amounts for Invoice {invoiceNumber} (Contact: {contactName}).")
        writeLog("---------------------------\n")


def clearDownloadedInvoices():
    """Remove all files in the 'downloadedInvoices' folder"""
    if os.path.exists(DOWNLOAD_FOLDER):
        shutil.rmtree(DOWNLOAD_FOLDER)
        writeLog(f"🗑️ Cleared {DOWNLOAD_FOLDER} folder.")


def main():
    """Main function to fetch, validate, update invoice numbers, and then update status in Xero"""
    client = "COSMOPOLITAN_CORPORATION"

    # First log entry with date/time
    writeLog("", isFirstEntry=True)

    accessToken, xeroTenantId = getXeroTenant(client)
    invoices = fetchInvoices(accessToken, xeroTenantId)
    invoiceIds = [invoice["InvoiceID"] for invoice in invoices]

    extractedFiles = downloadInvoiceAttachments(accessToken, xeroTenantId, invoiceIds)

    # Step 1: For invoices with invoice numbers starting with 'HD', update the invoice number
    processHDInvoices(accessToken, xeroTenantId, invoices, extractedFiles)

    # Step 2: Validate ALL invoices for total amount and GST; if matching, approve them.
    validateAndApproveInvoices(accessToken, xeroTenantId, invoices, extractedFiles)

    clearDownloadedInvoices()
    
    recipients = ["leo@trihalo.com.au"]
    subject = f"ATB Report"
    body = f"Hi Leo,\nYou're weird.\n\nThanks"

    sendEmailWithAttachment(recipients, subject, body, file_path=None, provider="GMAIL")


if __name__ == "__main__":
    main()
