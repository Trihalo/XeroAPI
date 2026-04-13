// Core calculation helpers for the forecasting module

export type WeekMap = Record<string, Record<number, number>>;

export function initializeWeeklyMap(keys: string[], weeks: number[]): WeekMap {
  const map: WeekMap = {};
  keys.forEach((key) => {
    map[key] = {};
    weeks.forEach((w) => {
      map[key][w] = 0;
    });
  });
  return map;
}

export function computeCumulativeTotals(inputMap: WeekMap): WeekMap {
  const result: WeekMap = {};

  Object.entries(inputMap).forEach(([key, weekValues]) => {
    result[key] = {};
    const sortedWeeks = Object.keys(weekValues)
      .map(Number)
      .sort((a, b) => a - b);

    sortedWeeks.forEach((week, i) => {
      result[key][week] =
        i === 0
          ? 0
          : result[key][sortedWeeks[i - 1]] + (weekValues[sortedWeeks[i - 1]] || 0);
    });
  });

  const allWeeks = new Set<number>();
  Object.values(result).forEach((weekMap) => {
    Object.keys(weekMap).forEach((w) => allWeeks.add(Number(w)));
  });

  result["Total"] = {};
  Array.from(allWeeks)
    .sort((a, b) => a - b)
    .forEach((week) => {
      result["Total"][week] = Object.entries(result)
        .filter(([key]) => key !== "Total")
        .reduce((sum, [, weekMap]) => sum + (weekMap[week] || 0), 0);
    });

  return result;
}

export interface RecruiterEntry {
  area: string;
  weeks: Record<number, number>;
}

export function buildRecruiterTogetherByWeek(params: {
  allRecruiters: string[];
  recruiterToArea: Record<string, string>;
  cumulativeActualsByRecruiter: WeekMap;
  cumulativeForecastsByRecruiter: WeekMap;
}): Record<string, RecruiterEntry> {
  const { allRecruiters, recruiterToArea, cumulativeActualsByRecruiter, cumulativeForecastsByRecruiter } = params;
  const result: Record<string, RecruiterEntry> = {};

  allRecruiters.forEach((recruiter) => {
    const actualWeeks   = cumulativeActualsByRecruiter[recruiter] || {};
    const forecastWeeks = cumulativeForecastsByRecruiter[recruiter] || {};
    const allWeeks      = new Set<number>([
      ...Object.keys(actualWeeks).map(Number),
      ...Object.keys(forecastWeeks).map(Number),
    ]);

    result[recruiter] = {
      area: recruiterToArea[recruiter] || "Unknown",
      weeks: Object.fromEntries(
        Array.from(allWeeks).map((w) => [w, (actualWeeks[w] || 0) + (forecastWeeks[w] || 0)]),
      ),
    };
  });

  return result;
}

export function groupRecruitersByAreaWeek(
  recruiterData: Record<string, RecruiterEntry>,
): Record<string, Record<number, number>> {
  const areaWeekTotals: Record<string, Record<number, number>> = {};

  Object.values(recruiterData).forEach(({ area, weeks }) => {
    if (!areaWeekTotals[area]) areaWeekTotals[area] = {};
    Object.entries(weeks).forEach(([week, amount]) => {
      const w = Number(week);
      areaWeekTotals[area][w] = (areaWeekTotals[area][w] || 0) + amount;
    });
  });

  return areaWeekTotals;
}

// Format a dollar value as "123K" — used in summary tables
export function fmtK(value: number): string {
  return value > 0 ? `${Math.round(value / 1000).toLocaleString("en-AU")}` : "-";
}

// Format a raw dollar value, showing negatives as (123)
export function fmtDollar(value: number): string {
  if (value === 0) return "-";
  const rounded = Math.round(value);
  if (rounded < 0) return `(${Math.abs(rounded).toLocaleString("en-AU")})`;
  return rounded.toLocaleString("en-AU");
}
