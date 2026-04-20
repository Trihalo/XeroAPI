"""
sunRoadInvoicing.py — Sun Road invoice processing for H2coco

Usage:
  python sunRoadInvoicing.py                        # process all Sun Road drafts
  python sunRoadInvoicing.py --test-cds SI-00021927 # test CDS logic on one invoice

Finds all DRAFT Sun Road invoices in Xero, matches each against SR.xlsx by
H2coco PO number, then for each match:
  1. Clean reference (strip "Sunroad"), set date=today, due=today+7, approve
  2. Allocate 50% deposit (account 1400, USD, exchange rate from file)
  3. Query Unleashed for SO delivery address — skip CDS if NZL
  4. Create CDS invoice if 500ml/200ml line items exist
"""

import sys
import os
import re
import hmac
import hashlib
import base64
import requests
import pandas as pd
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from helpers.fetchInvoicesForClient import fetchInvoicesForClient

# ── Constants ────────────────────────────────────────────────────────────────
SUNROAD_CONTACT         = "Sun Road Food & Beverage - CDS"
SUNROAD_CONTACT_ID      = "4e2bbc25-e13b-4638-842d-2c47fd892a09"
SUNROAD_CDS_CONTACT     = "Sun Road Food and Beverage Australia - CDS"
SUNROAD_CDS_CONTACT_ID  = "edb8e6c4-b04d-440d-97bc-eb8ebaa29099"
SR_XLSX_PATH      = os.path.join(os.path.dirname(__file__), "SR.xlsx")
PAYMENT_ACCOUNT   = "1400"
CDS_ACCOUNT       = "4000"   # Sales
CDS_UNIT_COST     = 0.143
CDS_MULTIPLIER    = 12
UNLEASHED_BASE    = "https://api.unleashedsoftware.com"

NZL_COUNTRY_CODES = {"NZL", "NZ", "NEW ZEALAND"}


# ── Xero helpers ─────────────────────────────────────────────────────────────



