"use client";

import { useEffect, useState, useMemo, useRef } from "react";
import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { useRecruiterData } from "@/hooks/forecasting/useRecruiterData";
import { fcFetchLegends, type LegendsMonthRow } from "@/lib/forecasting-api";
import { FC_AUTH } from "@/lib/forecasting-cache";

// ── Constants ─────────────────────────────────────────────────────────────────

const CURRENT_FY = "FY26";
const PRIOR_FY = "FY25";
const MONTHS = [
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
] as const;
const DAYS_IN_MONTH = [31, 31, 30, 31, 30, 31, 31, 28, 31, 30, 31, 30] as const;
const CUM_DAYS = DAYS_IN_MONTH.reduce<number[]>((a, d, i) => {
  a.push((a[i - 1] ?? 0) + d);
  return a;
}, []);

// ── Types ─────────────────────────────────────────────────────────────────────

interface MonthlyEntry {
  perm: number;
  temp: number;
}

interface ConsultantRow {
  name: string;
  area: string;
  fy26Monthly: MonthlyEntry[];
  fy25Monthly: MonthlyEntry[];
  cur: { perm: number; temp: number; total: number };
  prev: { perm: number; temp: number; total: number };
}

interface AreaRow {
  area: string;
  consultants: ConsultantRow[];
  cur: { perm: number; temp: number; total: number };
  prev: { perm: number; temp: number; total: number };
}

type YTD = { monthIdx: number; dayOfMonth: number };
type DeltaMode = "pct" | "dollar";
type ViewMode = "Consultant" | "Area";
type SortKey = "total" | "yoyAbs" | "yoyPct" | "name";

// ── FY / date helpers ─────────────────────────────────────────────────────────

function getTodayYTD(): YTD {
  const today = new Date();
  const m = today.getMonth(); // 0=Jan..11=Dec
  const fyMonthIdx = m >= 6 ? m - 6 : m + 6;
  return { monthIdx: fyMonthIdx, dayOfMonth: today.getDate() };
}

function toDayOfFY(monthIdx: number, dayOfMonth: number): number {
  return (monthIdx === 0 ? 0 : CUM_DAYS[monthIdx - 1]) + dayOfMonth;
}

function fmtYTD(ytd: YTD): string {
  return `${ytd.dayOfMonth} ${MONTHS[ytd.monthIdx]}`;
}

function monthNameToFyIdx(name: string): number {
  return (MONTHS as readonly string[]).indexOf(name);
}

// ── Number formatters ─────────────────────────────────────────────────────────

function fmt(n: number): string {
  const v = Math.round(n || 0);
  if (!v) return "–";
  return v.toLocaleString("en-AU");
}

function fmtCompact(n: number): string {
  const v = Math.round(n || 0);
  if (v === 0) return "0";
  if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(1) + "m";
  if (Math.abs(v) >= 1_000) return (v / 1_000).toFixed(0) + "k";
  return String(v);
}

function calcPct(cur: number, prev: number): number {
  if (!prev) return cur > 0 ? 1 : 0;
  return (cur - prev) / prev;
}

function fmtPct(p: number): string {
  if (!isFinite(p)) return "—";
  const v = Math.round(p * 100);
  return (v > 0 ? "+" : "") + v + "%";
}

function fmtDollarDeltaCompact(diff: number): string {
  const abs = Math.abs(Math.round(diff));
  const sign = diff >= 0 ? "+" : "−";
  return sign + "$" + fmtCompact(abs);
}

// ── Data builder ──────────────────────────────────────────────────────────────

function buildConsultantData(
  curRows: LegendsMonthRow[],
  prevRows: LegendsMonthRow[],
  ytd: YTD,
  recruiterNames: string[]
): ConsultantRow[] {
  const map = new Map<
    string,
    {
      name: string;
      area: string;
      fy26Monthly: MonthlyEntry[];
      fy25Monthly: MonthlyEntry[];
    }
  >();

  const empty = (): MonthlyEntry[] =>
    Array.from({ length: 12 }, () => ({ perm: 0, temp: 0 }));

  for (const row of [...curRows, ...prevRows]) {
    if (recruiterNames.length > 0 && !recruiterNames.includes(row.Consultant))
      continue;
    if (!map.has(row.Consultant)) {
      map.set(row.Consultant, {
        name: row.Consultant,
        area: row.Area,
        fy26Monthly: empty(),
        fy25Monthly: empty(),
      });
    }
  }

  for (const row of curRows) {
    const e = map.get(row.Consultant);
    if (!e) continue;
    const idx = monthNameToFyIdx(row.MonthName);
    if (idx < 0) continue;
    if (row.Type === "Perm") e.fy26Monthly[idx].perm += row.TotalMargin;
    else e.fy26Monthly[idx].temp += row.TotalMargin;
  }

  for (const row of prevRows) {
    const e = map.get(row.Consultant);
    if (!e) continue;
    const idx = monthNameToFyIdx(row.MonthName);
    if (idx < 0) continue;
    if (row.Type === "Perm") e.fy25Monthly[idx].perm += row.TotalMargin;
    else e.fy25Monthly[idx].temp += row.TotalMargin;
  }

  return Array.from(map.values()).map((e) => {
    const cur = computeYTDTotals(e.fy26Monthly, ytd.monthIdx, ytd.dayOfMonth);
    const prev = computeYTDTotals(e.fy25Monthly, ytd.monthIdx, ytd.dayOfMonth);
    return { ...e, cur, prev };
  });
}

function computeYTDTotals(
  monthly: MonthlyEntry[],
  monthIdx: number,
  _dayOfMonth: number
): { perm: number; temp: number; total: number } {
  let perm = 0,
    temp = 0;
  for (let i = 0; i <= monthIdx && i < 12; i++) {
    perm += monthly[i].perm;
    temp += monthly[i].temp;
  }
  return { perm, temp, total: perm + temp };
}

