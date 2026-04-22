// LegendsTable.jsx — improved Legends Table for FutureYou admin
// Depends on window.LEGENDS_DATA (see data.js)

const { useState, useMemo, useEffect, useRef } = React;

// ── Brand palette (from frontend/app/globals.css) ──────────────────────────
const NAVY = "#003464";
const SALMON = "#F25A57";
const DARK_GREY = "#6b6c6e";
const LIGHT_GREY = "#EEEEEE";

// ── Helpers ────────────────────────────────────────────────────────────────
const fmt = (n) => {
  const v = Math.round(n || 0);
  if (!v) return "–";
  return v.toLocaleString("en-AU");
};
const fmtCompact = (n) => {
  const v = Math.round(n || 0);
  if (v === 0) return "0";
  if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(1) + "m";
  if (Math.abs(v) >= 1_000) return (v / 1_000).toFixed(0) + "k";
  return String(v);
};
const pct = (a, b) => {
  if (!b) return a > 0 ? 1 : 0;
  return (a - b) / b;
};
const fmtPct = (p) => {
  if (!isFinite(p)) return "—";
  const v = Math.round(p * 100);
  return (v > 0 ? "+" : "") + v + "%";
};
const fmtDollarDelta = (diff) => {
  const abs = Math.abs(Math.round(diff));
  if (abs === 0) return "0";
  const sign = diff >= 0 ? "+" : "−";
  return sign + "$" + abs.toLocaleString("en-AU");
};
const fmtDollarDeltaCompact = (diff) => {
  const abs = Math.abs(Math.round(diff));
  const sign = diff >= 0 ? "+" : "−";
  return sign + "$" + fmtCompact(abs);
};

// ── Delta component — inline YoY indicator ─────────────────────────────────
// deltaMode: "pct" | "dollar"
function Delta({ cur, prev, deltaMode = "pct", size = "sm" }) {
  if (!prev && !cur) return <span style={{ color: "#c9ccd1" }}>—</span>;
  const diff = cur - prev;
  const p = pct(cur, prev);
  const up = diff >= 0;
  const color = up ? NAVY : SALMON;
  const arrow = up ? "▲" : "▼";
  const text = deltaMode === "pct" ? fmtPct(p) : fmtDollarDeltaCompact(diff);
  const fs = size === "xs" ? 10 : size === "sm" ? 11 : 12;
  return (
    <span style={{ color, fontSize: fs, fontWeight: 600, fontVariantNumeric: "tabular-nums", letterSpacing: 0.2 }}>
      {arrow} {text}
    </span>
  );
}

// ── Monthly sparkline for the drawer ───────────────────────────────────────
function MonthlySparkline({ fy26Monthly, fy25Monthly, data, height = 60 }) {
  const w = 360, pad = 4;
  const months = 12;
  const step = (w - pad * 2) / (months - 1);
  const all = [...fy26Monthly, ...fy25Monthly].map(m => m.perm + m.temp);
  const max = Math.max(1, ...all);

  const todayMonthIdx = window.fromDayOfFY(data.currentDay).monthIdx;

  const path = (arr, clip = 12) => arr.slice(0, clip).map((m, i) => {
    const x = pad + i * step;
    const y = height - pad - ((m.perm + m.temp) / max) * (height - pad * 2);
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  return (
    <svg width={w} height={height} viewBox={`0 0 ${w} ${height}`} style={{ display: "block" }}>
      <rect x={pad} y={0} width={(todayMonthIdx) * step} height={height} fill={NAVY} opacity={0.04} />
      <path d={path(fy25Monthly, 12)} fill="none" stroke="#c9ccd1" strokeWidth={1.5} strokeDasharray="3 2" />
      <path d={path(fy26Monthly, todayMonthIdx + 1)} fill="none" stroke={NAVY} strokeWidth={1.75} />
      {fy26Monthly.slice(0, todayMonthIdx + 1).map((m, i) => {
        const x = pad + i * step;
        const y = height - pad - ((m.perm + m.temp) / max) * (height - pad * 2);
        return <circle key={i} cx={x} cy={y} r={1.75} fill={NAVY} />;
      })}
    </svg>
  );
}

// ── Aggregate per consultant up to a specific day-of-FY ────────────────────
function aggregateYTD(data, dayOfFY) {
  return data.consultants.map((c) => {
    const cur = window.sumDaily(c.fy26Daily, dayOfFY);
    const prev = window.sumDaily(c.fy25Daily, dayOfFY);
    const full25 = window.sumDaily(c.fy25Daily, data.TOTAL_DAYS);
    return { ...c, cur, prev, full25 };
  });
}

function aggregateByArea(consultants) {
  const map = {};
  consultants.forEach((c) => {
    if (!map[c.area]) map[c.area] = { area: c.area, consultants: [], cur: { perm: 0, temp: 0, total: 0 }, prev: { perm: 0, temp: 0, total: 0 } };
    map[c.area].consultants.push(c);
    ["perm", "temp", "total"].forEach(k => {
      map[c.area].cur[k] += c.cur[k];
      map[c.area].prev[k] += c.prev[k];
    });
  });
  return Object.values(map);
}

// ── Tab button ─────────────────────────────────────────────────────────────
function TabBtn({ active, onClick, children, size = "sm" }) {
  const pad = size === "xs" ? "4px 10px" : "6px 12px";
  const fs = size === "xs" ? 12 : 13;
  return (
    <button
      onClick={onClick}
      style={{
        padding: pad, fontSize: fs, fontWeight: 500, borderRadius: 6, border: "none",
        cursor: "pointer", background: active ? NAVY : "#f3f4f6",
        color: active ? "#fff" : DARK_GREY, transition: "background 120ms", fontFamily: "inherit",
      }}
      onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = "#e5e7eb"; }}
      onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = "#f3f4f6"; }}
    >
      {children}
    </button>
  );
}

