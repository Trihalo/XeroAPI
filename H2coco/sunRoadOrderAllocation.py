import sys
import os
import hmac
import hashlib
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

UNLEASHED_BASE = "https://api.unleashedsoftware.com"
FOB_WAREHOUSE = "FOB"
SUNROAD_CUSTOMER_NAME = "Sun Road Food & Beverage"

# ---------------------------------------------------------------------------
# Unleashed API helpers
# ---------------------------------------------------------------------------

def build_unleashed_headers(query_string: str, api_id: str, api_key: str) -> dict:
    """HMAC-SHA256 auth headers required by the Unleashed API."""
    signature = base64.b64encode(
        hmac.new(api_key.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")
    return {
        "api-auth-id": api_id,
        "api-auth-signature": signature,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def unleashed_get(path: str, params: dict, api_id: str, api_key: str) -> dict | None:
    """Generic Unleashed GET. Returns parsed JSON or None on failure."""
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    headers = build_unleashed_headers(query_string, api_id, api_key)
    url = f"{UNLEASHED_BASE}/{path}?{query_string}" if query_string else f"{UNLEASHED_BASE}/{path}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    print(f"Unleashed GET /{path} failed: {response.status_code} — {response.text}")
    return None


# ---------------------------------------------------------------------------
# Step 1: Fetch Purchase Order
# ---------------------------------------------------------------------------

def get_purchase_order(po_number: str, api_id: str, api_key: str) -> dict | None:
    """GET /PurchaseOrders?orderNumber={po_number}. Returns PO dict or None."""
    result = unleashed_get("PurchaseOrders", {"orderNumber": po_number}, api_id, api_key)
    if not result:
        return None
    items = result.get("Items", [])
    if not items:
        print(f"PO not found in Unleashed: {po_number}")
        return None
    return items[0]


# ---------------------------------------------------------------------------
# Step 2: Find linked Sales Order via CustomerRef
# ---------------------------------------------------------------------------

def get_sunroad_customer_guid(api_id: str, api_key: str) -> str | None:
    """GET /Customers?customerName={name} to resolve Sun Road's API GUID."""
    result = unleashed_get("Customers", {"customerName": SUNROAD_CUSTOMER_NAME}, api_id, api_key)
    if not result:
        return None
    items = result.get("Items", [])
    if not items:
        print(f"Customer not found in Unleashed: '{SUNROAD_CUSTOMER_NAME}'")
        return None
    guid = items[0].get("Guid", "")
    print(f"Sun Road GUID: {guid}")
    return guid


def get_sales_order_by_customer_ref(customer_ref: str, sunroad_guid: str, api_id: str, api_key: str) -> dict | None:
    """
    Fetches Parked SalesOrders for the Sun Road customer and returns the one
    whose CustomerRef exactly matches customer_ref. Filtering by customerId and
    orderStatus=Parked server-side keeps the result set small; we then exact-match
    client-side since CustomerRef is not a supported API filter.
    Returns the matching SO dict, or None if not found / ambiguous.
    """
    page = 1
    page_size = 200
    matches = []

    while True:
        result = unleashed_get(
            "SalesOrders",
            {"customerId": sunroad_guid, "orderStatus": "Parked", "pageSize": page_size, "pageNumber": page},
            api_id,
            api_key,
        )
        if not result:
            break
        items = result.get("Items", [])
        for so in items:
            if so.get("CustomerRef", "").strip() == customer_ref:
                matches.append(so)
        if len(items) < page_size:
            break
        page += 1

    if not matches:
        print(f"No Parked SO found for Sun Road with CustomerRef exactly matching: '{customer_ref}'")
        return None
    if len(matches) > 1:
        numbers = [so.get("OrderNumber") for so in matches]
        print(f"ERROR: Multiple SOs have CustomerRef '{customer_ref}': {numbers}. Expected exactly one — resolve manually.")
        return None
    return matches[0]


# ---------------------------------------------------------------------------
# Step 3: Fetch FOB warehouse batches for a product
# ---------------------------------------------------------------------------

def get_fob_batches_for_product(product_code: str, api_id: str, api_key: str) -> list:
    """
    GET /BatchNumbers?productCode={code}&warehouseCode=FOB.
    NOTE: Verify exact param names against Unleashed API docs.
    Returns list of batch dicts (BatchNumber, Quantity, etc.).
    """
    result = unleashed_get(
        "BatchNumbers",
        {"productCode": product_code, "warehouseCode": FOB_WAREHOUSE},
        api_id,
        api_key,
    )
    if not result:
        return []
    return result.get("Items", [])


# ---------------------------------------------------------------------------
# Step 4: Quantity check (hard stop)
# ---------------------------------------------------------------------------

def check_quantities(so_lines: list, api_id: str, api_key: str) -> tuple[bool, dict]:
    """
    For each SO line, sums FOB batch quantities and compares to the ordered quantity.
    Returns (all_match, fob_batches_by_product_code).
    Prints a formatted table so mismatches are immediately visible.
    """
    all_match = True
    fob_batches_by_product = {}

    print(f"\n{'Product Code':<25} {'SO Qty':>10} {'FOB Qty':>10} {'Status':>10}")
    print("-" * 58)

    for line in so_lines:
        product_code = line.get("Product", {}).get("ProductCode", "")
        so_qty = float(line.get("OrderQuantity", 0))

        batches = get_fob_batches_for_product(product_code, api_id, api_key)
        fob_batches_by_product[product_code] = batches
        fob_qty = sum(float(b.get("Quantity", 0)) for b in batches)

        match = fob_qty == so_qty
        if not match:
            all_match = False

        status = "OK" if match else "MISMATCH"
        print(f"{product_code:<25} {so_qty:>10.2f} {fob_qty:>10.2f} {status:>10}")

    return all_match, fob_batches_by_product


# ---------------------------------------------------------------------------
# Step 5: Assign batches to SO (stub — confirm endpoint via sandbox)
# ---------------------------------------------------------------------------

def assign_batches_to_so(so_guid: str, fob_batches_by_product: dict, so_lines: list, api_id: str, api_key: str):
    """
    TODO: POST batch assignments to the SO.

    Two candidate approaches to verify in the Unleashed sandbox:
      A) POST /SalesOrders/{so_guid}/BatchNumbers
         with a payload mapping each batch to its SO line
      B) Set serialBatch=true when completing the SO, letting Unleashed
         auto-assign available FOB batches

    Print the intended assignments so they can be manually verified first.
    """
    print("\n[STUB] Batch assignment — verify approach in sandbox before enabling.")
    print(f"SO Guid: {so_guid}")
    print("\nIntended batch assignments:")
    print(f"  {'Product Code':<25} {'Batch Number':<20} {'Quantity':>10}")
    print("  " + "-" * 58)
    for product_code, batches in fob_batches_by_product.items():
        for b in batches:
            batch_num = b.get("BatchNumber", "N/A")
            qty = b.get("Quantity", 0)
            print(f"  {product_code:<25} {batch_num:<20} {float(qty):>10.2f}")

    # Uncomment once endpoint is confirmed:
    # url = f"{UNLEASHED_BASE}/SalesOrders/{so_guid}/BatchNumbers"
    # query_string = ""
    # headers = build_unleashed_headers(query_string, api_id, api_key)
    # payload = { ... }
    # response = requests.post(url, headers=headers, json=payload)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python sunRoadOrderAllocation.py <PO-number> [--sandbox]")
        print("Example: python sunRoadOrderAllocation.py PO-00005596")
        print("         python sunRoadOrderAllocation.py PO-00005596 --sandbox")
        sys.exit(1)

    po_number = sys.argv[1]
    sandbox = "--sandbox" in sys.argv

    if sandbox:
        print("*** SANDBOX MODE ***")
        api_id = os.environ["H2COCO_UNLEASHED_SANDBOX_API_ID"]
        api_key = os.environ["H2COCO_UNLEASHED_SANDBOX_API_KEY"]
    else:
        api_id = os.environ["H2COCO_UNLEASHED_API_ID"]
        api_key = os.environ["H2COCO_UNLEASHED_API_KEY"]

    # Step 1: Fetch PO and extract SupplierRef
    print(f"\n{'='*60}")
    print(f"Step 1: Fetching PO {po_number}")
    print("=" * 60)
    po = get_purchase_order(po_number, api_id, api_key)
    if not po:
        sys.exit(1)

    customer_ref = po.get("SupplierRef", "").strip()
    print(f"SupplierRef: {customer_ref}")
    if not customer_ref:
        print("ERROR: PO has no SupplierRef set. Cannot find linked SO.")
        sys.exit(1)

    # Step 2: Find linked SO
    print(f"\n{'='*60}")
    print(f"Step 2: Finding Sun Road GUID and scanning Parked SOs for CustomerRef '{customer_ref}'")
    print("=" * 60)
    sunroad_guid = get_sunroad_customer_guid(api_id, api_key)
    if not sunroad_guid:
        sys.exit(1)
    so = get_sales_order_by_customer_ref(customer_ref, sunroad_guid, api_id, api_key)
    if not so:
        sys.exit(1)

    so_number = so.get("OrderNumber", "Unknown")
    so_guid = so.get("Guid", "")
    so_lines = so.get("SalesOrderLines", [])
    print(f"Found SO: {so_number} | Guid: {so_guid} | Lines: {len(so_lines)}")

    # Step 3 + 4: Fetch FOB batches and check quantities
    print(f"\n{'='*60}")
    print("Step 3+4: Checking FOB batch quantities vs SO quantities")
    print("=" * 60)
    all_match, fob_batches_by_product = check_quantities(so_lines, api_id, api_key)

    if not all_match:
        print("\nERROR: Quantity mismatch — cannot proceed.")
        print("Resolve the stock discrepancy in the FOB warehouse before running again.")
        sys.exit(1)

    print("\nAll quantities match.")

    # Step 5: Assign batches to SO
    print(f"\n{'='*60}")
    print("Step 5: Batch assignment")
    print("=" * 60)
    assign_batches_to_so(so_guid, fob_batches_by_product, so_lines, api_id, api_key)


if __name__ == "__main__":
    main()
