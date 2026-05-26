# Current Task: Site-Wide Auth + 4-Tier Role System

## Status: In Progress

## Goal
Move auth from the forecasting module level to the root app level.
Add 4 tiers: Finance, Admin, Partner, Recruiter.
Improve security: bcrypt-hash passwords, force-change on default.

## Role Access Matrix
| Route                   | Finance | Admin | Partner | Recruiter |
|-------------------------|---------|-------|---------|-----------|
| /                       | ✅      | ✅    | ✅      | ✅        |
| /annual-leave           | ✅      | ✅    | ❌      | ❌        |
| /talent-map             | ✅      | ✅    | ✅      | ✅        |
| /forecasting (main)     | ✅      | ✅    | ✅      | ❌        |
| /forecasting/revenue    | ✅      | ❌    | ❌      | ❌        |
| /forecasting/admin      | ✅      | ✅    | ❌      | ❌        |
| /legends                | ✅      | ✅    | ✅      | ✅        |
| /forecasting/password   | ✅      | ✅    | ✅      | ✅        |

## Files Changed
- [ ] lib/forecasting-cache.ts
- [ ] lib/forecasting-api.ts
- [ ] lib/api.ts
- [ ] components/AppShell.tsx (NEW)
- [ ] app/layout.tsx
- [ ] components/Sidebar.tsx
- [ ] app/forecasting/layout.tsx
- [ ] app/annual-leave/page.tsx
- [ ] app/page.tsx
- [ ] app/forecasting/password/page.tsx
- [ ] backend/app.py