// ── YTD Date picker ────────────────────────────────────────────────────────
// Lets the user pick day/month for the "YTD through" anchor.
function YTDDatePicker({ dayOfFY, setDayOfFY, data }) {
  const { monthIdx, dayOfMonth } = window.fromDayOfFY(dayOfFY);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const daysInSelectedMonth = data.DAYS_IN_MONTH[monthIdx];

  const pickMonth = (m) => {
    const curDay = Math.min(dayOfMonth, data.DAYS_IN_MONTH[m]);
    setDayOfFY(window.toDayOfFY(m, curDay));
  };
  const pickDay = (d) => setDayOfFY(window.toDayOfFY(monthIdx, d));

  return (
    <div ref={wrapRef} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "6px 12px", fontSize: 12, fontFamily: "inherit",
          background: "#fff", color: "#111", fontWeight: 500,
          border: `1px solid ${open ? NAVY : "#e5e7eb"}`, borderRadius: 6,
          cursor: "pointer", lineHeight: 1,
        }}
      >
        <span style={{ color: DARK_GREY, fontSize: 11, fontWeight: 600, letterSpacing: 0.3, textTransform: "uppercase" }}>YTD through</span>
        <span style={{ color: NAVY, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
          {dayOfMonth} {data.MONTHS[monthIdx]}
        </span>
        <span style={{ color: DARK_GREY, fontSize: 10 }}>▾</span>
      </button>

      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 6px)", left: 0, zIndex: 30,
          background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8,
          boxShadow: "0 8px 24px rgba(0,0,0,0.10)", padding: 12,
          width: 300,
        }}>
          <div style={{ fontSize: 10.5, color: DARK_GREY, fontWeight: 600, letterSpacing: 0.3, textTransform: "uppercase", marginBottom: 6 }}>Month</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 4, marginBottom: 10 }}>
            {data.MONTHS.map((m, i) => (
              <button key={m} onClick={() => pickMonth(i)} style={{
                padding: "6px 0", fontSize: 11, fontFamily: "inherit",
                border: "none", borderRadius: 4, cursor: "pointer",
                background: i === monthIdx ? NAVY : "#f3f4f6",
                color: i === monthIdx ? "#fff" : DARK_GREY,
                fontWeight: 500,
              }}>{m}</button>
            ))}
          </div>
          <div style={{ fontSize: 10.5, color: DARK_GREY, fontWeight: 600, letterSpacing: 0.3, textTransform: "uppercase", marginBottom: 6 }}>Day</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 3 }}>
            {Array.from({ length: daysInSelectedMonth }, (_, i) => i + 1).map(d => (
              <button key={d} onClick={() => { pickDay(d); setOpen(false); }} style={{
                padding: "5px 0", fontSize: 11, fontFamily: "inherit",
                border: "none", borderRadius: 4, cursor: "pointer",
                background: d === dayOfMonth ? NAVY : "transparent",
                color: d === dayOfMonth ? "#fff" : "#111",
                fontWeight: d === dayOfMonth ? 600 : 400,
                fontVariantNumeric: "tabular-nums",
              }}
              onMouseEnter={(e) => { if (d !== dayOfMonth) e.currentTarget.style.background = "#f3f4f6"; }}
              onMouseLeave={(e) => { if (d !== dayOfMonth) e.currentTarget.style.background = "transparent"; }}
              >{d}</button>
            ))}
          </div>
          <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid #f1f3f5", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <button onClick={() => { setDayOfFY(data.TODAY_DAY_OF_FY); setOpen(false); }} style={{
              background: "transparent", border: "none", color: NAVY, fontSize: 11, fontWeight: 600, cursor: "pointer", padding: 0, fontFamily: "inherit",
            }}>Reset to today ({data.TODAY_LABEL})</button>
            <span style={{ fontSize: 10.5, color: DARK_GREY }}>FY Jul 1 – Jun 30</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Page header ────────────────────────────────────────────────────────────
function PageHeader({ data, dayOfFY }) {
  const { monthIdx, dayOfMonth } = window.fromDayOfFY(dayOfFY);
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: NAVY, margin: 0, letterSpacing: -0.2 }}>
          Legends Table — {data.currentFY}
        </h1>
        <span style={{ fontSize: 12, color: DARK_GREY, background: LIGHT_GREY, padding: "2px 8px", borderRadius: 10, fontWeight: 500 }}>
          YTD · 1 Jul – {dayOfMonth} {data.MONTHS[monthIdx]} ({dayOfFY} {dayOfFY === 1 ? "day" : "days"})
        </span>
      </div>
      <p style={{ fontSize: 13, color: DARK_GREY, marginTop: 4, marginBottom: 0 }}>
        Consultant revenue, split by perm & temp, compared to same elapsed period last financial year.
      </p>
      <p style={{ fontSize: 11, color: DARK_GREY, marginTop: 4, marginBottom: 0 }}>
        Data last updated: <b>{data.lastUpdated}</b>
      </p>
    </div>
  );
}

