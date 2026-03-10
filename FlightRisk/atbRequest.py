import sys
import os
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load .env when running locally (no-op in GitHub Actions where no .env exists)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except ImportError:
    pass

from atbAnalysis import processAtbData, exportAtbData
from helpers.fetchInvoicesForClient import fetchInvoicesForClient


def main():
    parser = argparse.ArgumentParser(description="FlightRisk ATB Report")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Export to Excel instead of uploading to BigQuery (for local testing)"
    )
    args = parser.parse_args()

    invoices, _, _ = fetchInvoicesForClient("FLIGHT_RISK", "AUTHORISED")
    if not isinstance(invoices, list):
        raise Exception(f"Expected a list of invoices but got {type(invoices)}")

    if args.local:
        exportAtbData(invoices)
    else:
        processAtbData(invoices)


if __name__ == "__main__":
    main()
