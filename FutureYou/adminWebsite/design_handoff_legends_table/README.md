# Handoff: Legends Table Redesign

## Overview

This is a redesign of the **Legends Table** tab inside the FutureYou admin forecasting section (`/forecasting/legends`). The original table showed consultant revenue split by Perm & Temp. The redesign adds:

- Year-on-year comparison against the **same elapsed period** last FY (daily granularity, not just month-end)
- Inline YoY deltas on every number (toggle between % and $)
- KPI summary strip at the top
- "Biggest Movers" callout (top 3 up / top 3 down)
- Expandable area roll-ups (group by Area, drill into consultants)
- Click-through consultant drawer with monthly sparkline + full breakdown
- YTD date picker (pick a specific day, not just a month)
- Compact / Comfortable density toggle

---

## About the Design Files

The files in this bundle are **HTML design prototypes** — not production code to ship directly. They use React + Babel in-browser and seeded mock data. The task is to **recreate this design inside the existing Next.js + Tailwind + shadcn codebase** at `frontend/app/forecasting/legends/page.tsx`, using the patterns and components already established there.

## Fidelity

**High-fidelity.** Colors, typography, spacing, interactions, and copy are all final. Recreate pixel-accurately using the existing Tailwind config (`globals.css`) and shadcn components.

---

## Design Tokens (from `frontend/app/globals.css`)

| Token | Value |
|---|---|
| `--navy` | `#003464` |
| `--salmon` | `#F25A57` |
| `--dark-grey` | `#6b6c6e` |
| `--light-grey` | `#EEEEEE` |
| Background page | `#EEEEEE` |
| Card/panel bg | `#FFFFFF` |
| Border | `#e5e7eb` |
| Row stripe (alt) | `#fcfcfd` |
| Area row bg | `#fbfcfd` |
| Total column bg | `rgba(0,52,100,0.04)` |
| Total footer bg | `rgba(0,52,100,0.09)` |

Typography: `'Helvetica Neue', Helvetica, Arial, sans-serif` (matches existing site). All numeric columns use `font-variant-numeric: tabular-nums`.

---

## Screens / Views

### 1. Page Header

- Title: `Legends Table — FY26` (22px, bold, navy)
- YTD badge: `YTD · 1 Jul – {day} {month} ({N} days)` — light-grey pill, 12px
- Subtitle: 13px dark-grey
- Last updated: 11px dark-grey, bold date

### 2. KPI Strip (4 cards, equal-width grid)

Each card: white bg, 1px border, 8px radius, 12px/14px padding. First card has `border-top: 2px solid navy`.

| Card | Value | Delta |
|---|---|---|
| Total revenue YTD | `fmt(cur.total)` | YoY delta (% or $) |
| Perm YTD | `fmt(cur.perm)` | YoY delta |
| Temp YTD | `fmt(cur.temp)` | YoY delta |
| Active consultants | count | No delta — "across N areas" subtitle |

Delta display:
- ▲ in navy when positive, ▼ in salmon when negative
- Toggle between `%` (e.g. `▲ +12%`) and `$` (e.g. `▲ +$14k`)
- Prior YTD value shown below in 11px dark-grey

### 3. Biggest Movers Strip (2 cards side by side)

Left card: **Biggest gainers YoY** (navy left-border, `▲` navy)
Right card: **Biggest drops YoY** (salmon left-border, `▼` salmon)

Each shows top 3 consultants by absolute $ change. Each row:
- Rank number (10px, dark-grey)
- Consultant name (13px, clickable → opens drawer)
- Current YTD compact (11px, dark-grey)
- Delta in % or $ mode (11px, bold, colored)

### 4. Controls Bar

White card, 1px border, 8px radius. Horizontal flex row with dividers between groups:

1. **YTD through** date picker button → dropdown with month grid (6 cols) + day grid (7 cols). "Reset to today" link at bottom.
2. **Compare** toggle: `%` | `$` pill tabs
3. **Group** toggle: `Consultant` | `Area` pill tabs
4. **Sort** tabs: `Total` | `YoY $` | `YoY %` | `A–Z`
5. **Search** input (right-aligned, 220px) with ⌕ icon prefix

Pill tab active state: navy bg, white text. Inactive: `#f3f4f6` bg, dark-grey text, hover `#e5e7eb`.

### 5. Main Table

No outer scroll wrapper needed (columns are few). Layout via CSS Grid:

```
Consultant column   Perm YTD   Temp YTD   [Total YTD — shaded]
```

Grid template (Consultant view): `minmax(200px, 1fr) 1fr 1fr 1.1fr`
Grid template (Area view): `minmax(220px, 1.3fr) 1fr 1fr 1.1fr`

**Header row**: `#f8f9fb` bg, 11px uppercase navy, 600 weight, 0.3 letter-spacing. 8px/14px padding. Total column has `border-left: 2px solid #e5e7eb` + shaded bg bleeding to right edge.

