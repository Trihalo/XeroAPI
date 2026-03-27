# CLAUDE.md — helpers/

Shared utilities used across all client scripts. Always check here before writing new functionality — these helpers should be reused rather than duplicated per client.

## Utilities

| File | Purpose | Key Function(s) |
|------|---------|-----------------|
| `dateStringsHelper.py` | Date formatting and string utilities | Date range helpers for Xero API queries |
| `emailAttachment.py` | Send emails with file attachments via Gmail | `sendEmailWithAttachment()` |
| `fetchInvoicesForClient.py` | Fetch invoices from Xero for a given client/tenant | High-level invoice fetch wrapper |
| `fetchXeroInvoices.py` | Low-level Xero invoice API calls | Raw Xero invoice list fetching |
| `fetchInvoiceAttachment.py` | Download attachment files from a Xero invoice | `fetchInvoiceAttachment()` |
| `extractInvoiceAmountFromPDF.py` | Parse the invoice amount from a PDF attachment | `extractAmount()` |
| `extractInvoiceNumberFromPDF.py` | Parse the invoice number from a PDF attachment | `extractInvoiceNumber()` |
| `databaseHelpers.py` | Read/write to the database (Firestore or similar) | Database CRUD utilities |

## When to Add a New Helper

Add to `helpers/` when:
- The utility is used (or likely to be used) by more than one client script
- It abstracts a Xero API interaction, file I/O, email, or database operation

Keep it in the client folder when:
- The logic is specific to one client's business rules
- It references client-specific account codes, mappings, or data structures
