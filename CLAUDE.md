# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **Trihalo Accountancy's Xero API Integration** — a multi-client financial automation platform. It connects Xero accounting data to custom analysis workflows for several clients (Cosmo, FutureYou, FlightRisk, H2coco, MacMerch). Workflows are triggered via a React/Flask dashboard or run on a schedule via GitHub Actions.

## Commands

### Dashboard Frontend (dashboardWebsite/frontend/)
```bash
npm run dev       # Start Vite dev server
npm run build     # Production build
npm run lint      # ESLint
npm run preview   # Preview production build
```

### Dashboard Backend (dashboardWebsite/backend/)
```bash
pip install -r dashboardWebsite/backend/requirements.txt
python dashboardWebsite/backend/app.py
# Or via Docker:
docker build -t dashboard-backend ./dashboardWebsite/backend
docker run -p 5000:5000 dashboard-backend
```

### Python Client Scripts
Each client folder has its own `requirements.txt`. Scripts are typically run via GitHub Actions but can be run locally:
```bash
pip install -r <ClientFolder>/requirements.txt
python <ClientFolder>/<script>.py
```

## Architecture

### Request Flow
```
Dashboard UI (React) → Flask API (app.py) → GitHub Actions workflow dispatch → Python scripts → Xero API
```

1. **Dashboard** (`dashboardWebsite/frontend/`) — React + Vite + Tailwind/DaisyUI SPA. Users click buttons to trigger workflows.
2. **Flask Backend** (`dashboardWebsite/backend/app.py`) — REST API at `/api/trigger/{workflow}`. Dispatches GitHub Actions via GitHub API and logs calls to Firestore.
3. **GitHub Actions** (`.github/workflows/`) — 12 workflows that run Python scripts on ubuntu-latest with secrets/variables injected as env vars.
4. **Client Scripts** — One folder per client. Each script handles a specific automation (invoice approval, ATB reports, payment allocation, etc.).
5. **Shared Helpers** (`helpers/`) — Reusable utilities for Xero API calls, PDF extraction, email, and date/database logic.

### Authentication
- **Xero OAuth2**: Initial auth via `xeroAuth.py` (browser-based). Refresh tokens are stored in **GitHub Variables** (not .env) and rotated by `xeroAuthHelper.py` after each use.
- `XeroAuthHelper.getXeroAccessToken()` is the standard entry point in scripts — it fetches the latest refresh token from GitHub, exchanges it, stores the new one, and returns the access token.
- Tenant IDs are retrieved at runtime via `XeroTenants(access_token)`.
- **Outlook OAuth2**: Managed by `outlookAuthRefresh.py` separately.

### Key Environment Variables (stored as GitHub Secrets/Variables)
- `XERO_REFRESH_TOKEN_<CLIENT>` — per-client refresh tokens (stored in GitHub Variables)
- `<CLIENT>_CLIENT_ID` / `<CLIENT>_CLIENT_SECRET` — Xero app credentials per client
- `GH_PAT` — GitHub PAT for updating GitHub Variables and triggering workflows
- `EMAIL_SENDER_GMAIL` / `EMAIL_PASSWORD_GMAIL` — Gmail credentials for email sending

### Client Folders
| Folder | Client | Key Scripts |
|--------|--------|-------------|
| `Cosmo/` | Cosmopolitan Corp | `invoiceApprovalRequest.py` |
| `FutureYou/` | FutureYou Contracting | `atbRequest.py`, `overdueRequest.py`, `manualJournalRequest.py`, Bullhorn CRM integration |
| `FlightRisk/` | FlightRisk | `ARPaymentAllocator.py`, `CustomerPrepaymentARAllocator.py`, `draftInvoiceApprover.py` |
| `H2coco/` | H2coco | `draftInvoiceApprover.py`, `supplierPrepayments.py`, `tradeFinancePaymentsRequest.py` |
| `MacMerch/` | MacMerch | Various custom scripts |

### `clientDetails/` Folder
Contains per-client JSON configuration files. This folder is gitignored — do not commit client metadata.
