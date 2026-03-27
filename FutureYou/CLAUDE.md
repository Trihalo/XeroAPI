# CLAUDE.md — FutureYou

## Business Description
<!-- TODO: What does FutureYou do? Industry, size, key contacts, business stage, relationship with Trihalo -->

## Xero Setup
<!-- TODO: Which Xero organisations are connected, account codes, chart of accounts quirks, data model notes -->
- Entities: FutureYou Contracting, FutureYou Recruitment, FutureYou Recruitment Perth (three separate Xero orgs)
- Config files: `clientDetails/Futureyou_Contracting.json`, `clientDetails/Futureyou_Recruitment.json`, `clientDetails/Futureyou_Recruitment_Perth.json`

## External Integrations
<!-- TODO: Bullhorn CRM — how it's used, what data flows between Bullhorn and Xero -->
- Bullhorn CRM integration present (see `databaseMappings.py`, `databaseInvoiceRequestv2.py`)

## Scripts
| Script | Purpose |
|--------|---------|
| `atbRequest.py` | Aged Trial Balance report request |
| `atbRequestv2.py` | Updated ATB report request |
| `atbAnalysis.py` | ATB data analysis and processing |
| `atbAnalysisv2.py` | Updated ATB analysis |
| `overdueRequest.py` | Overdue invoice report/notice generation |
| `overdueAnalysis.py` | Overdue invoice analysis |
| `manualJournalRequest.py` | Manual journal entry creation in Xero |
| `databaseInvoiceRequestv2.py` | Invoice data sync to database (Bullhorn integration) |
| `databaseMappings.py` | Mappings between Xero and Bullhorn data structures |
| `fetchFYAnnualLeave.py` | Annual leave data fetch |
| `sharepoint.py` | SharePoint integration utilities |
| `count_accpay.py` | Accounts payable count/analysis |

## Automation Rules
<!-- TODO: Key business logic, edge cases, special conditions -->
<!-- e.g. Which Xero orgs get included in which reports, ATB thresholds, overdue notice timing -->

## Coding Style & Conventions
<!-- TODO: Output format preferences (email format, report layout), naming conventions, recipient lists -->
<!-- e.g. Who receives ATB emails, report date format, Excel vs CSV output preference -->