**Data rows**:
- Comfortable: 10px top/bottom padding. Compact: 6px.
- Odd rows: `#fff`. Even: `#fcfcfd`. Hover: `#f7f9fb`.
- Area rows: `#fbfcfd` bg, hover `#f3f6f9`, bold, navy text.
- Child consultant rows (when area expanded): 34px left-indent.
- Each cell: number (13.5px / 12.5px compact, tabular-nums) + delta below (10px).

**Area rows** have a `▶` chevron (rotates 90° when expanded) that reveals child consultants inline.

**Total footer row**: `#f1f3f5` bg, `border-top: 2px solid #e5e7eb`, bold. Total column uses `#rgba(0,52,100,0.09)` bg.

**Clicking a consultant row** opens the detail drawer.

**Total column** (rightmost): `border-left: 2px solid #e5e7eb`, shaded background bleeding to right edge with extra padding (`paddingRight: 22px, paddingLeft: 18px`).

**Perm/Temp columns**: `paddingRight: 18px, paddingLeft: 18px`.

### 6. Consultant Drawer (right-side panel)

Width: 520px, slides in from right. Backdrop: `rgba(0,0,0,0.3)`. Close on Esc or backdrop click.

**Header**: Consultant name (20px bold navy), area below (12px dark-grey), Esc button top-right.

**YTD summary cards** (3-col grid): Perm / Temp / Total. Each shows value, delta, prior YTD.

**Monthly sparkline** (360×60px SVG):
- Solid navy line = FY26 (current year, through YTD date)
- Dashed grey line = FY25 (full year)
- Shaded region = elapsed months
- Month labels below (abbreviated first letter, current month bold navy)

**Monthly breakdown table**:
- Columns: Month | Perm | Temp | Total | YoY
- Rows beyond YTD date: `opacity: 0.4`
- Current month row: bold, salmon `● thru {day}` label
- YTD Total footer: bold navy

**Footer note**: FY25 full-year total + % achieved.

---

## Interactions & Behaviour

### YoY Delta mode
State: `deltaMode: "pct" | "dollar"` — toggled in controls bar, propagated to all Delta components throughout the page (KPI strip, movers, table inline deltas, drawer).

### YTD Date picker
State: `dayOfFY: number` (1–365, FY-indexed from Jul 1).
- Default: today's day-of-FY (e.g. day 289 = 15 Apr).
- Changing the date re-aggregates all revenue figures by summing the daily series up to that day.
- "Reset to today" snaps back.
- FY months: Jul Aug Sep Oct Nov Dec Jan Feb Mar Apr May Jun (financial year).

### Consultant drawer
- Opens on row click (consultant rows only; area rows expand instead).
- Closes on Esc or backdrop click.
- Drawer content is driven by the same `dayOfFY` as the main table.

### Area expansion
- Clicking an area row toggles `expanded[area]` in local state.
- Expanded area shows child consultant rows indented below it.

### Search
- Filters by consultant name or area name (case-insensitive substring).

### Sort
- `total`: highest `cur.total` first
- `yoyAbs`: highest `cur.total - prev.total` first
- `yoyPct`: highest `(cur - prev) / prev` first
- `name`: alphabetical

### Density
- `comfortable`: 10px row padding, 13.5px font, area subtitle visible.
- `compact`: 6px row padding, 12.5px font, area subtitle hidden.

---

## API / Data Changes Required

The current endpoint `fcFetchLegends(FY)` returns `{ consultantTotals, consultantTypeTotals }` with monthly granularity.

### Option A — Daily granularity (recommended for YTD-to-day accuracy)
Extend the endpoint to return a daily series per consultant per type, so the frontend can sum up to any arbitrary day. Response shape per consultant-type row:

```ts
{
  Consultant: string;
  Area: string;
  Type: "Perm" | "Temp";
  // daily entries for each FY
  fy26Daily: { day: number; amount: number }[]; // day 1..365
  fy25Daily: { day: number; amount: number }[];
  // keep monthly for sparkline / drawer monthly breakdown
  fy26Monthly: { month: string; perm: number; temp: number }[];
  fy25Monthly: { month: string; perm: number; temp: number }[];
}
```

### Option B — Pre-aggregated to elapsed period (simpler backend, less flexible)
Keep monthly data but add a `ytdDay` query param. The backend sums to the requested day and returns pre-aggregated `{ cur, prev }` totals. Loses per-day picker flexibility.

### Prior FY data
Currently only FY26 is fetched. Add a second call `fcFetchLegends("FY25")` (or a `includePrior: true` param) to get the comparison year data.

---

## Files

| File | Purpose |
|---|---|
| `design_handoff_legends_table/Legends Table.html` | Full interactive prototype — open in browser to explore |
| `design_handoff_legends_table/data.js` | Mock data generator (daily granularity) |
| `design_handoff_legends_table/LegendsTable.jsx` | All React components for the redesign |
| `frontend/app/forecasting/legends/page.tsx` | Existing page to replace/extend |
| `frontend/app/globals.css` | Brand tokens (navy, salmon, etc.) |

Open `Legends Table.html` locally in a browser to interact with the full prototype before implementing.
