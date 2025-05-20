// src/utils/calcHelpers.js

export const initializeWeeklyMap = (keys, weeks) => {
  const map = {};
  keys.forEach((key) => {
    map[key] = {};
    weeks.forEach((w) => {
      map[key][w] = 0;
    });
  });
  return map;
};

export const computeCumulativeTotals = (inputMap) => {
  const result = {};
  Object.entries(inputMap).forEach(([key, weekValues]) => {
    result[key] = {};
    const sortedWeeks = Object.keys(weekValues)
      .map(Number)
      .sort((a, b) => a - b);
    sortedWeeks.forEach((week, i) => {
      result[key][week] =
        i === 0
          ? 0
          : result[key][sortedWeeks[i - 1]] +
            (weekValues[sortedWeeks[i - 1]] || 0);
    });
  });

  const allWeeks = new Set();
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
};

export function buildRecruiterTogetherByWeek({
  allRecruiters,
  recruiterToArea,
  cumulativeActualsByRecruiter,
  cumulativeForecastsByRecruiter,
}) {
  const result = {};

  allRecruiters.forEach((recruiter) => {
    result[recruiter] = {
      area: recruiterToArea[recruiter] || "Unknown",
      weeks: {},
    };

    const actualWeeks = cumulativeActualsByRecruiter[recruiter] || {};
    const forecastWeeks = cumulativeForecastsByRecruiter[recruiter] || {};

    const allWeeks = new Set([
      ...Object.keys(actualWeeks).map(Number),
      ...Object.keys(forecastWeeks).map(Number),
    ]);

    allWeeks.forEach((week) => {
      const actual = actualWeeks[week] || 0;
      const forecast = forecastWeeks[week] || 0;
      result[recruiter].weeks[week] = actual + forecast;
    });
  });

  return result;
}

export function groupRecruitersByAreaWeek(recruiterData) {
  const areaWeekTotals = {};

  Object.values(recruiterData).forEach(({ area, weeks }) => {
    if (!areaWeekTotals[area]) areaWeekTotals[area] = {};

    Object.entries(weeks).forEach(([week, amount]) => {
      const w = Number(week);
      if (!areaWeekTotals[area][w]) areaWeekTotals[area][w] = 0;
      areaWeekTotals[area][w] += amount;
    });
  });

  return areaWeekTotals;
}