def _xero_headers(access_token, tenant_id):
    return {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def xero_update_invoice(invoice_id, payload, access_token, tenant_id):
    url = f"https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}"
    resp = requests.post(url, headers=_xero_headers(access_token, tenant_id), json=payload)
    if resp.status_code in (200, 201):
        return resp.json().get("Invoices", [{}])[0]
    raise RuntimeError(f"Update invoice failed {resp.status_code}: {resp.text}")


def xero_create_invoice(payload, access_token, tenant_id):
    url = "https://api.xero.com/api.xro/2.0/Invoices"
    resp = requests.post(url, headers=_xero_headers(access_token, tenant_id), json=payload)
    if resp.status_code in (200, 201):
        return resp.json().get("Invoices", [{}])[0]
    raise RuntimeError(f"Create invoice failed {resp.status_code}: {resp.text}")


def xero_create_payment(invoice_id, account_code, date_str, currency_rate, amount,
                         reference, access_token, tenant_id):
    payload = {
        "Payments": [{
            "Invoice":      {"InvoiceID": invoice_id},
            "Account":      {"Code": account_code},
            "Date":         date_str,
            "CurrencyRate": currency_rate,
            "Amount":       amount,
            "Reference":    reference,
        }]
    }
    url = "https://api.xero.com/api.xro/2.0/Payments"
    resp = requests.post(url, headers=_xero_headers(access_token, tenant_id), json=payload)
    if resp.status_code in (200, 201):
        return resp.json()
    raise RuntimeError(f"Create payment failed {resp.status_code}: {resp.text}")


# ── Unleashed helpers ────────────────────────────────────────────────────────

def _unleashed_headers(query_string, api_id, api_key):
    sig = base64.b64encode(
        hmac.new(api_key.encode(), query_string.encode(), hashlib.sha256).digest()
    ).decode()
    return {
        "api-auth-id":        api_id,
        "api-auth-signature": sig,
        "Accept":             "application/json",
        "Content-Type":       "application/json",
    }


def unleashed_get(path, params, api_id, api_key):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{UNLEASHED_BASE}/{path}?{qs}" if qs else f"{UNLEASHED_BASE}/{path}"
    resp = requests.get(url, headers=_unleashed_headers(qs, api_id, api_key))
    if resp.status_code == 200:
        return resp.json()
    print(f"Unleashed GET /{path} failed {resp.status_code}: {resp.text}")
    return None


def get_so_delivery_country(si_number, api_id, api_key):
    """
    Converts SI-XXXXX → SO-XXXXX and fetches the SO from Unleashed by orderNumber.
    Returns the delivery country (upper-cased) or None if not found.
    """
    so_number = si_number.replace("SI-", "SO-", 1)
    result    = unleashed_get("SalesOrders", {"orderNumber": so_number}, api_id, api_key)
    items     = (result or {}).get("Items", [])
    if not items:
        print(f"SO {so_number} not found in Unleashed.")
        return None
    so      = items[0]
    addr    = so.get("DeliveryAddress") or {}
    country = (addr.get("Country") or so.get("DeliveryCountry") or "").strip().upper()
    print(f"Found SO: {so.get('OrderNumber', '?')}  |  Delivery country: '{country}'")
    return country


# ── Invoice helpers ───────────────────────────────────────────────────────────

def find_sunroad_drafts(invoices):
    """Return all DRAFT ACCREC invoices for the Sun Road contact."""
    return [
        inv for inv in invoices
        if inv.get("Contact", {}).get("Name", "") == SUNROAD_CONTACT
    ]


def match_po_from_invoice(inv, sr_h2coco_map, sr_sunroad_map):
    """
    Return the SR.xlsx row whose H2coco PO or Sun Road PO appears in the invoice
    reference/number, or None if no match.
    The reference typically contains the Sun Road PO (e.g. 'Sunroad PO37815').
    """
    haystack = (inv.get("Reference", "") or "") + " " + (inv.get("InvoiceNumber", "") or "")
    for po, row in sr_sunroad_map.items():
        if str(po) in haystack:
            return row
    for po, row in sr_h2coco_map.items():
        if str(po) in haystack:
            return row
    return None


def clean_reference(reference):
    """Strip 'Sunroad' / 'Sun Road' from the reference field."""
    return re.sub(r"(?i)sun\s*road\s*[-–]?\s*", "", reference).strip()


def is_cds_product(description):
    return bool(re.search(r"\b(500\s*ml|200\s*ml)\b", description, re.IGNORECASE))


def build_cds_line_items(original_lines):
    cds_lines = []
    for line in original_lines:
        desc = line.get("Description", "")
        if is_cds_product(desc):
            qty         = float(line.get("Quantity", 1)) * CDS_MULTIPLIER
            line_amount = round(qty * CDS_UNIT_COST, 2)
            cds_lines.append({
                "Description": desc,
                "Quantity":    qty,
                "UnitAmount":  CDS_UNIT_COST,
                "LineAmount":  line_amount,
                "AccountCode": CDS_ACCOUNT,
                "TaxType":     "BASEXCLUDED",
            })
    return cds_lines


# ── Per-invoice processing ────────────────────────────────────────────────────

def process_invoice(inv, sr_row, access_token, tenant_id, api_id, api_key, cds_contact_id):
    today    = datetime.now().strftime("%Y-%m-%d")
    due_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    inv_id     = inv["InvoiceID"]
    inv_number = inv.get("InvoiceNumber", "")
    orig_ref   = inv.get("Reference", "") or ""

    # Derive a clean reference from whatever is in the invoice
    new_ref = clean_reference(orig_ref) or orig_ref

    print(f"\n{'='*60}")
    print(f"Invoice : {inv_number}  |  Ref: '{orig_ref}' → '{new_ref}'")

    # Step 1: Update reference/dates and approve
    clean_lines = [
        {k: v for k, v in li.items() if k != "TaxAmount"}
        for li in inv.get("LineItems", [])
    ]
    updated = xero_update_invoice(inv_id, {
        "Type":          inv["Type"],
        "InvoiceNumber": inv_number,
        "Reference":     new_ref,
        "Date":          today,
        "DueDate":       due_date,
        "Status":        "AUTHORISED",
        "LineItems":     clean_lines,
    }, access_token, tenant_id)
    print(f"Approved. Total: {updated.get('Total')} {updated.get('CurrencyCode', '')}")

    # Step 2: Allocate deposit payment (only if a deposit row was found in SR.xlsx)
    if sr_row is None:
        print("No deposit found in SR.xlsx — skipping payment allocation.")
        po_number  = None
        sunroad_po = None
    else:
        po_number     = int(sr_row["H2coco PO"])
        usd_amount    = float(sr_row["DP Amount (USD)"])
        aud_amount    = float(sr_row["DP Amount (AUD)"])
        sunroad_po    = int(sr_row["Sun Road PO"])
        currency_rate = round(aud_amount / usd_amount, 6)
        print(f"Deposit : PO{po_number} / PO{sunroad_po}  USD {usd_amount}  AUD {aud_amount}  rate {currency_rate}")
        payment_ref = f"{inv_number} PO{po_number} PO{sunroad_po} USD {usd_amount}"
        xero_create_payment(
            inv_id, PAYMENT_ACCOUNT, today,
            currency_rate, usd_amount,
            payment_ref, access_token, tenant_id,
        )
        print(f"Payment allocated: {payment_ref}")

    # Step 3: Check delivery address via Unleashed using the original invoice reference
    create_cds = False
    if not api_id or not api_key:
        print("Unleashed credentials not set — skipping CDS check.")
    else:
        delivery_country = get_so_delivery_country(inv_number, api_id, api_key)
        if delivery_country is None:
            print("Could not determine delivery country — skipping CDS invoice.")
        elif delivery_country in NZL_COUNTRY_CODES:
            print(f"NZ delivery ({delivery_country}) — CDS invoice will NOT be created.")
        else:
            create_cds = True

    # Step 4: Create CDS invoice if applicable
    if create_cds:
        cds_lines = build_cds_line_items(inv.get("LineItems", []))
        if not cds_lines:
            print("No 500ml/200ml line items found — CDS invoice skipped.")
        else:
            cds_inv = xero_create_invoice({
                "Type":            "ACCREC",
                "InvoiceNumber":   f"{inv_number} CDS",
                "Contact":         {"ContactID": cds_contact_id},
                "Date":            today,
                "DueDate":         due_date,
                "Reference":       new_ref,
                "Status":          "AUTHORISED",
                "CurrencyCode":    "AUD",
                "LineItems":       cds_lines,
            }, access_token, tenant_id)
            print(f"CDS invoice created: {cds_inv.get('InvoiceNumber')}  Total AUD {cds_inv.get('Total')}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Load SR.xlsx — build lookup dicts by both H2coco PO and Sun Road PO
    sr_df          = pd.read_excel(SR_XLSX_PATH)
    sr_h2coco_map  = {int(row["H2coco PO"]):  row for _, row in sr_df.iterrows()}
    sr_sunroad_map = {int(row["Sun Road PO"]): row for _, row in sr_df.iterrows()}
    print(f"SR.xlsx: {len(sr_df)} deposit rows loaded.")

    # Fetch all draft ACCREC invoices from Xero
    print("Fetching draft invoices from Xero...")
    invoices, access_token, tenant_id = fetchInvoicesForClient("H2COCO", "DRAFT")
    draft_accrec = [inv for inv in invoices if inv.get("Type") == "ACCREC"]
    print(f"{len(draft_accrec)} draft ACCREC invoices retrieved.")

    # Filter to Sun Road drafts and match each against SR.xlsx
    sunroad_drafts = find_sunroad_drafts(draft_accrec)
    print(f"{len(sunroad_drafts)} Sun Road draft invoice(s) found.")

    if not sunroad_drafts:
        print("Nothing to process.")
        return

    api_id  = os.environ.get("H2COCO_UNLEASHED_API_ID", "")
    api_key = os.environ.get("H2COCO_UNLEASHED_API_KEY", "")

    cds_contact_id = SUNROAD_CDS_CONTACT_ID

    processed = 0
    for inv in sunroad_drafts:
        sr_row = match_po_from_invoice(inv, sr_h2coco_map, sr_sunroad_map)
        if sr_row is None:
            ref = inv.get("Reference", "")
            print(f"\n{inv.get('InvoiceNumber', '?')} (ref: '{ref}') — no deposit in SR.xlsx, processing without payment.")

        process_invoice(inv, sr_row, access_token, tenant_id, api_id, api_key, cds_contact_id)
        processed += 1

    print(f"\n{'='*60}")
    print(f"Done. {processed}/{len(sunroad_drafts)} invoice(s) processed.")


def test_cds(si_number):
    """
    Convert SI-XXXXX → SO-XXXXX, fetch the SO from Unleashed, check delivery
    country and line items, then create the CDS invoice in Xero if applicable.

    Usage: python sunRoadInvoicing.py --test-cds SI-00021927
    """
    from xeroAuthHelper import getXeroAccessToken
    from xeroAuth import XeroTenants

    api_id  = os.environ.get("H2COCO_UNLEASHED_API_ID", "")
    api_key = os.environ.get("H2COCO_UNLEASHED_API_KEY", "")
    if not api_id or not api_key:
        print("Unleashed credentials not set.")
        return

    # SI-00021927 → SO-00021927
    so_number = si_number.replace("SI-", "SO-", 1)
    print(f"Looking up Unleashed SO: {so_number}")

    result = unleashed_get("SalesOrders", {"orderNumber": so_number}, api_id, api_key)
    items  = (result or {}).get("Items", [])
    if not items:
        print(f"SO {so_number} not found in Unleashed.")
        return

    so           = items[0]
    customer_ref = so.get("CustomerRef", "").strip()
    addr         = so.get("DeliveryAddress") or {}
    country      = (addr.get("Country") or so.get("DeliveryCountry") or "").strip().upper()
    so_lines     = so.get("SalesOrderLines", [])

    print(f"SO       : {so.get('OrderNumber')}  |  CustomerRef: '{customer_ref}'")
    print(f"Delivery : {country or '(unknown)'}")
    print(f"Lines    : {len(so_lines)}")
    for line in so_lines:
        desc = line.get("Product", {}).get("ProductDescription", "") or line.get("LineNumber", "")
        qty  = line.get("OrderQuantity", 0)
        print(f"  {'[CDS]' if is_cds_product(desc) else '     '} qty={qty}  {desc}")

    if country in NZL_COUNTRY_CODES:
        print(f"\nNZ delivery — CDS invoice will NOT be created.")
        return

    # Build CDS lines from Unleashed SO lines
    cds_lines = []
    for line in so_lines:
        desc = line.get("Product", {}).get("ProductDescription", "")
        if is_cds_product(desc):
            qty         = float(line.get("OrderQuantity", 1)) * CDS_MULTIPLIER
            line_amount = round(qty * CDS_UNIT_COST, 2)
            cds_lines.append({
                "Description": desc,
                "Quantity":    qty,
                "UnitAmount":  CDS_UNIT_COST,
                "LineAmount":  line_amount,
                "AccountCode": CDS_ACCOUNT,
                "TaxType":     "BASEXCLUDED",
            })

    if not cds_lines:
        print("No 500ml/200ml line items found — no CDS invoice.")
        return

    print(f"\nCDS line items to be created ({len(cds_lines)}):")
    for li in cds_lines:
        print(f"  qty={li['Quantity']}  unit={li['UnitAmount']}  {li['Description']}")

    access_token   = getXeroAccessToken("H2COCO")
    tenant_id      = XeroTenants(access_token)
    contact_id     = SUNROAD_CDS_CONTACT_ID

    today    = datetime.now().strftime("%Y-%m-%d")
    due_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    new_ref  = clean_reference(customer_ref) or customer_ref

    cds_inv = xero_create_invoice({
        "Type":          "ACCREC",
        "InvoiceNumber": f"{si_number} CDS",
        "Contact":       {"ContactID": contact_id},
        "Date":          today,
        "DueDate":       due_date,
        "Reference":     new_ref,
        "Status":        "AUTHORISED",
        "CurrencyCode":  "AUD",
        "LineItems":     cds_lines,
    }, access_token, tenant_id)
    print(f"CDS invoice created: {cds_inv.get('InvoiceNumber')}  Total AUD {cds_inv.get('Total')}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--test-cds":
        test_cds(sys.argv[2])  # e.g. --test-cds SI-00021927
    else:
        main()