// ── Delta ─────────────────────────────────────────────────────────────────────

function Delta({
  cur,
  prev,
  deltaMode,
  size = "sm",
}: {
  cur: number;
  prev: number;
  deltaMode: DeltaMode;
  size?: "xs" | "sm" | "md";
}) {
  if (!prev && !cur) return <span style={{ color: "#c9ccd1" }}>—</span>;
  const diff = cur - prev;
  const p = calcPct(cur, prev);
  const up = diff >= 0;
  const color = up ? "#003464" : "#F25A57";
  const arrow = up ? "▲" : "▼";
  const text = deltaMode === "pct" ? fmtPct(p) : fmtDollarDeltaCompact(diff);
  const fs = size === "xs" ? 10 : size === "sm" ? 11 : 12;
  return (
    <span
      style={{
        color,
        fontSize: fs,
        fontWeight: 600,
        fontVariantNumeric: "tabular-nums",
        letterSpacing: 0.2,
      }}
    >
      {arrow} {text}
    </span>
  );
}

// ── MonthlySparkline ──────────────────────────────────────────────────────────

function MonthlySparkline({
  fy26Monthly,
  fy25Monthly,
  todayMonthIdx,
}: {
  fy26Monthly: MonthlyEntry[];
  fy25Monthly: MonthlyEntry[];
  todayMonthIdx: number;
}) {
  const vw = 600,
    h = 72,
    pad = 4;
  const step = (vw - pad * 2) / 11;
  const all = [...fy26Monthly, ...fy25Monthly].map((m) => m.perm + m.temp);
  const max = Math.max(1, ...all);

  const pathStr = (arr: MonthlyEntry[], clip: number) =>
    arr
      .slice(0, clip)
      .map((m, i) => {
        const x = pad + i * step;
        const y = h - pad - ((m.perm + m.temp) / max) * (h - pad * 2);
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");

  return (
    <svg width="100%" viewBox={`0 0 ${vw} ${h}`} style={{ display: "block" }}>
      <rect
        x={pad}
        y={0}
        width={todayMonthIdx * step}
        height={h}
        fill="#003464"
        opacity={0.04}
      />
      <path
        d={pathStr(fy25Monthly, 12)}
        fill="none"
        stroke="#c9ccd1"
        strokeWidth={1.5}
        strokeDasharray="3 2"
      />
      <path
        d={pathStr(fy26Monthly, todayMonthIdx + 1)}
        fill="none"
        stroke="#003464"
        strokeWidth={1.75}
      />
      {fy26Monthly.slice(0, todayMonthIdx + 1).map((m, i) => {
        const x = pad + i * step;
        const y = h - pad - ((m.perm + m.temp) / max) * (h - pad * 2);
        return <circle key={i} cx={x} cy={y} r={1.75} fill="#003464" />;
      })}
    </svg>
  );
}

// ── TabBtn ────────────────────────────────────────────────────────────────────

function TabBtn({
  active,
  onClick,
  children,
  size = "sm",
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  size?: "xs" | "sm";
}) {
  const pad = size === "xs" ? "4px 10px" : "6px 12px";
  const fs = size === "xs" ? 12 : 13;
  return (
    <button
      onClick={onClick}
      style={{
        padding: pad,
        fontSize: fs,
        fontWeight: 500,
        borderRadius: 6,
        border: "none",
        cursor: "pointer",
        background: active ? "#003464" : "#f3f4f6",
        color: active ? "#fff" : "#6b6c6e",
        transition: "background 120ms",
        fontFamily: "inherit",
      }}
      onMouseEnter={(e) => {
        if (!active)
          (e.currentTarget as HTMLButtonElement).style.background = "#e5e7eb";
      }}
      onMouseLeave={(e) => {
        if (!active)
          (e.currentTarget as HTMLButtonElement).style.background = "#f3f4f6";
      }}
    >
      {children}
    </button>
  );
}

// ── YTDDatePicker ─────────────────────────────────────────────────────────────

function YTDDatePicker({
  ytd,
  setYtd,
  todayYTD,
}: {
  ytd: YTD;
  setYtd: (v: YTD) => void;
  todayYTD: YTD;
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node))
        setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const daysInSelected = DAYS_IN_MONTH[ytd.monthIdx];

  const pickMonth = (m: number) => {
    const d = Math.min(ytd.dayOfMonth, DAYS_IN_MONTH[m]);
    setYtd({ monthIdx: m, dayOfMonth: d });
  };

  return (
    <div ref={wrapRef} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "6px 12px",
          fontSize: 12,
          fontFamily: "inherit",
          fontWeight: 500,
          background: "#fff",
          color: "#111",
          border: `1px solid ${open ? "#003464" : "#e5e7eb"}`,
          borderRadius: 6,
          cursor: "pointer",
          lineHeight: 1,
        }}
      >
        <span
          style={{
            color: "#6b6c6e",
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: 0.3,
            textTransform: "uppercase",
          }}
        >
          YTD through
        </span>
        <span
          style={{
            color: "#003464",
            fontWeight: 700,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {fmtYTD(ytd)}
        </span>
        <span style={{ color: "#6b6c6e", fontSize: 10 }}>▾</span>
      </button>

      {open && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 6px)",
            left: 0,
            zIndex: 30,
            background: "#fff",
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            boxShadow: "0 8px 24px rgba(0,0,0,0.10)",
            padding: 12,
            width: 300,
          }}
        >
          <div
            style={{
              fontSize: 10.5,
              color: "#6b6c6e",
              fontWeight: 600,
              letterSpacing: 0.3,
              textTransform: "uppercase",
              marginBottom: 6,
            }}
          >
            Month
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(6, 1fr)",
              gap: 4,
              marginBottom: 10,
            }}
          >
            {MONTHS.map((m, i) => (
              <button
                key={m}
                onClick={() => pickMonth(i)}
                style={{
                  padding: "6px 0",
                  fontSize: 11,
                  fontFamily: "inherit",
                  border: "none",
                  borderRadius: 4,
                  cursor: "pointer",
                  background: i === ytd.monthIdx ? "#003464" : "#f3f4f6",
                  color: i === ytd.monthIdx ? "#fff" : "#6b6c6e",
                  fontWeight: 500,
                }}
              >
                {m}
              </button>
            ))}
          </div>
          <div
            style={{
              fontSize: 10.5,
              color: "#6b6c6e",
              fontWeight: 600,
              letterSpacing: 0.3,
              textTransform: "uppercase",
              marginBottom: 6,
            }}
          >
            Day
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(7, 1fr)",
              gap: 3,
            }}
          >
            {Array.from({ length: daysInSelected }, (_, i) => i + 1).map(
              (d) => (
                <button
                  key={d}
                  onClick={() => {
                    setYtd({ ...ytd, dayOfMonth: d });
                    setOpen(false);
                  }}
                  style={{
                    padding: "5px 0",
                    fontSize: 11,
                    fontFamily: "inherit",
                    border: "none",
                    borderRadius: 4,
                    cursor: "pointer",
                    background:
                      d === ytd.dayOfMonth ? "#003464" : "transparent",
                    color: d === ytd.dayOfMonth ? "#fff" : "#111",
                    fontWeight: d === ytd.dayOfMonth ? 600 : 400,
                    fontVariantNumeric: "tabular-nums",
                  }}
                  onMouseEnter={(e) => {
                    if (d !== ytd.dayOfMonth)
                      (e.currentTarget as HTMLButtonElement).style.background =
                        "#f3f4f6";
                  }}
                  onMouseLeave={(e) => {
                    if (d !== ytd.dayOfMonth)
                      (e.currentTarget as HTMLButtonElement).style.background =
                        "transparent";
                  }}
                >
                  {d}
                </button>
              )
            )}
          </div>
          <div
            style={{
              marginTop: 10,
              paddingTop: 10,
              borderTop: "1px solid #f1f3f5",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <button
              onClick={() => {
                setYtd(todayYTD);
                setOpen(false);
              }}
              style={{
                background: "transparent",
                border: "none",
                color: "#003464",
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
                padding: 0,
                fontFamily: "inherit",
              }}
            >
              Reset to today ({fmtYTD(todayYTD)})
            </button>
            <span style={{ fontSize: 10.5, color: "#6b6c6e" }}>
              FY Jul 1 – Jun 30
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// ── KPI Strip ─────────────────────────────────────────────────────────────────

function KpiStrip({
  rows,
  numAreas,
  deltaMode,
}: {
  rows: ConsultantRow[];
  numAreas: number;
  deltaMode: DeltaMode;
}) {
  const totals = rows.reduce(
    (acc, r) => {
      acc.cur.perm += r.cur.perm;
      acc.cur.temp += r.cur.temp;
      acc.cur.total += r.cur.total;
      acc.prev.perm += r.prev.perm;
      acc.prev.temp += r.prev.temp;
      acc.prev.total += r.prev.total;
      return acc;
    },
    {
      cur: { perm: 0, temp: 0, total: 0 },
      prev: { perm: 0, temp: 0, total: 0 },
    }
  );

  const cards = [
    {
      label: "Total revenue YTD",
      cur: totals.cur.total,
      prev: totals.prev.total,
      accent: true,
      hideDelta: false,
    },
    {
      label: "Perm YTD",
      cur: totals.cur.perm,
      prev: totals.prev.perm,
      accent: false,
      hideDelta: false,
    },
    {
      label: "Temp YTD",
      cur: totals.cur.temp,
      prev: totals.prev.temp,
      accent: false,
      hideDelta: false,
    },
    {
      label: "Active consultants",
      cur: rows.length,
      prev: rows.length,
      accent: false,
      hideDelta: true,
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map((c, i) => (
        <div
          key={i}
          style={{
            background: "#fff",
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            padding: "12px 14px",
            borderTop: c.accent ? "2px solid #003464" : undefined,
          }}
        >
          <div
            style={{
              fontSize: 11,
              color: "#6b6c6e",
              fontWeight: 500,
              letterSpacing: 0.3,
              textTransform: "uppercase",
            }}
          >
            {c.label}
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              gap: 8,
              marginTop: 4,
            }}
          >
            <div
              style={{
                fontSize: 20,
                fontWeight: 700,
                color: "#111",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {c.hideDelta ? c.cur : fmt(c.cur)}
            </div>
            {!c.hideDelta && (
              <Delta
                cur={c.cur}
                prev={c.prev}
                deltaMode={deltaMode}
                size="md"
              />
            )}
          </div>
          {!c.hideDelta && (
            <div
              style={{
                fontSize: 11,
                color: "#6b6c6e",
                marginTop: 2,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              prior YTD {fmt(c.prev)}
            </div>
          )}
          {c.hideDelta && (
            <div style={{ fontSize: 11, color: "#6b6c6e", marginTop: 2 }}>
              across {numAreas} areas
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Movers ────────────────────────────────────────────────────────────────────

// ── DataCell ──────────────────────────────────────────────────────────────────

function DataCell({
  cur,
  prev,
  deltaMode,
}: {
  cur: number;
  prev: number;
  deltaMode: DeltaMode;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-end",
        gap: 2,
        paddingRight: 18,
        paddingLeft: 18,
      }}
    >
      <span
        style={{
          fontSize: 13.5,
          color: "#111",
          fontVariantNumeric: "tabular-nums",
          fontWeight: 500,
        }}
      >
        {fmt(cur)}
      </span>
      <Delta cur={cur} prev={prev} deltaMode={deltaMode} size="xs" />
    </div>
  );
}

// ── LegendsTable ──────────────────────────────────────────────────────────────

function LegendsTable({
  rows,
  viewMode,
  search,
  onOpenDetail,
  sortKey,
  deltaMode,
}: {
  rows: ConsultantRow[];
  viewMode: ViewMode;
  search: string;
  onOpenDetail: (name: string) => void;
  sortKey: SortKey;
  deltaMode: DeltaMode;
}) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (r) =>
        r.name.toLowerCase().includes(q) || r.area.toLowerCase().includes(q)
    );
  }, [rows, search]);

  const sortConsultants = (a: ConsultantRow, b: ConsultantRow): number => {
    if (sortKey === "name") return a.name.localeCompare(b.name);
    if (sortKey === "yoyAbs")
      return b.cur.total - b.prev.total - (a.cur.total - a.prev.total);
    if (sortKey === "yoyPct")
      return (
        calcPct(b.cur.total, b.prev.total) - calcPct(a.cur.total, a.prev.total)
      );
    return b.cur.total - a.cur.total;
  };

  const areaRows = useMemo<AreaRow[]>(() => {
    const areaMap = new Map<string, AreaRow>();
    filtered.forEach((c) => {
      if (!areaMap.has(c.area)) {
        areaMap.set(c.area, {
          area: c.area,
          consultants: [],
          cur: { perm: 0, temp: 0, total: 0 },
          prev: { perm: 0, temp: 0, total: 0 },
        });
      }
      const a = areaMap.get(c.area)!;
      a.consultants.push(c);
      a.cur.perm += c.cur.perm;
      a.cur.temp += c.cur.temp;
      a.cur.total += c.cur.total;
      a.prev.perm += c.prev.perm;
      a.prev.temp += c.prev.temp;
      a.prev.total += c.prev.total;
    });
    return [...areaMap.values()].sort((a, b) => {
      if (sortKey === "name") return a.area.localeCompare(b.area);
      if (sortKey === "yoyAbs")
        return b.cur.total - b.prev.total - (a.cur.total - a.prev.total);
      if (sortKey === "yoyPct")
        return (
          calcPct(b.cur.total, b.prev.total) -
          calcPct(a.cur.total, a.prev.total)
        );
      return b.cur.total - a.cur.total;
    });
  }, [filtered, sortKey]);

  const totals = useMemo(
    () =>
      filtered.reduce(
        (acc, r) => {
          acc.cur.perm += r.cur.perm;
          acc.cur.temp += r.cur.temp;
          acc.cur.total += r.cur.total;
          acc.prev.perm += r.prev.perm;
          acc.prev.temp += r.prev.temp;
          acc.prev.total += r.prev.total;
          return acc;
        },
        {
          cur: { perm: 0, temp: 0, total: 0 },
          prev: { perm: 0, temp: 0, total: 0 },
        }
      ),
    [filtered]
  );

  const rowPad = "10px 14px";
  const nameCol =
    viewMode === "Area" ? "minmax(220px, 1.3fr)" : "minmax(200px, 1fr)";
  const gridCols = `${nameCol} 1fr 1fr 1.1fr`;

  // ── Render a single data row ──
  const renderRow = (
    kind: "consultant" | "area" | "consultantChild",
    entity: ConsultantRow | AreaRow,
    idx: number,
    parent?: string
  ) => {
    const isArea = kind === "area";
    const isChild = kind === "consultantChild";
    const isExpanded = isArea && expanded[(entity as AreaRow).area];
    const label = isArea
      ? (entity as AreaRow).area
      : (entity as ConsultantRow).name;
    const rowKey = isArea
      ? `A:${(entity as AreaRow).area}`
      : `${isChild ? "CC:" + parent + ":" : "C:"}${
          (entity as ConsultantRow).name
        }`;

    return (
      <div
        key={rowKey}
        onClick={() => {
          if (isArea)
            setExpanded((prev) => ({
              ...prev,
              [(entity as AreaRow).area]: !prev[(entity as AreaRow).area],
            }));
          else onOpenDetail((entity as ConsultantRow).name);
        }}
        style={{
          display: "grid",
          gridTemplateColumns: gridCols,
          padding: rowPad,
          paddingLeft: isChild ? 34 : 14,
          borderBottom: "1px solid #f1f3f5",
          background: isArea ? "#fbfcfd" : idx % 2 === 0 ? "#fff" : "#fcfcfd",
          fontWeight: isArea ? 600 : 400,
          cursor: "pointer",
          alignItems: "center",
          transition: "background 100ms",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLDivElement).style.background = isArea
            ? "#f3f6f9"
            : "#f7f9fb";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLDivElement).style.background = isArea
            ? "#fbfcfd"
            : idx % 2 === 0
            ? "#fff"
            : "#fcfcfd";
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            overflow: "hidden",
          }}
        >
          {isArea && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 16,
                height: 16,
                color: "#003464",
                fontSize: 10,
                transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
                transition: "transform 140ms",
              }}
            >
              ▶
            </span>
          )}
          <div style={{ overflow: "hidden" }}>
            <div
              style={{
                fontSize: 13.5,
                color: isArea ? "#003464" : "#111",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {label}
            </div>
            {isArea && (
              <div style={{ fontSize: 11, color: "#6b6c6e", marginTop: 1 }}>
                {(entity as AreaRow).consultants.length}{" "}
                {(entity as AreaRow).consultants.length === 1
                  ? "consultant"
                  : "consultants"}
              </div>
            )}
            {!isArea && !isChild && (
              <div style={{ fontSize: 11, color: "#6b6c6e", marginTop: 1 }}>
                {(entity as ConsultantRow).area}
              </div>
            )}
          </div>
        </div>

        <DataCell
          cur={entity.cur.perm}
          prev={entity.prev.perm}
          deltaMode={deltaMode}
        />
        <DataCell
          cur={entity.cur.temp}
          prev={entity.prev.temp}
          deltaMode={deltaMode}
        />

        <div
          style={{
            background: "rgba(0,52,100,0.04)",
            marginRight: -14,
            paddingRight: 22,
            paddingLeft: 18,
            marginTop: -10,
            paddingTop: 10,
            marginBottom: -10,
            paddingBottom: 10,
            borderLeft: "2px solid #e5e7eb",
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-end",
            gap: 2,
          }}
        >
          <span
            style={{
              fontSize: 14,
              color: "#003464",
              fontWeight: 600,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {fmt(entity.cur.total)}
          </span>
          <Delta
            cur={entity.cur.total}
            prev={entity.prev.total}
            deltaMode={deltaMode}
            size="xs"
          />
        </div>
      </div>
    );
  };

  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: gridCols,
          padding: "8px 14px",
          background: "#f8f9fb",
          borderBottom: "1px solid #e5e7eb",
          fontSize: 11,
          fontWeight: 600,
          color: "#003464",
          letterSpacing: 0.3,
          textTransform: "uppercase",
        }}
      >
        <div>{viewMode === "Consultant" ? "Consultant" : "Area"}</div>
        <div style={{ textAlign: "right", paddingRight: 18, paddingLeft: 18 }}>
          Perm YTD
        </div>
        <div style={{ textAlign: "right", paddingRight: 18, paddingLeft: 18 }}>
          Temp YTD
        </div>
        <div
          style={{
            textAlign: "right",
            background: "rgba(0,52,100,0.04)",
            marginRight: -14,
            paddingRight: 22,
            paddingLeft: 18,
            marginTop: -8,
            paddingTop: 8,
            marginBottom: -8,
            paddingBottom: 8,
            borderLeft: "2px solid #e5e7eb",
          }}
        >
          Total YTD
        </div>
      </div>

      {/* Empty state */}
      {filtered.length === 0 && (
        <div
          style={{
            padding: "24px 14px",
            textAlign: "center",
            fontSize: 13,
            color: "#6b6c6e",
          }}
        >
          No results{search ? ` for "${search}"` : ""}.
        </div>
      )}

      {/* Rows */}
      {viewMode === "Consultant"
        ? [...filtered]
            .sort(sortConsultants)
            .map((c, i) => renderRow("consultant", c, i))
        : areaRows.flatMap((a, i) => [
            renderRow("area", a, i),
            ...(expanded[a.area]
              ? [...a.consultants]
                  .sort(sortConsultants)
                  .map((c, ci) => renderRow("consultantChild", c, ci, a.area))
              : []),
          ])}

      {/* Footer */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: gridCols,
          padding: "10px 14px",
          background: "#f1f3f5",
          borderTop: "2px solid #e5e7eb",
          fontWeight: 700,
          alignItems: "center",
        }}
      >
        <div style={{ color: "#003464", fontSize: 13 }}>Total</div>
        <DataCell
          cur={totals.cur.perm}
          prev={totals.prev.perm}
          deltaMode={deltaMode}
        />
        <DataCell
          cur={totals.cur.temp}
          prev={totals.prev.temp}
          deltaMode={deltaMode}
        />
        <div
          style={{
            background: "rgba(0,52,100,0.09)",
            marginRight: -14,
            paddingRight: 22,
            paddingLeft: 18,
            marginTop: -10,
            paddingTop: 10,
            marginBottom: -10,
            paddingBottom: 10,
            borderLeft: "2px solid #e5e7eb",
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-end",
            gap: 2,
          }}
        >
          <span
            style={{
              fontSize: 14.5,
              color: "#003464",
              fontWeight: 800,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {fmt(totals.cur.total)}
          </span>
          <Delta
            cur={totals.cur.total}
            prev={totals.prev.total}
            deltaMode={deltaMode}
            size="sm"
          />
        </div>
      </div>
    </div>
  );
}

// ── Drawer ────────────────────────────────────────────────────────────────────

function Drawer({
  open,
  onClose,
  entity,
  ytd,
  deltaMode,
}: {
  open: boolean;
  onClose: () => void;
  entity: ConsultantRow | null;
  ytd: YTD;
  deltaMode: DeltaMode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!entity) return null;

  const full25Total = entity.fy25Monthly.reduce(
    (s, m) => s + m.perm + m.temp,
    0
  );

  const monthBreakdown = entity.fy26Monthly.map((m, i) => ({
    perm: m.perm,
    temp: m.temp,
    cur: m.perm + m.temp,
    prev: entity.fy25Monthly[i].perm + entity.fy25Monthly[i].temp,
  }));

  const pctOfPrior =
    full25Total > 0 ? Math.round((entity.cur.total / full25Total) * 100) : 0;

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.3)",
          opacity: open ? 1 : 0,
          pointerEvents: open ? "auto" : "none",
          transition: "opacity 200ms",
          zIndex: 40,
        }}
      />
      <aside
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: 680,
          maxWidth: "95vw",
          background: "#fff",
          boxShadow: "-8px 0 28px rgba(0,0,0,0.12)",
          transform: open ? "translateX(0)" : "translateX(100%)",
          transition: "transform 220ms cubic-bezier(.4,.0,.2,1)",
          zIndex: 50,
          display: "flex",
          flexDirection: "column",
          fontFamily: "inherit",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid #e5e7eb",
            display: "flex",
            alignItems: "start",
            gap: 12,
          }}
        >
          <div style={{ flex: 1 }}>
            <div
              style={{
                fontSize: 11,
                color: "#6b6c6e",
                fontWeight: 600,
                letterSpacing: 0.4,
                textTransform: "uppercase",
              }}
            >
              Consultant
            </div>
            <h2
              style={{
                fontSize: 20,
                fontWeight: 700,
                color: "#003464",
                margin: "2px 0 0",
              }}
            >
              {entity.name}
            </h2>
            <div style={{ fontSize: 12, color: "#6b6c6e", marginTop: 2 }}>
              {entity.area}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "1px solid #e5e7eb",
              borderRadius: 6,
              padding: "4px 8px",
              fontSize: 12,
              color: "#6b6c6e",
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Esc
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflow: "auto", padding: "16px 20px" }}>
          {/* YTD summary cards */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: 10,
              marginBottom: 18,
            }}
          >
            {(
              [
                {
                  label: "Perm YTD",
                  cur: entity.cur.perm,
                  prev: entity.prev.perm,
                  bold: false,
                },
                {
                  label: "Temp YTD",
                  cur: entity.cur.temp,
                  prev: entity.prev.temp,
                  bold: false,
                },
                {
                  label: "Total YTD",
                  cur: entity.cur.total,
                  prev: entity.prev.total,
                  bold: true,
                },
              ] as const
            ).map((c, i) => (
              <div
                key={i}
                style={{
                  border: "1px solid #e5e7eb",
                  borderRadius: 6,
                  padding: "10px 12px",
                  background: c.bold ? "#f7f9fc" : "#fff",
                }}
              >
                <div
                  style={{
                    fontSize: 10.5,
                    color: "#6b6c6e",
                    fontWeight: 600,
                    letterSpacing: 0.3,
                    textTransform: "uppercase",
                  }}
                >
                  {c.label}
                </div>
                <div
                  style={{
                    fontSize: 17,
                    fontWeight: 700,
                    color: "#111",
                    fontVariantNumeric: "tabular-nums",
                    marginTop: 2,
                  }}
                >
                  {fmt(c.cur)}
                </div>
                <div style={{ marginTop: 2 }}>
                  <Delta
                    cur={c.cur}
                    prev={c.prev}
                    deltaMode={deltaMode}
                    size="sm"
                  />
                </div>
                <div
                  style={{
                    fontSize: 10.5,
                    color: "#6b6c6e",
                    fontVariantNumeric: "tabular-nums",
                    marginTop: 2,
                  }}
                >
                  prior {fmt(c.prev)}
                </div>
              </div>
            ))}
          </div>

          {/* Sparkline */}
          <div
            style={{
              border: "1px solid #e5e7eb",
              borderRadius: 6,
              padding: "12px 14px",
              marginBottom: 18,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                justifyContent: "space-between",
                marginBottom: 8,
              }}
            >
              <div style={{ fontSize: 12, color: "#003464", fontWeight: 600 }}>
                Monthly revenue
              </div>
              <div
                style={{
                  display: "flex",
                  gap: 12,
                  fontSize: 10.5,
                  color: "#6b6c6e",
                }}
              >
                <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <span
                    style={{
                      width: 14,
                      height: 2,
                      background: "#003464",
                      display: "inline-block",
                    }}
                  />
                  {CURRENT_FY}
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <span
                    style={{
                      width: 14,
                      height: 0,
                      borderTop: "1.5px dashed #c9ccd1",
                      display: "inline-block",
                    }}
                  />
                  {PRIOR_FY}
                </span>
              </div>
            </div>
            <MonthlySparkline
              fy26Monthly={entity.fy26Monthly}
              fy25Monthly={entity.fy25Monthly}
              todayMonthIdx={ytd.monthIdx}
            />
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginTop: 2,
                fontSize: 9.5,
                color: "#6b6c6e",
                letterSpacing: 0.3,
              }}
            >
              {MONTHS.map((m, i) => (
                <span
                  key={m}
                  style={{
                    fontWeight: i === ytd.monthIdx ? 600 : 400,
                    color: i === ytd.monthIdx ? "#003464" : "#6b6c6e",
                  }}
                >
                  {m[0]}
                </span>
              ))}
            </div>
          </div>

          {/* Monthly breakdown table */}
          <div
            style={{
              fontSize: 12,
              color: "#003464",
              fontWeight: 600,
              marginBottom: 8,
            }}
          >
            Monthly breakdown
          </div>
          <table
            style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}
          >
            <thead>
              <tr style={{ background: "#f8f9fb", color: "#003464" }}>
                <th
                  style={{
                    textAlign: "left",
                    padding: "6px 8px",
                    fontWeight: 600,
                    borderBottom: "1px solid #e5e7eb",
                  }}
                >
                  Month
                </th>
                <th
                  style={{
                    textAlign: "right",
                    padding: "6px 8px",
                    fontWeight: 600,
                    borderBottom: "1px solid #e5e7eb",
                  }}
                >
                  Perm
                </th>
                <th
                  style={{
                    textAlign: "right",
                    padding: "6px 8px",
                    fontWeight: 600,
                    borderBottom: "1px solid #e5e7eb",
                  }}
                >
                  Temp
                </th>
                <th
                  style={{
                    textAlign: "right",
                    padding: "6px 8px",
                    fontWeight: 600,
                    borderBottom: "1px solid #e5e7eb",
                    background: "rgba(0,52,100,0.05)",
                  }}
                >
                  Total
                </th>
                <th
                  style={{
                    textAlign: "right",
                    padding: "6px 8px",
                    fontWeight: 600,
                    borderBottom: "1px solid #e5e7eb",
                  }}
                >
                  YoY
                </th>
              </tr>
            </thead>
            <tbody>
              {monthBreakdown.map((m, i) => {
                const inYTD = i < ytd.monthIdx;
                const isCurrent = i === ytd.monthIdx;
                const opacity = inYTD || isCurrent ? 1 : 0.4;
                return (
                  <tr
                    key={i}
                    style={{ borderBottom: "1px solid #f1f3f5", opacity }}
                  >
                    <td
                      style={{
                        padding: "5px 8px",
                        color: "#111",
                        fontWeight: isCurrent ? 600 : 400,
                      }}
                    >
                      {MONTHS[i]}
                      {isCurrent && (
                        <span
                          style={{
                            color: "#F25A57",
                            marginLeft: 4,
                            fontSize: 10,
                          }}
                        >
                          ● thru {ytd.dayOfMonth}
                        </span>
                      )}
                    </td>
                    <td
                      style={{
                        padding: "5px 8px",
                        textAlign: "right",
                        fontVariantNumeric: "tabular-nums",
                      }}
                    >
                      {fmt(m.perm)}
                    </td>
                    <td
                      style={{
                        padding: "5px 8px",
                        textAlign: "right",
                        fontVariantNumeric: "tabular-nums",
                      }}
                    >
                      {fmt(m.temp)}
                    </td>
                    <td
                      style={{
                        padding: "5px 8px",
                        textAlign: "right",
                        fontVariantNumeric: "tabular-nums",
                        fontWeight: 600,
                        background: "rgba(0,52,100,0.04)",
                      }}
                    >
                      {fmt(m.cur)}
                    </td>
                    <td style={{ padding: "5px 8px", textAlign: "right" }}>
                      {inYTD ? (
                        <Delta
                          cur={m.cur}
                          prev={m.prev}
                          deltaMode={deltaMode}
                          size="xs"
                        />
                      ) : (
                        <span style={{ fontSize: 10, color: "#c9ccd1" }}>
                          —
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
              <tr style={{ background: "#f1f3f5", fontWeight: 700 }}>
                <td style={{ padding: "7px 8px", color: "#003464" }}>
                  YTD Total
                </td>
                <td
                  style={{
                    padding: "7px 8px",
                    textAlign: "right",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {fmt(entity.cur.perm)}
                </td>
                <td
                  style={{
                    padding: "7px 8px",
                    textAlign: "right",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {fmt(entity.cur.temp)}
                </td>
                <td
                  style={{
                    padding: "7px 8px",
                    textAlign: "right",
                    fontVariantNumeric: "tabular-nums",
                    color: "#003464",
                    background: "rgba(0,52,100,0.08)",
                  }}
                >
                  {fmt(entity.cur.total)}
                </td>
                <td style={{ padding: "7px 8px", textAlign: "right" }}>
                  <Delta
                    cur={entity.cur.total}
                    prev={entity.prev.total}
                    deltaMode={deltaMode}
                    size="sm"
                  />
                </td>
              </tr>
            </tbody>
          </table>

          {/* Footer note */}
          <div
            style={{
              marginTop: 16,
              padding: "10px 12px",
              background: "#f8f9fb",
              border: "1px solid #e5e7eb",
              borderRadius: 6,
              fontSize: 11.5,
              color: "#6b6c6e",
            }}
          >
            {PRIOR_FY} full-year total:{" "}
            <b style={{ color: "#111", fontVariantNumeric: "tabular-nums" }}>
              {fmt(full25Total)}
            </b>
            {" · "}Currently at{" "}
            <b style={{ color: "#003464", fontVariantNumeric: "tabular-nums" }}>
              {pctOfPrior}%
            </b>{" "}
            of prior year total.
          </div>
        </div>
      </aside>
    </>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LegendsPage() {
  const TODAY_YTD = useMemo(() => getTodayYTD(), []);

  const [curRows, setCurRows] = useState<LegendsMonthRow[]>([]);
  const [prevRows, setPrevRows] = useState<LegendsMonthRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [ytd, setYtd] = useState<YTD>(TODAY_YTD);
  const [deltaMode, setDeltaMode] = useState<DeltaMode>("pct");
  const [viewMode, setViewMode] = useState<ViewMode>("Consultant");
  const [sortKey, setSortKey] = useState<SortKey>("total");
  const [search, setSearch] = useState("");
  const [detailName, setDetailName] = useState<string | null>(null);

  const { allRecruiters, loading: recruiterLoading } = useRecruiterData();
  const lastModified = FC_AUTH.getLastModified();

  useEffect(() => {
    setLoading(true);
    fcFetchLegends(CURRENT_FY)
      .then((data) => {
        setCurRows(data.consultantTypeTotals);
        setPrevRows(data.priorConsultantTypeTotals);
      })
      .catch(() => setError("Failed to load legends data."))
      .finally(() => setLoading(false));
  }, []);

  const rows = useMemo(
    () => buildConsultantData(curRows, prevRows, ytd, allRecruiters),
    [curRows, prevRows, ytd, allRecruiters]
  );

  const numAreas = useMemo(() => new Set(rows.map((r) => r.area)).size, [rows]);
  const dayOfFY = toDayOfFY(ytd.monthIdx, ytd.dayOfMonth);

  const detailEntity = useMemo(
    () => (detailName ? rows.find((r) => r.name === detailName) ?? null : null),
    [detailName, rows]
  );

  const isLoading = loading || recruiterLoading;

  return (
    <div
      className="px-4 sm:px-7 pt-5 pb-8 flex flex-col gap-4 sm:gap-[18px]"
      style={{
        maxWidth: 1240,
        width: "100%",
        margin: "0 auto",
        fontFamily: "'Helvetica Neue', Helvetica, Arial, sans-serif",
      }}
    >
      {/* Header */}
      <div>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: 12,
            flexWrap: "wrap",
          }}
        >
          <h1
            style={{
              fontSize: 22,
              fontWeight: 700,
              color: "#003464",
              margin: 0,
              letterSpacing: -0.2,
            }}
          >
            Legends Table — {CURRENT_FY}
          </h1>
          <span
            style={{
              fontSize: 12,
              color: "#6b6c6e",
              background: "#EEEEEE",
              padding: "2px 8px",
              borderRadius: 10,
              fontWeight: 500,
            }}
          >
            YTD · 1 Jul – {fmtYTD(ytd)} ({dayOfFY}{" "}
            {dayOfFY === 1 ? "day" : "days"})
          </span>
        </div>
        <p
          style={{
            fontSize: 13,
            color: "#6b6c6e",
            marginTop: 4,
            marginBottom: 0,
          }}
        >
          Consultant revenue, split by perm &amp; temp, compared to same elapsed
          period last financial year.
        </p>
        <p
          style={{
            fontSize: 13,
            color: "#6b6c6e",
            marginTop: 4,
            marginBottom: 0,
          }}
        >
          Some numbers may be slightly different to commission reports. Finance
          may apply minor adjustments to some invoices. Recruiters who have left
          the business are not shown.
        </p>
        {lastModified && (
          <p
            style={{
              fontSize: 11,
              color: "#6b6c6e",
              marginTop: 4,
              marginBottom: 0,
            }}
          >
            Data last updated: <b>{lastModified}</b>
          </p>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="w-4 h-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : (
        <>
          <KpiStrip rows={rows} numAreas={numAreas} deltaMode={deltaMode} />

          {/* Controls bar */}
          <div
            style={{
              background: "#fff",
              border: "1px solid #e5e7eb",
              borderRadius: 8,
              padding: "10px 14px",
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              gap: 14,
            }}
          >
            <YTDDatePicker ytd={ytd} setYtd={setYtd} todayYTD={TODAY_YTD} />

            <div
              style={{ width: 1, background: "#e5e7eb", alignSelf: "stretch" }}
            />

            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span
                style={{
                  fontSize: 11,
                  color: "#6b6c6e",
                  fontWeight: 600,
                  letterSpacing: 0.3,
                  textTransform: "uppercase",
                }}
              >
                Compare
              </span>
              <div style={{ display: "flex", gap: 4 }}>
                <TabBtn
                  active={deltaMode === "pct"}
                  onClick={() => setDeltaMode("pct")}
                >
                  %
                </TabBtn>
                <TabBtn
                  active={deltaMode === "dollar"}
                  onClick={() => setDeltaMode("dollar")}
                >
                  $
                </TabBtn>
              </div>
            </div>

            <div
              style={{ width: 1, background: "#e5e7eb", alignSelf: "stretch" }}
            />

            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span
                style={{
                  fontSize: 11,
                  color: "#6b6c6e",
                  fontWeight: 600,
                  letterSpacing: 0.3,
                  textTransform: "uppercase",
                }}
              >
                Group
              </span>
              <div style={{ display: "flex", gap: 4 }}>
                <TabBtn
                  active={viewMode === "Consultant"}
                  onClick={() => setViewMode("Consultant")}
                >
                  Consultant
                </TabBtn>
                <TabBtn
                  active={viewMode === "Area"}
                  onClick={() => setViewMode("Area")}
                >
                  Area
                </TabBtn>
              </div>
            </div>

            <div
              style={{ width: 1, background: "#e5e7eb", alignSelf: "stretch" }}
            />

            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span
                style={{
                  fontSize: 11,
                  color: "#6b6c6e",
                  fontWeight: 600,
                  letterSpacing: 0.3,
                  textTransform: "uppercase",
                }}
              >
                Sort
              </span>
              <div style={{ display: "flex", gap: 4 }}>
                <TabBtn
                  active={sortKey === "total"}
                  onClick={() => setSortKey("total")}
                >
                  Total
                </TabBtn>
                <TabBtn
                  active={sortKey === "yoyAbs"}
                  onClick={() => setSortKey("yoyAbs")}
                >
                  YoY $
                </TabBtn>
                <TabBtn
                  active={sortKey === "yoyPct"}
                  onClick={() => setSortKey("yoyPct")}
                >
                  YoY %
                </TabBtn>
                <TabBtn
                  active={sortKey === "name"}
                  onClick={() => setSortKey("name")}
                >
                  A–Z
                </TabBtn>
              </div>
            </div>

            <div style={{ flex: 1 }} />

            {/* Search */}
            <div
              style={{
                position: "relative",
                flex: 1,
                minWidth: 160,
                maxWidth: 220,
              }}
            >
              <input
                placeholder="Search consultant or area…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{
                  padding: "6px 10px 6px 28px",
                  fontSize: 12,
                  border: "1px solid #e5e7eb",
                  borderRadius: 6,
                  width: "100%",
                  fontFamily: "inherit",
                  outline: "none",
                }}
                onFocus={(e) => {
                  (e.target as HTMLInputElement).style.borderColor = "#003464";
                }}
                onBlur={(e) => {
                  (e.target as HTMLInputElement).style.borderColor = "#e5e7eb";
                }}
              />
              <span
                style={{
                  position: "absolute",
                  left: 9,
                  top: 6,
                  fontSize: 12,
                  color: "#6b6c6e",
                  pointerEvents: "none",
                }}
              >
                ⌕
              </span>
            </div>
          </div>

          <LegendsTable
            rows={rows}
            viewMode={viewMode}
            search={search}
            sortKey={sortKey}
            onOpenDetail={setDetailName}
            deltaMode={deltaMode}
          />

          <div
            style={{
              fontSize: 11,
              color: "#6b6c6e",
              textAlign: "center",
              padding: "4px 0 12px",
            }}
          >
            Comparing <b>{CURRENT_FY}</b> (1 Jul – {fmtYTD(ytd)}) against the
            same elapsed period in {PRIOR_FY}. Click any consultant for monthly
            breakdown. Press{" "}
            <kbd
              style={{
                fontSize: 10,
                background: "#f1f3f5",
                padding: "1px 4px",
                border: "1px solid #e5e7eb",
                borderRadius: 3,
                fontFamily: "monospace",
              }}
            >
              Esc
            </kbd>{" "}
            to close.
          </div>
        </>
      )}

      <Drawer
        open={!!detailEntity}
        onClose={() => setDetailName(null)}
        entity={detailEntity}
        ytd={ytd}
        deltaMode={deltaMode}
      />
    </div>
  );
}
