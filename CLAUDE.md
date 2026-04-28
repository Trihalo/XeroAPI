# CLAUDE.md

## SESSION START

1. Read tasks/lessons.md — apply all lessons before touching anything

2. Read tasks/todo.md — understand current state

3. If neither exists, create them before starting

## WORKFLOW

### 1. Plan First

- Enter plan mode for any non-trivial task (3+ steps)

- Write plan to tasks/todo.md before implementing

- If something goes wrong, STOP and re-plan — never push through

### 2. Subagent Strategy

- Use subagents to keep main context clean

- One task per subagent

- Throw more compute at hard problems

### 3. Self-Improvement Loop

- After any correction: update tasks/lessons.md

- Format: [date] | what went wrong | rule to prevent it

- Review lessons at every session start

### 4. Verification Standard

- Never mark complete without proving it works

- Run tests, check logs, diff behavior

- Ask: "Would a staff engineer approve this?"

### 5. Demand Elegance

- For non-trivial changes: is there a more elegant solution?

- If a fix feels hacky: rebuild it properly

- Don't over-engineer simple things

### 6. Autonomous Bug Fixing

- When given a bug: just fix it

- Go to logs, find root cause, resolve it

- No hand-holding needed

## CORE PRINCIPLES

- Simplicity First — touch minimal code

- No Laziness — root causes only, no temp fixes

- Never Assume — verify paths, APIs, variables before using

- Ask Once — one question upfront if unclear, never interrupt mid-task

## TASK MANAGEMENT

1. Plan → tasks/todo.md

2. Verify → confirm before implementing

3. Track → mark complete as you go

4. Explain → high-level summary each step

5. Learn → tasks/lessons.md after corrections

## LEARNED

(Claude fills this in over time)

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Trihalo Accountancy's Xero API Integration** — a multi-client financial automation platform connecting Xero accounting data to custom analysis workflows for clients: Cosmo, FutureYou, FlightRisk, H2coco, MacMerch. Workflows are triggered via a React/Flask dashboard or run on a schedule via GitHub Actions.

Each client folder has its own `CLAUDE.md` with client-specific context. The `dashboardWebsite/` folder has its own `CLAUDE.md` with frontend/backend context.

## Authentication

### Xero OAuth2

- Initial auth via `xeroAuth.py` (browser-based).
- Refresh tokens stored in **GitHub Variables** (not .env), rotated by `xeroAuthHelper.py` after each use.
- **Standard entry point**: `XeroAuthHelper.getXeroAccessToken()` — fetches latest refresh token from GitHub, exchanges it, stores the new one, returns the access token.
- Tenant IDs retrieved at runtime via `XeroTenants(access_token)`.

## Shared Helpers (`helpers/`)

| File                             | Purpose                                |
| -------------------------------- | -------------------------------------- |
| `dateStringsHelper.py`           | Date formatting utilities              |
| `emailAttachment.py`             | Email sending with attachments         |
| `fetchInvoicesForClient.py`      | Fetch invoices from Xero for a client  |
| `fetchXeroInvoices.py`           | Low-level Xero invoice fetching        |
| `fetchInvoiceAttachment.py`      | Download invoice attachments from Xero |
| `extractInvoiceAmountFromPDF.py` | Parse invoice amount from PDF          |
| `extractInvoiceNumberFromPDF.py` | Parse invoice number from PDF          |
| `databaseHelpers.py`             | Database read/write utilities          |

## Client Folders

| Folder        | Client                            | Summary                                                                 |
| ------------- | --------------------------------- | ----------------------------------------------------------------------- |
| `Cosmo/`      | Cosmopolitan Corp                 | Invoice approval automation                                             |
| `FutureYou/`  | FutureYou Contracting/Recruitment | ATB reports, overdue notices, manual journals, Bullhorn CRM integration |
| `FlightRisk/` | FlightRisk                        | AR payment allocation, prepayment allocation, draft invoice approval    |
| `H2coco/`     | H2coco                            | Draft invoice approval, supplier prepayments, trade finance payments    |
| `MacMerch/`   | MacMerch                          | Annual leave tracking, database invoice requests                        |

## `clientDetails/` Folder

Per-client JSON configuration files. Gitignored — do not commit client metadata.
