// Mock FY26 / FY25 legends data for the prototype (daily granularity).
// FY = Jul 1 → Jun 30. We simulate today = 15 Apr 2026 (FY26, ~9.5 months in).

window.LEGENDS_DATA = (() => {
  const MONTHS = ["Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar","Apr","May","Jun"];
  // Days in each FY month (Jul..Jun). FY26 Feb has 28 days (2026 not leap); FY25 Feb had 29 (2025? no, 2024 had 29 -> FY25 Feb=Feb 2025=28).
  // Keep it simple: assume 28 Feb for both years.
  const DAYS_IN_MONTH = [31,31,30,31,30,31,31,28,31,30,31,30]; // Jul..Jun
  const CUM_DAYS = DAYS_IN_MONTH.reduce((a, d, i) => { a.push((a[i-1] || 0) + d); return a; }, []);
  const TOTAL_DAYS = CUM_DAYS[11]; // 365

  // "Today" = 15 Apr 2026 in FY26 terms. Apr is index 9.
  // Days into FY through end of Mar = Jul(31)+Aug(31)+Sep(30)+Oct(31)+Nov(30)+Dec(31)+Jan(31)+Feb(28)+Mar(31) = 274
  // + 15 Apr days = 289 (day-of-FY, 1-indexed).
  const TODAY_DAY_OF_FY = 31+31+30+31+30+31+31+28+31 + 15; // 289

  // seeded rand so numbers are stable
  let seed = 42;
  const rand = () => {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  };

  const AREAS = [
    { name: "Accounting & Finance", focus: "mix" },
    { name: "Technology", focus: "mix" },
    { name: "Sales & Marketing", focus: "perm" },
    { name: "Legal", focus: "perm" },
    { name: "HR & Operations", focus: "mix" },
    { name: "Supply Chain", focus: "temp" },
  ];

  const NAMES = [
    ["Harper", "Alessandro"], ["Olivia", "Chen"], ["James", "O'Sullivan"], ["Priya", "Nair"],
    ["Noah", "Whitfield"], ["Mia", "Kowalski"], ["Ethan", "Rasmussen"], ["Charlotte", "Beaumont"],
    ["Lucas", "Ferraro"], ["Amelia", "Tanaka"], ["Henry", "Oyelaran"], ["Isla", "Petersen"],
    ["William", "Nguyen"], ["Ava", "Blackwood"], ["Oscar", "Lindqvist"], ["Sophia", "Hartley"],
    ["Leo", "Andrikidis"], ["Grace", "Mukherjee"], ["Jack", "Ferreira"], ["Ruby", "Caldwell"],
    ["Max", "Volkov"], ["Evie", "Rangel"], ["Theo", "Sutherland"], ["Maya", "Okonkwo"],
  ];

  const consultants = NAMES.map(([f, l], i) => {
    const area = AREAS[i % AREAS.length];
    return { name: `${f} ${l}`, area: area.name, focus: area.focus, id: `c${i}` };
  });

  // Simulate monthly totals (as before) then spread evenly across days within the month
  // to get daily {perm, temp} series. We also add light per-day noise.
  function buildMonths(baseMonthly, focus, yoyBias) {
    const permWeight = focus === "perm" ? 0.8 : focus === "temp" ? 0.2 : 0.5 + (rand() - 0.5) * 0.3;
    return MONTHS.map((_, m) => {
      const seasonal = [1.0, 1.05, 1.1, 1.05, 1.0, 0.75, 0.8, 1.05, 1.15, 1.2, 1.1, 0.95][m];
      const noise = 0.7 + rand() * 0.6;
      const monthly = baseMonthly * seasonal * noise * (1 + yoyBias);
      const perm = monthly * permWeight;
      const temp = monthly * (1 - permWeight);
      return { perm, temp };
    });
  }

  // Spread a month total across its days with mild per-day variance.
  function spreadMonthDaily(monthEntry, days) {
    // weekday-ish variance: day 0..n with noise
    const weights = [];
    let sum = 0;
    for (let d = 0; d < days; d++) {
      const w = 0.6 + rand() * 0.8; // 0.6..1.4
      weights.push(w); sum += w;
    }
    return weights.map(w => ({
      perm: monthEntry.perm * (w / sum),
      temp: monthEntry.temp * (w / sum),
    }));
  }

  const consultantsFull = consultants.map((c) => {
    const base = 8000 + rand() * 22000;
    const yoyBias = (rand() - 0.45) * 0.5;
    const fy25Months = buildMonths(base, c.focus, 0);
    const fy26Months = buildMonths(base, c.focus, yoyBias);

    // Daily arrays of length TOTAL_DAYS (365). Index 0 = Jul 1, index 364 = Jun 30.
    const fy25Daily = [];
    const fy26Daily = [];
    for (let m = 0; m < 12; m++) {
      const d25 = spreadMonthDaily(fy25Months[m], DAYS_IN_MONTH[m]);
      const d26 = spreadMonthDaily(fy26Months[m], DAYS_IN_MONTH[m]);
      fy25Daily.push(...d25);
      fy26Daily.push(...d26);
    }

    return { ...c, fy25Monthly: fy25Months, fy26Monthly: fy26Months, fy25Daily, fy26Daily, yoyBias };
  });

  return {
    MONTHS,
    DAYS_IN_MONTH,
    CUM_DAYS,
    TOTAL_DAYS,
    TODAY_DAY_OF_FY,       // 1..365
    TODAY_LABEL: "15 Apr 2026",
    AREAS: AREAS.map(a => a.name),
    consultants: consultantsFull,
    currentFY: "FY26",
    priorFY: "FY25",
    lastUpdated: "21 Apr 2026, 9:14am",
  };
})();

// ── Helpers exposed globally ──────────────────────────────────────────────
// Sum a daily series up to (and including) day N (1-indexed).
window.sumDaily = function(daily, dayOfFY) {
  let perm = 0, temp = 0;
  const cap = Math.min(dayOfFY, daily.length);
  for (let i = 0; i < cap; i++) { perm += daily[i].perm; temp += daily[i].temp; }
  return { perm, temp, total: perm + temp };
};

// Convert {monthIdx 0..11, dayOfMonth 1..N} to day-of-FY (1..365)
window.toDayOfFY = function(monthIdx, dayOfMonth) {
  const data = window.LEGENDS_DATA;
  const before = monthIdx === 0 ? 0 : data.CUM_DAYS[monthIdx - 1];
  return before + dayOfMonth;
};

// Convert day-of-FY back to {monthIdx, dayOfMonth}
window.fromDayOfFY = function(dayOfFY) {
  const data = window.LEGENDS_DATA;
  for (let m = 0; m < 12; m++) {
    if (dayOfFY <= data.CUM_DAYS[m]) {
      const before = m === 0 ? 0 : data.CUM_DAYS[m - 1];
      return { monthIdx: m, dayOfMonth: dayOfFY - before };
    }
  }
  return { monthIdx: 11, dayOfMonth: data.DAYS_IN_MONTH[11] };
};

// Format a day-of-FY as "15 Apr"
window.fmtDayOfFY = function(dayOfFY) {
  const { monthIdx, dayOfMonth } = window.fromDayOfFY(dayOfFY);
  return `${dayOfMonth} ${window.LEGENDS_DATA.MONTHS[monthIdx]}`;
};