// ── KPI strip ──────────────────────────────────────────────────────────────
function KpiStrip({ rows, data, deltaMode }) {
  const totals = rows.reduce((acc, r) => {
    acc.cur.perm += r.cur.perm; acc.cur.temp += r.cur.temp; acc.cur.total += r.cur.total;
    acc.prev.perm += r.prev.perm; acc.prev.temp += r.prev.temp; acc.prev.total += r.prev.total;
    return acc;
  }, { cur: { perm: 0, temp: 0, total: 0 }, prev: { perm: 0, temp: 0, total: 0 } });

  const cards = [
    { label: "Total revenue YTD", cur: totals.cur.total, prev: totals.prev.total, accent: NAVY },
    { label: "Perm YTD",          cur: totals.cur.perm,  prev: totals.prev.perm },
    { label: "Temp YTD",          cur: totals.cur.temp,  prev: totals.prev.temp },
    { label: "Active consultants", cur: rows.length,     prev: rows.length, hideDelta: true },
  ];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
      {cards.map((c, i) => (
        <div key={i} style={{
          background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8,
          padding: "12px 14px",
          borderTop: c.accent ? `2px solid ${c.accent}` : "1px solid #e5e7eb",
        }}>
          <div style={{ fontSize: 11, color: DARK_GREY, fontWeight: 500, letterSpacing: 0.3, textTransform: "uppercase" }}>{c.label}</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4 }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: "#111", fontVariantNumeric: "tabular-nums" }}>
              {c.hideDelta ? c.cur : fmt(c.cur)}
            </div>
            {!c.hideDelta && <Delta cur={c.cur} prev={c.prev} deltaMode={deltaMode} size="md" />}
          </div>
          {!c.hideDelta && (
            <div style={{ fontSize: 11, color: DARK_GREY, marginTop: 2, fontVariantNumeric: "tabular-nums" }}>
              prior YTD {fmt(c.prev)}
            </div>
          )}
          {c.hideDelta && (
            <div style={{ fontSize: 11, color: DARK_GREY, marginTop: 2 }}>
              across {new Set(data.consultants.map(x => x.area)).size} areas
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Movers strip ───────────────────────────────────────────────────────────
function Movers({ rows, onPick, deltaMode }) {
  const withDelta = rows
    .filter(r => r.prev.total > 1000)
    .map(r => ({ ...r, deltaPct: pct(r.cur.total, r.prev.total), deltaAbs: r.cur.total - r.prev.total }));
  const up = [...withDelta].sort((a, b) => b.deltaAbs - a.deltaAbs).slice(0, 3);
  const down = [...withDelta].sort((a, b) => a.deltaAbs - b.deltaAbs).slice(0, 3);

  const Card = ({ title, color, arrow, items }) => (
    <div style={{
      flex: 1, background: "#fff", border: "1px solid #e5e7eb",
      borderLeft: `3px solid ${color}`, borderRadius: 8, padding: "10px 14px",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
        <span style={{ color, fontSize: 12, fontWeight: 700 }}>{arrow}</span>
        <span style={{ fontSize: 11, fontWeight: 600, color: DARK_GREY, letterSpacing: 0.4, textTransform: "uppercase" }}>{title}</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {items.map((r, i) => {
          const deltaText = deltaMode === "pct"
            ? fmtPct(r.deltaPct)
            : fmtDollarDeltaCompact(r.deltaAbs);
          return (
            <button key={r.id} onClick={() => onPick(r)}
              style={{
                display: "grid", gridTemplateColumns: "14px 1fr auto auto", alignItems: "center", gap: 8,
                background: "transparent", border: "none", padding: "3px 0", cursor: "pointer",
                textAlign: "left", borderRadius: 4, fontFamily: "inherit",
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = "#f8f9fb"}
              onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
            >
              <span style={{ fontSize: 10, color: DARK_GREY, fontVariantNumeric: "tabular-nums" }}>{i + 1}.</span>
              <span style={{ fontSize: 13, color: "#111", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.name}</span>
              <span style={{ fontSize: 11, color: DARK_GREY, fontVariantNumeric: "tabular-nums" }}>{fmtCompact(r.cur.total)}</span>
              <span style={{ color, fontSize: 11, fontWeight: 600, fontVariantNumeric: "tabular-nums", minWidth: 60, textAlign: "right" }}>
                {deltaText}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );

  return (
    <div style={{ display: "flex", gap: 12 }}>
      <Card title="Biggest gainers YoY" color={NAVY} arrow="▲" items={up} />
      <Card title="Biggest drops YoY"   color={SALMON} arrow="▼" items={down} />
    </div>
  );
}

// ── Data cell: number + delta stacked ──────────────────────────────────────
function DataCell({ cur, prev, compareOn, density, deltaMode }) {
  const rowFs = density === "compact" ? 12.5 : 13.5;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: density === "compact" ? 1 : 2, paddingRight: 18, paddingLeft: 18 }}>
      <span style={{ fontSize: rowFs, color: "#111", fontVariantNumeric: "tabular-nums", fontWeight: 500 }}>{fmt(cur)}</span>
      {compareOn && <Delta cur={cur} prev={prev} deltaMode={deltaMode} size="xs" />}
    </div>
  );
}

// ── Drawer ─────────────────────────────────────────────────────────────────
function Drawer({ open, onClose, entity, data, deltaMode, dayOfFY }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!entity) return null;
  const fullPrevTotal = window.sumDaily(entity.fy25Daily || [], data.TOTAL_DAYS).total;

  const monthTotals = (entity.fy26Monthly || []).map((m, i) => {
    const cur = m.perm + m.temp;
    const prev = entity.fy25Monthly[i].perm + entity.fy25Monthly[i].temp;
    return { cur, prev, perm: m.perm, temp: m.temp, prevPerm: entity.fy25Monthly[i].perm, prevTemp: entity.fy25Monthly[i].temp };
  });

  const { monthIdx: todayMonthIdx, dayOfMonth: todayDayOfMonth } = window.fromDayOfFY(dayOfFY);

  return (
    <>
      <div onClick={onClose} style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.3)",
        opacity: open ? 1 : 0, pointerEvents: open ? "auto" : "none",
        transition: "opacity 200ms", zIndex: 40,
      }} />
      <aside style={{
        position: "fixed", top: 0, right: 0, bottom: 0, width: 520, maxWidth: "92vw",
        background: "#fff", boxShadow: "-8px 0 28px rgba(0,0,0,0.12)",
        transform: open ? "translateX(0)" : "translateX(100%)",
        transition: "transform 220ms cubic-bezier(.4,.0,.2,1)",
        zIndex: 50, display: "flex", flexDirection: "column",
      }}>
        <div style={{ padding: "16px 20px", borderBottom: "1px solid #e5e7eb", display: "flex", alignItems: "start", gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: DARK_GREY, fontWeight: 600, letterSpacing: 0.4, textTransform: "uppercase" }}>Consultant</div>
            <h2 style={{ fontSize: 20, fontWeight: 700, color: NAVY, margin: "2px 0 0" }}>{entity.name}</h2>
            <div style={{ fontSize: 12, color: DARK_GREY, marginTop: 2 }}>{entity.area}</div>
          </div>
          <button onClick={onClose} style={{
            background: "transparent", border: "1px solid #e5e7eb", borderRadius: 6, padding: "4px 8px",
            fontSize: 12, color: DARK_GREY, cursor: "pointer", fontFamily: "inherit",
          }}>Esc</button>
        </div>

        <div style={{ flex: 1, overflow: "auto", padding: "16px 20px" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 18 }}>
            {[
              { label: "Perm YTD",  cur: entity.cur.perm,  prev: entity.prev.perm },
              { label: "Temp YTD",  cur: entity.cur.temp,  prev: entity.prev.temp },
              { label: "Total YTD", cur: entity.cur.total, prev: entity.prev.total, bold: true },
            ].map((c, i) => (
              <div key={i} style={{
                border: "1px solid #e5e7eb", borderRadius: 6, padding: "10px 12px",
                background: c.bold ? "#f7f9fc" : "#fff",
              }}>
                <div style={{ fontSize: 10.5, color: DARK_GREY, fontWeight: 600, letterSpacing: 0.3, textTransform: "uppercase" }}>{c.label}</div>
                <div style={{ fontSize: 17, fontWeight: 700, color: "#111", fontVariantNumeric: "tabular-nums", marginTop: 2 }}>{fmt(c.cur)}</div>
                <div style={{ marginTop: 2 }}><Delta cur={c.cur} prev={c.prev} deltaMode={deltaMode} size="sm" /></div>
                <div style={{ fontSize: 10.5, color: DARK_GREY, fontVariantNumeric: "tabular-nums", marginTop: 2 }}>prior {fmt(c.prev)}</div>
              </div>
            ))}
          </div>

          <div style={{ border: "1px solid #e5e7eb", borderRadius: 6, padding: "12px 14px", marginBottom: 18 }}>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 8 }}>
              <div style={{ fontSize: 12, color: NAVY, fontWeight: 600 }}>Monthly revenue</div>
              <div style={{ display: "flex", gap: 12, fontSize: 10.5, color: DARK_GREY }}>
                <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <span style={{ width: 14, height: 2, background: NAVY, display: "inline-block" }} />FY26
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <span style={{ width: 14, height: 0, borderTop: "1.5px dashed #c9ccd1", display: "inline-block" }} />FY25
                </span>
              </div>
            </div>
            <MonthlySparkline fy26Monthly={entity.fy26Monthly} fy25Monthly={entity.fy25Monthly} data={{ ...data, currentDay: dayOfFY }} />
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 2, fontSize: 9.5, color: DARK_GREY, letterSpacing: 0.3 }}>
              {data.MONTHS.map((m, i) => (
                <span key={m} style={{ fontWeight: i === todayMonthIdx ? 600 : 400, color: i === todayMonthIdx ? NAVY : DARK_GREY }}>{m[0]}</span>
              ))}
            </div>
          </div>

          <div style={{ fontSize: 12, color: NAVY, fontWeight: 600, marginBottom: 8 }}>Monthly breakdown</div>
          <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "#f8f9fb", color: NAVY }}>
                <th style={{ textAlign: "left", padding: "6px 8px", fontWeight: 600, borderBottom: "1px solid #e5e7eb" }}>Month</th>
                <th style={{ textAlign: "right", padding: "6px 8px", fontWeight: 600, borderBottom: "1px solid #e5e7eb" }}>Perm</th>
                <th style={{ textAlign: "right", padding: "6px 8px", fontWeight: 600, borderBottom: "1px solid #e5e7eb" }}>Temp</th>
                <th style={{ textAlign: "right", padding: "6px 8px", fontWeight: 600, borderBottom: "1px solid #e5e7eb", background: "rgba(0,52,100,0.05)" }}>Total</th>
                <th style={{ textAlign: "right", padding: "6px 8px", fontWeight: 600, borderBottom: "1px solid #e5e7eb" }}>YoY</th>
              </tr>
            </thead>
            <tbody>
              {monthTotals.map((m, i) => {
                const inYTD = i < todayMonthIdx;
                const isCurrent = i === todayMonthIdx;
                const op = (inYTD || isCurrent) ? 1 : 0.4;
                return (
                  <tr key={i} style={{ borderBottom: "1px solid #f1f3f5", opacity: op }}>
                    <td style={{ padding: "5px 8px", color: "#111", fontWeight: isCurrent ? 600 : 400 }}>
                      {data.MONTHS[i]}{isCurrent && <span style={{ color: SALMON, marginLeft: 4, fontSize: 10 }}>● thru {todayDayOfMonth}</span>}
                    </td>
                    <td style={{ padding: "5px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{fmt(m.perm)}</td>
                    <td style={{ padding: "5px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{fmt(m.temp)}</td>
                    <td style={{ padding: "5px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums", fontWeight: 600, background: "rgba(0,52,100,0.04)" }}>{fmt(m.cur)}</td>
                    <td style={{ padding: "5px 8px", textAlign: "right" }}>
                      {inYTD ? <Delta cur={m.cur} prev={m.prev} deltaMode={deltaMode} size="xs" /> : <span style={{ fontSize: 10, color: "#c9ccd1" }}>—</span>}
                    </td>
                  </tr>
                );
              })}
              <tr style={{ background: "#f1f3f5", fontWeight: 700 }}>
                <td style={{ padding: "7px 8px", color: NAVY }}>YTD Total</td>
                <td style={{ padding: "7px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{fmt(entity.cur.perm)}</td>
                <td style={{ padding: "7px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{fmt(entity.cur.temp)}</td>
                <td style={{ padding: "7px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums", color: NAVY, background: "rgba(0,52,100,0.08)" }}>{fmt(entity.cur.total)}</td>
                <td style={{ padding: "7px 8px", textAlign: "right" }}><Delta cur={entity.cur.total} prev={entity.prev.total} deltaMode={deltaMode} size="sm" /></td>
              </tr>
            </tbody>
          </table>

          <div style={{ marginTop: 16, padding: "10px 12px", background: "#f8f9fb", border: "1px solid #e5e7eb", borderRadius: 6, fontSize: 11.5, color: DARK_GREY }}>
            FY25 full-year total: <b style={{ color: "#111", fontVariantNumeric: "tabular-nums" }}>{fmt(fullPrevTotal)}</b>
            {" · "}Currently at <b style={{ color: NAVY, fontVariantNumeric: "tabular-nums" }}>{Math.round((entity.cur.total / fullPrevTotal) * 100)}%</b> of prior year total.
          </div>
        </div>
      </aside>
    </>
  );
}

// ── Main table ─────────────────────────────────────────────────────────────
function LegendsTable({ data, compareOn, viewMode, search, density, onOpenDetail, sortKey, dayOfFY, deltaMode }) {
  const all = useMemo(() => aggregateYTD(data, dayOfFY), [data, dayOfFY]);
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return all;
    return all.filter(c => c.name.toLowerCase().includes(q) || c.area.toLowerCase().includes(q));
  }, [all, search]);

  const [expanded, setExpanded] = useState({});

  const sortFn = (a, b) => {
    if (sortKey === "name") return a.name.localeCompare(b.name);
    if (sortKey === "yoyAbs") return (b.cur.total - b.prev.total) - (a.cur.total - a.prev.total);
    if (sortKey === "yoyPct") return pct(b.cur.total, b.prev.total) - pct(a.cur.total, a.prev.total);
    return b.cur.total - a.cur.total;
  };

  const rowPad = density === "compact" ? "6px 14px" : "10px 14px";

  let rowList;
  if (viewMode === "Consultant") {
    rowList = [...filtered].sort(sortFn).map(c => ({ kind: "consultant", entity: c }));
  } else {
    const areas = aggregateByArea(filtered);
    const sortedAreas = [...areas].sort((a, b) => {
      if (sortKey === "name") return a.area.localeCompare(b.area);
      if (sortKey === "yoyAbs") return (b.cur.total - b.prev.total) - (a.cur.total - a.prev.total);
      if (sortKey === "yoyPct") return pct(b.cur.total, b.prev.total) - pct(a.cur.total, a.prev.total);
      return b.cur.total - a.cur.total;
    });
    rowList = [];
    sortedAreas.forEach(a => {
      rowList.push({ kind: "area", entity: a });
      if (expanded[a.area]) {
        [...a.consultants].sort(sortFn).forEach(c => rowList.push({ kind: "consultantChild", entity: c, parent: a.area }));
      }
    });
  }

  const totals = filtered.reduce((acc, r) => {
    acc.cur.perm += r.cur.perm; acc.cur.temp += r.cur.temp; acc.cur.total += r.cur.total;
    acc.prev.perm += r.prev.perm; acc.prev.temp += r.prev.temp; acc.prev.total += r.prev.total;
    return acc;
  }, { cur: { perm: 0, temp: 0, total: 0 }, prev: { perm: 0, temp: 0, total: 0 } });

  // Columns — Name / Perm / Temp / Total (no VS LY bar anymore)
  const nameCol = viewMode === "Area" ? "minmax(220px, 1.3fr)" : "minmax(200px, 1fr)";
  const gridCols = `${nameCol} 1fr 1fr 1.1fr`;

  return (
    <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, overflow: "hidden" }}>
      <div style={{
        display: "grid", gridTemplateColumns: gridCols, padding: "8px 14px",
        background: "#f8f9fb", borderBottom: "1px solid #e5e7eb",
        fontSize: 11, fontWeight: 600, color: NAVY, letterSpacing: 0.3, textTransform: "uppercase",
      }}>
        <div>{viewMode === "Consultant" ? "Consultant" : "Area"}</div>
        <div style={{ textAlign: "right", paddingRight: 18, paddingLeft: 18 }}>Perm YTD</div>
        <div style={{ textAlign: "right", paddingRight: 18, paddingLeft: 18 }}>Temp YTD</div>
        <div style={{ textAlign: "right", background: "rgba(0,52,100,0.04)", marginRight: -14, paddingRight: 22, paddingLeft: 18, marginTop: -8, paddingTop: 8, marginBottom: -8, paddingBottom: 8, borderLeft: "2px solid #e5e7eb" }}>Total YTD</div>
      </div>

      {rowList.length === 0 && (
        <div style={{ padding: "24px 14px", textAlign: "center", fontSize: 13, color: DARK_GREY }}>
          No results for "{search}".
        </div>
      )}

      {rowList.map((r, i) => {
        const isArea = r.kind === "area";
        const isChild = r.kind === "consultantChild";
        const e = r.entity;
        const isExpanded = isArea && expanded[e.area];
        return (
          <div key={(isArea ? "A:" : isChild ? "CC:" + r.parent + ":" : "C:") + (e.id || e.area)}
            onClick={() => {
              if (isArea) setExpanded(prev => ({ ...prev, [e.area]: !prev[e.area] }));
              else onOpenDetail(e);
            }}
            style={{
              display: "grid", gridTemplateColumns: gridCols,
              padding: rowPad, paddingLeft: isChild ? 34 : 14,
              borderBottom: "1px solid #f1f3f5",
              background: isArea ? "#fbfcfd" : (i % 2 === 0 ? "#fff" : "#fcfcfd"),
              fontWeight: isArea ? 600 : 400, cursor: "pointer", alignItems: "center",
              transition: "background 100ms",
            }}
            onMouseEnter={(el) => el.currentTarget.style.background = isArea ? "#f3f6f9" : "#f7f9fb"}
            onMouseLeave={(el) => el.currentTarget.style.background = isArea ? "#fbfcfd" : (i % 2 === 0 ? "#fff" : "#fcfcfd")}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, overflow: "hidden" }}>
              {isArea && (
                <span style={{
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  width: 16, height: 16, color: NAVY, fontSize: 10,
                  transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
                  transition: "transform 140ms",
                }}>▶</span>
              )}
              <div style={{ overflow: "hidden" }}>
                <div style={{ fontSize: density === "compact" ? 13 : 13.5, color: isArea ? NAVY : "#111", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {isArea ? e.area : e.name}
                </div>
                {!isArea && !isChild && density !== "compact" && (
                  <div style={{ fontSize: 11, color: DARK_GREY, marginTop: 1 }}>{e.area}</div>
                )}
                {isArea && density !== "compact" && (
                  <div style={{ fontSize: 11, color: DARK_GREY, marginTop: 1 }}>
                    {e.consultants.length} {e.consultants.length === 1 ? "consultant" : "consultants"}
                  </div>
                )}
              </div>
            </div>

            <DataCell cur={e.cur.perm} prev={e.prev.perm} compareOn={compareOn} density={density} deltaMode={deltaMode} />
            <DataCell cur={e.cur.temp} prev={e.prev.temp} compareOn={compareOn} density={density} deltaMode={deltaMode} />

            <div style={{
              background: "rgba(0,52,100,0.04)",
              marginRight: -14, paddingRight: 22, paddingLeft: 18,
              marginTop: density === "compact" ? -6 : -10, paddingTop: density === "compact" ? 6 : 10,
              marginBottom: density === "compact" ? -6 : -10, paddingBottom: density === "compact" ? 6 : 10,
              borderLeft: "2px solid #e5e7eb",
              display: "flex", flexDirection: "column", alignItems: "flex-end", gap: density === "compact" ? 1 : 2,
            }}>
              <span style={{ fontSize: density === "compact" ? 13 : 14, color: NAVY, fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>{fmt(e.cur.total)}</span>
              {compareOn && <Delta cur={e.cur.total} prev={e.prev.total} deltaMode={deltaMode} size="xs" />}
            </div>
          </div>
        );
      })}

      <div style={{
        display: "grid", gridTemplateColumns: gridCols, padding: "10px 14px",
        background: "#f1f3f5", borderTop: "2px solid #e5e7eb", fontWeight: 700, alignItems: "center",
      }}>
        <div style={{ color: NAVY, fontSize: 13 }}>Total</div>
        <DataCell cur={totals.cur.perm} prev={totals.prev.perm} compareOn={compareOn} density={density} deltaMode={deltaMode} />
        <DataCell cur={totals.cur.temp} prev={totals.prev.temp} compareOn={compareOn} density={density} deltaMode={deltaMode} />
        <div style={{
          background: "rgba(0,52,100,0.09)",
          marginRight: -14, paddingRight: 22, paddingLeft: 18,
          marginTop: -10, paddingTop: 10, marginBottom: -10, paddingBottom: 10,
          borderLeft: "2px solid #e5e7eb",
          display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2,
        }}>
          <span style={{ fontSize: 14.5, color: NAVY, fontWeight: 800, fontVariantNumeric: "tabular-nums" }}>{fmt(totals.cur.total)}</span>
          {compareOn && <Delta cur={totals.cur.total} prev={totals.prev.total} deltaMode={deltaMode} size="sm" />}
        </div>
      </div>
    </div>
  );
}

// ── Tweaks panel ───────────────────────────────────────────────────────────
function TweaksPanel({ visible, density, setDensity }) {
  if (!visible) return null;
  return (
    <div style={{
      position: "fixed", bottom: 20, right: 20, zIndex: 60,
      background: "#fff", border: "1px solid #e5e7eb", borderRadius: 10,
      boxShadow: "0 10px 30px rgba(0,0,0,0.12)",
      padding: 14, width: 240, fontFamily: "inherit",
    }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: NAVY, letterSpacing: 0.4, textTransform: "uppercase", marginBottom: 10 }}>Tweaks</div>
      <div>
        <div style={{ fontSize: 11, color: DARK_GREY, fontWeight: 500, marginBottom: 4 }}>Density</div>
        <div style={{ display: "flex", gap: 4 }}>
          <TabBtn active={density === "compact"} onClick={() => setDensity("compact")} size="xs">Compact</TabBtn>
          <TabBtn active={density === "comfortable"} onClick={() => setDensity("comfortable")} size="xs">Comfortable</TabBtn>
        </div>
      </div>
    </div>
  );
}

// ── Top bar ────────────────────────────────────────────────────────────────
function TopBar() {
  const NAV = [
    { label: "Forecasts",          active: false },
    { label: "Revenue Dashboard",  active: false },
    { label: "Admin Panel",        active: false },
    { label: "Legends Table",      active: true },
  ];
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "10px 32px", borderBottom: "1px solid #e5e7eb", background: "#fff", flexShrink: 0,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
          <span style={{ fontWeight: 700, color: NAVY }}>Leo Oshi</span>
          <span style={{ fontSize: 10, background: "rgba(242,90,87,0.1)", color: SALMON, fontWeight: 700, padding: "1px 8px", borderRadius: 10 }}>Admin</span>
        </div>
        <nav style={{ display: "flex", alignItems: "center", gap: 2, borderLeft: "1px solid #e5e7eb", paddingLeft: 20 }}>
          {NAV.map((n) => (
            <a key={n.label} href="#" style={{
              padding: "6px 12px", fontSize: 12, fontWeight: 500, borderRadius: 6, textDecoration: "none",
              color: n.active ? "#fff" : DARK_GREY,
              background: n.active ? NAVY : "transparent",
            }}>{n.label}</a>
          ))}
        </nav>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 12, color: DARK_GREY }}>
        <span>Data updated: <b style={{ color: "#111" }}>{window.LEGENDS_DATA.lastUpdated}</b></span>
        <button style={{ background: "transparent", border: "none", color: DARK_GREY, fontSize: 12, cursor: "pointer", padding: "6px 10px" }}>Change password</button>
        <button style={{ background: "transparent", border: "none", color: DARK_GREY, fontSize: 12, cursor: "pointer", padding: "6px 10px" }}>Sign out</button>
      </div>
    </div>
  );
}

