# CLAUDE.md — FlightRisk

## Business Description
<!-- TODO: What does FlightRisk do? Industry, size, key contacts, business stage, relationship with Trihalo -->

## Xero Setup
<!-- TODO: Which Xero organisation is connected, account codes, chart of accounts quirks, data model notes -->
<!-- e.g. How AR accounts are structured, prepayment account codes, customer naming conventions -->

## Scripts
| Script | Purpose |
|--------|---------|
| `ARPaymentAllocator.py` | Allocates AR payments to outstanding invoices |
| `CustomerPrepaymentARAllocator.py` | Allocates customer prepayments against AR invoices |
| `draftInvoiceApprover.py` | Approves draft invoices in bulk |
| `atbRequest.py` | Aged Trial Balance report request |
| `atbAnalysis.py` | ATB data analysis and processing |

## Automation Rules
<!-- TODO: Key business logic, edge cases, special conditions -->
<!-- e.g. Payment matching logic, prepayment allocation priority, draft invoice approval criteria -->

## Coding Style & Conventions
<!-- TODO: Output format preferences, naming conventions, logging style, report recipients -->
