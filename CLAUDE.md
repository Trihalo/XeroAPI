# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Trihalo Accountancy's Xero API Integration** — a multi-client financial automation platform connecting Xero accounting data to custom analysis workflows for clients: Cosmo, FutureYou, FlightRisk, H2coco, MacMerch. Workflows are triggered via a React/Flask dashboard or run on a schedule via GitHub Actions.

Each client folder has its own `CLAUDE.md` with client-specific context. The `dashboardWebsite/` folder has its own `CLAUDE.md` with frontend/backend context.

## Architecture

### Request Flow
```
Dashboard UI (React) → Flask API (app.py) → GitHub Actions workflow dispatch → Python scripts → Xero API
```

1. **Dashboard** (`dashboardWebsite/`) — React + Vite + Tailwind/DaisyUI frontend, Flask backend. See `dashboardWebsite/CLAUDE.md` for details.
2. **GitHub Actions** (`.github/workflows/`) — Workflows run Python scripts on ubuntu-latest with secrets/variables injected as env vars.
3. **Client Scripts** — One folder per client. Each script handles a specific automation. See the client folder's `CLAUDE.md` for details.
4. **Shared Helpers** (`helpers/`) — Reusable utilities for Xero API calls, PDF extraction, email, and date/database logic.

## Running Client Scripts
Each client folder has its own `requirements.txt`. Scripts are run via GitHub Actions but can be run locally:
```bash
pip install -r <ClientFolder>/requirements.txt
python <ClientFolder>/<script>.py
```

## Authentication

### Xero OAuth2
- Initial auth via `xeroAuth.py` (browser-based).
- Refresh tokens stored in **GitHub Variables** (not .env), rotated by `xeroAuthHelper.py` after each use.
- **Standard entry point**: `XeroAuthHelper.getXeroAccessToken()` — fetches latest refresh token from GitHub, exchanges it, stores the new one, returns the access token.
- Tenant IDs retrieved at runtime via `XeroTenants(access_token)`.

### Outlook OAuth2
- Managed separately by `outlookAuthRefresh.py`.

## Key Environment Variables (GitHub Secrets/Variables)
| Variable | Purpose |
|----------|---------|
| `XERO_REFRESH_TOKEN_<CLIENT>` | Per-client refresh tokens (GitHub Variables) |
| `<CLIENT>_CLIENT_ID` / `<CLIENT>_CLIENT_SECRET` | Xero app credentials per client |
| `GH_PAT` | GitHub PAT for updating Variables and triggering workflows |
| `EMAIL_SENDER_GMAIL` / `EMAIL_PASSWORD_GMAIL` | Gmail credentials for email sending |

## Shared Helpers (`helpers/`)
| File | Purpose |
|------|---------|
| `dateStringsHelper.py` | Date formatting utilities |
| `emailAttachment.py` | Email sending with attachments |
| `fetchInvoicesForClient.py` | Fetch invoices from Xero for a client |
| `fetchXeroInvoices.py` | Low-level Xero invoice fetching |
| `fetchInvoiceAttachment.py` | Download invoice attachments from Xero |
| `extractInvoiceAmountFromPDF.py` | Parse invoice amount from PDF |
| `extractInvoiceNumberFromPDF.py` | Parse invoice number from PDF |
| `databaseHelpers.py` | Database read/write utilities |

## Client Folders
| Folder | Client | Summary |
|--------|--------|---------|
| `Cosmo/` | Cosmopolitan Corp | Invoice approval automation |
| `FutureYou/` | FutureYou Contracting/Recruitment | ATB reports, overdue notices, manual journals, Bullhorn CRM integration |
| `FlightRisk/` | FlightRisk | AR payment allocation, prepayment allocation, draft invoice approval |
| `H2coco/` | H2coco | Draft invoice approval, supplier prepayments, trade finance payments |
| `MacMerch/` | MacMerch | Annual leave tracking, database invoice requests |

## `clientDetails/` Folder
Per-client JSON configuration files. Gitignored — do not commit client metadata.

---

## Coding Best Practices

These apply across all client scripts and shared helpers.

### General Python
<!-- TODO: Add your preferred Python conventions — e.g. f-strings vs format(), type hints, logging vs print, error handling patterns -->

### Error Handling
<!-- TODO: How to handle Xero API errors, rate limits, missing data — e.g. retry logic, fail-fast vs silent skip -->

### Xero API Usage
<!-- TODO: Preferred patterns for API calls — e.g. always use XeroAuthHelper, batch size limits, pagination handling -->

### Logging & Output
<!-- TODO: Logging style — e.g. print statements vs logging module, log file location conventions, verbosity level -->

### Script Structure
<!-- TODO: Preferred script layout — e.g. main() function, argument parsing, environment variable loading pattern -->

### Testing
<!-- TODO: How scripts are validated before deployment — e.g. dry-run flags, test tenant usage, manual checks -->
