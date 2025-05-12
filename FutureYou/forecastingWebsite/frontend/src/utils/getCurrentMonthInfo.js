// src/utils/getCurrentMonthInfo.js

export function getCurrentMonthInfo(calendar, today = new Date()) {
  const matchedEntry = calendar.find((entry) => {
    const [startStr, endStr] = entry.range.split(" - ");
    const [sd, sm, sy] = startStr.split("/").map(Number);
    const [ed, em, ey] = endStr.split("/").map(Number);

    const start = new Date(sy < 100 ? sy + 2000 : sy, sm - 1, sd);
    const end = new Date(ey < 100 ? ey + 2000 : ey, em - 1, ed);

    start.setHours(0, 0, 0, 0);
    end.setHours(23, 59, 59, 999);

    return today >= start && today <= end;
  });

  const currentMonth = matchedEntry?.month ?? "Unknown";
  const currentFY = matchedEntry?.fy ?? "FY?";
  const weeksInMonth = calendar.filter(
    (e) => e.fy === currentFY && e.month === currentMonth
  );

  let currentWeekIndex = 0;

  for (let i = 0; i < weeksInMonth.length; i++) {
    const [startStr] = weeksInMonth[i].range.split(" - ");
    const [sd, sm, sy] = startStr.split("/").map(Number);
    const startDate = new Date(sy < 100 ? sy + 2000 : sy, sm - 1, sd);

    if (today < startDate) {
      currentWeekIndex = i;
      break;
    }
  }

  // If today is after all start dates, set to length (highlight all)
  if (currentWeekIndex === -1) currentWeekIndex = weeksInMonth.length;

  const formattedDate = `${today.getDate()}/${today.getMonth() + 1}/${today
    .getFullYear()
    .toString()
    .slice(-2)}`;

  const weekLabel = matchedEntry
    ? `${matchedEntry.month} Week ${matchedEntry.week}, ${formattedDate}`
    : "";

  return {
    currentMonth,
    currentFY,
    weeksInMonth,
    currentWeekIndex,
    weekLabel,
  };
}