// ── Main App ───────────────────────────────────────────────────────────────
function LegendsApp({ tweaks }) {
  const data = window.LEGENDS_DATA;
  const [compareOn, setCompareOn] = useState(true);
  const [viewMode, setViewMode]   = useState("Consultant");
  const [search, setSearch]       = useState("");
  const [sortKey, setSortKey]     = useState("total");
  const [detail, setDetail]       = useState(null);
  const [dayOfFY, setDayOfFY]     = useState(data.TODAY_DAY_OF_FY);
  const [deltaMode, setDeltaMode] = useState("pct"); // "pct" | "dollar"
  const density = tweaks.density;

  const rows = useMemo(() => aggregateYTD(data, dayOfFY), [data, dayOfFY]);

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh", background: LIGHT_GREY, fontFamily: "'Helvetica Neue', Helvetica, Arial, sans-serif", color: "#111" }}>
      <TopBar />
      <div style={{ padding: "20px 28px 32px", display: "flex", flexDirection: "column", gap: 18, maxWidth: 1240, width: "100%", margin: "0 auto" }}>
        <PageHeader data={data} dayOfFY={dayOfFY} />

        <KpiStrip rows={rows} data={data} deltaMode={deltaMode} />

        <Movers rows={rows} onPick={(r) => setDetail(r)} deltaMode={deltaMode} />

        {/* Controls */}
        <div style={{
          background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8,
          padding: "10px 14px", display: "flex", flexWrap: "wrap", alignItems: "center", gap: 14,
        }}>
          <YTDDatePicker dayOfFY={dayOfFY} setDayOfFY={setDayOfFY} data={data} />

          <div style={{ width: 1, background: "#e5e7eb", alignSelf: "stretch" }} />

          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 11, color: DARK_GREY, fontWeight: 600, letterSpacing: 0.3, textTransform: "uppercase" }}>Compare</span>
            <div style={{ display: "flex", gap: 4 }}>
              <TabBtn active={deltaMode === "pct"} onClick={() => setDeltaMode("pct")}>%</TabBtn>
              <TabBtn active={deltaMode === "dollar"} onClick={() => setDeltaMode("dollar")}>$</TabBtn>
            </div>
          </div>

          <div style={{ width: 1, background: "#e5e7eb", alignSelf: "stretch" }} />

          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 11, color: DARK_GREY, fontWeight: 600, letterSpacing: 0.3, textTransform: "uppercase" }}>Group</span>
            <div style={{ display: "flex", gap: 4 }}>
              <TabBtn active={viewMode === "Consultant"} onClick={() => setViewMode("Consultant")}>Consultant</TabBtn>
              <TabBtn active={viewMode === "Area"} onClick={() => setViewMode("Area")}>Area</TabBtn>
            </div>
          </div>

          <div style={{ width: 1, background: "#e5e7eb", alignSelf: "stretch" }} />

          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 11, color: DARK_GREY, fontWeight: 600, letterSpacing: 0.3, textTransform: "uppercase" }}>Sort</span>
            <div style={{ display: "flex", gap: 4 }}>
              <TabBtn active={sortKey === "total"} onClick={() => setSortKey("total")}>Total</TabBtn>
              <TabBtn active={sortKey === "yoyAbs"} onClick={() => setSortKey("yoyAbs")}>YoY $</TabBtn>
              <TabBtn active={sortKey === "yoyPct"} onClick={() => setSortKey("yoyPct")}>YoY %</TabBtn>
              <TabBtn active={sortKey === "name"} onClick={() => setSortKey("name")}>A–Z</TabBtn>
            </div>
          </div>

          <div style={{ flex: 1 }} />

          <div style={{ position: "relative" }}>
            <input
              placeholder="Search consultant or area…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                padding: "6px 10px 6px 28px", fontSize: 12,
                border: "1px solid #e5e7eb", borderRadius: 6, width: 220,
                fontFamily: "inherit", outline: "none",
              }}
              onFocus={(e) => e.target.style.borderColor = NAVY}
              onBlur={(e) => e.target.style.borderColor = "#e5e7eb"}
            />
            <span style={{ position: "absolute", left: 9, top: 6, fontSize: 12, color: DARK_GREY }}>⌕</span>
          </div>
        </div>

        <LegendsTable
          data={data}
          compareOn={compareOn}
          viewMode={viewMode}
          search={search}
          density={density}
          sortKey={sortKey}
          onOpenDetail={setDetail}
          dayOfFY={dayOfFY}
          deltaMode={deltaMode}
        />

        <div style={{ fontSize: 11, color: DARK_GREY, textAlign: "center", padding: "4px 0 12px" }}>
          Comparing <b>{data.currentFY}</b> (1 Jul – {window.fmtDayOfFY(dayOfFY)}) against the same elapsed period in {data.priorFY}.
          Click any consultant for monthly breakdown. Press <kbd style={{ fontSize: 10, background: "#f1f3f5", padding: "1px 4px", border: "1px solid #e5e7eb", borderRadius: 3, fontFamily: "monospace" }}>Esc</kbd> to close.
        </div>
      </div>

      <Drawer open={!!detail} onClose={() => setDetail(null)} entity={detail} data={data} deltaMode={deltaMode} dayOfFY={dayOfFY} />
    </div>
  );
}

window.LegendsApp = LegendsApp;
window.TweaksPanel = TweaksPanel;
