# CLAUDE.md — Cosmo (Cosmopolitan Corp)

## Business Description
<!-- TODO: What does Cosmopolitan Corp do? Industry, size, key contacts, business stage, relationship with Trihalo -->

## Xero Setup
<!-- TODO: Which Xero organisation is connected, account codes, chart of accounts quirks, data model notes -->
- Config file: `clientDetails/Cosmopolitan_Corporation.json`
- Sample invoices available in `helpers/sampleCosmoInvoices/` (PDF format, used for extraction testing)

## Scripts
| Script | Purpose |
|--------|---------|
| `invoiceApprovalRequest.py` | Approves invoices — fetches PDF attachments, extracts amounts/numbers, sends approval requests |

## Automation Rules
<!-- TODO: Key business logic, edge cases, special conditions -->
<!-- e.g. Invoice approval thresholds, which suppliers need manual approval, PDF extraction logic -->

## Coding Style & Conventions
<!-- TODO: Output format preferences, naming conventions, email format for approval requests, recipient lists -->
