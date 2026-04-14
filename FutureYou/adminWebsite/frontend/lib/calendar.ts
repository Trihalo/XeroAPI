// FutureYou fiscal calendar — FY25 and FY26 week definitions

export interface CalendarEntry {
  fy: string;
  month: string;
  week: number;
  range: string;
  previousMonth: string;
  previousMonthFY: string;
}

const calendar: CalendarEntry[] = [
  { fy: "FY25", month: "Apr", week: 1, range: "29/3/25 - 4/4/25",   previousMonth: "Mar", previousMonthFY: "FY25" },
  { fy: "FY25", month: "Apr", week: 2, range: "5/4/25 - 11/4/25",   previousMonth: "Mar", previousMonthFY: "FY25" },
  { fy: "FY25", month: "Apr", week: 3, range: "12/4/25 - 18/4/25",  previousMonth: "Mar", previousMonthFY: "FY25" },
  { fy: "FY25", month: "Apr", week: 4, range: "19/4/25 - 25/4/25",  previousMonth: "Mar", previousMonthFY: "FY25" },
  { fy: "FY25", month: "May", week: 1, range: "26/4/25 - 2/5/25",   previousMonth: "Apr", previousMonthFY: "FY25" },
  { fy: "FY25", month: "May", week: 2, range: "3/5/25 - 9/5/25",    previousMonth: "Apr", previousMonthFY: "FY25" },
  { fy: "FY25", month: "May", week: 3, range: "10/5/25 - 16/5/25",  previousMonth: "Apr", previousMonthFY: "FY25" },
  { fy: "FY25", month: "May", week: 4, range: "17/5/25 - 23/5/25",  previousMonth: "Apr", previousMonthFY: "FY25" },
  { fy: "FY25", month: "Jun", week: 1, range: "24/5/25 - 30/5/25",  previousMonth: "May", previousMonthFY: "FY25" },
  { fy: "FY25", month: "Jun", week: 2, range: "31/5/25 - 6/6/25",   previousMonth: "May", previousMonthFY: "FY25" },
  { fy: "FY25", month: "Jun", week: 3, range: "7/6/25 - 13/6/25",   previousMonth: "May", previousMonthFY: "FY25" },
  { fy: "FY25", month: "Jun", week: 4, range: "14/6/25 - 20/6/25",  previousMonth: "May", previousMonthFY: "FY25" },
  { fy: "FY25", month: "Jun", week: 5, range: "21/6/25 - 27/6/25",  previousMonth: "May", previousMonthFY: "FY25" },
  { fy: "FY26", month: "Jul", week: 1, range: "28/6/25 - 4/7/25",   previousMonth: "Jun", previousMonthFY: "FY25" },
  { fy: "FY26", month: "Jul", week: 2, range: "5/7/25 - 11/7/25",   previousMonth: "Jun", previousMonthFY: "FY25" },
  { fy: "FY26", month: "Jul", week: 3, range: "12/7/25 - 18/7/25",  previousMonth: "Jun", previousMonthFY: "FY25" },
  { fy: "FY26", month: "Jul", week: 4, range: "19/7/25 - 25/7/25",  previousMonth: "Jun", previousMonthFY: "FY25" },
  { fy: "FY26", month: "Aug", week: 1, range: "26/7/25 - 1/8/25",   previousMonth: "Jul", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Aug", week: 2, range: "2/8/25 - 8/8/25",    previousMonth: "Jul", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Aug", week: 3, range: "9/8/25 - 15/8/25",   previousMonth: "Jul", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Aug", week: 4, range: "16/8/25 - 22/8/25",  previousMonth: "Jul", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Sep", week: 1, range: "23/8/25 - 29/8/25",  previousMonth: "Aug", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Sep", week: 2, range: "30/8/25 - 5/9/25",   previousMonth: "Aug", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Sep", week: 3, range: "6/9/25 - 12/9/25",   previousMonth: "Aug", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Sep", week: 4, range: "13/9/25 - 19/9/25",  previousMonth: "Aug", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Sep", week: 5, range: "20/9/25 - 26/9/25",  previousMonth: "Aug", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Oct", week: 1, range: "27/9/25 - 3/10/25",  previousMonth: "Sep", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Oct", week: 2, range: "4/10/25 - 10/10/25", previousMonth: "Sep", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Oct", week: 3, range: "11/10/25 - 17/10/25",previousMonth: "Sep", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Oct", week: 4, range: "18/10/25 - 24/10/25",previousMonth: "Sep", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Nov", week: 1, range: "25/10/25 - 31/10/25",previousMonth: "Oct", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Nov", week: 2, range: "1/11/25 - 7/11/25",  previousMonth: "Oct", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Nov", week: 3, range: "8/11/25 - 14/11/25", previousMonth: "Oct", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Nov", week: 4, range: "15/11/25 - 21/11/25",previousMonth: "Oct", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Dec", week: 1, range: "22/11/25 - 28/11/25",previousMonth: "Nov", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Dec", week: 2, range: "29/11/25 - 5/12/25", previousMonth: "Nov", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Dec", week: 3, range: "6/12/25 - 12/12/25", previousMonth: "Nov", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Dec", week: 4, range: "13/12/25 - 19/12/25",previousMonth: "Nov", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Dec", week: 5, range: "20/12/25 - 26/12/25",previousMonth: "Nov", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Dec", week: 6, range: "27/12/25 - 31/12/25",previousMonth: "Nov", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Jan", week: 1, range: "1/1/26 - 2/1/26",    previousMonth: "Dec", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Jan", week: 2, range: "3/1/26 - 9/1/26",    previousMonth: "Dec", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Jan", week: 3, range: "10/1/26 - 16/1/26",  previousMonth: "Dec", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Jan", week: 4, range: "17/1/26 - 23/1/26",  previousMonth: "Dec", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Feb", week: 1, range: "24/1/26 - 30/1/26",  previousMonth: "Jan", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Feb", week: 2, range: "31/1/26 - 6/2/26",   previousMonth: "Jan", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Feb", week: 3, range: "7/2/26 - 13/2/26",   previousMonth: "Jan", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Feb", week: 4, range: "14/2/26 - 20/2/26",  previousMonth: "Jan", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Mar", week: 1, range: "21/2/26 - 27/2/26",  previousMonth: "Feb", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Mar", week: 2, range: "28/2/26 - 6/3/26",   previousMonth: "Feb", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Mar", week: 3, range: "7/3/26 - 13/3/26",   previousMonth: "Feb", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Mar", week: 4, range: "14/3/26 - 20/3/26",  previousMonth: "Feb", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Mar", week: 5, range: "21/3/26 - 29/3/26",  previousMonth: "Feb", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Apr", week: 1, range: "30/3/26 - 3/4/26",   previousMonth: "Mar", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Apr", week: 2, range: "4/4/26 - 10/4/26",   previousMonth: "Mar", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Apr", week: 3, range: "11/4/26 - 17/4/26",  previousMonth: "Mar", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Apr", week: 4, range: "18/4/26 - 24/4/26",  previousMonth: "Mar", previousMonthFY: "FY26" },
  { fy: "FY26", month: "May", week: 1, range: "25/4/26 - 1/5/26",   previousMonth: "Apr", previousMonthFY: "FY26" },
  { fy: "FY26", month: "May", week: 2, range: "2/5/26 - 8/5/26",    previousMonth: "Apr", previousMonthFY: "FY26" },
  { fy: "FY26", month: "May", week: 3, range: "9/5/26 - 15/5/26",   previousMonth: "Apr", previousMonthFY: "FY26" },
  { fy: "FY26", month: "May", week: 4, range: "16/5/26 - 22/5/26",  previousMonth: "Apr", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Jun", week: 1, range: "23/5/26 - 29/5/26",  previousMonth: "May", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Jun", week: 2, range: "30/5/26 - 5/6/26",   previousMonth: "May", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Jun", week: 3, range: "6/6/26 - 12/6/26",   previousMonth: "May", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Jun", week: 4, range: "13/6/26 - 19/6/26",  previousMonth: "May", previousMonthFY: "FY26" },
  { fy: "FY26", month: "Jun", week: 5, range: "20/6/26 - 30/6/26",  previousMonth: "May", previousMonthFY: "FY26" },
];

export default calendar;

export interface MonthInfo {
  currentMonth: string;
  currentFY: string;
  weeksInMonth: CalendarEntry[];
  currentWeekIndex: number;
  previousMonth: string;
  previousMonthFY: string;
  nextMonth: string;
  nextMonthFY: string;
  nextMonthWeeks: CalendarEntry[];
}

export function getCurrentMonthInfo(today = new Date()): MonthInfo {
  const matched = calendar.find((entry) => {
    const [startStr, endStr] = entry.range.split(" - ");
    const [sd, sm, sy] = startStr.split("/").map(Number);
    const [ed, em, ey] = endStr.split("/").map(Number);
    const start = new Date(sy < 100 ? sy + 2000 : sy, sm - 1, sd);
    const end   = new Date(ey < 100 ? ey + 2000 : ey, em - 1, ed);
    start.setHours(0, 0, 0, 0);
    end.setHours(23, 59, 59, 999);
    return today >= start && today <= end;
  });

  // Fallback: use last entry if today is beyond the calendar
  const entry = matched ?? calendar[calendar.length - 1];

  // Derive next month from unique ordered month keys in the calendar
  const orderedMonths = Array.from(
    new Map(calendar.map((e) => [`${e.fy}:${e.month}`, { fy: e.fy, month: e.month }])).entries(),
  ).map(([, v]) => v);
  const currentIdx   = orderedMonths.findIndex((m) => m.fy === entry.fy && m.month === entry.month);
  const nextEntry    = orderedMonths[currentIdx + 1] ?? orderedMonths[currentIdx];
  const nextMonthWeeks = calendar.filter((e) => e.fy === nextEntry.fy && e.month === nextEntry.month);

  return {
    currentMonth:     entry.month,
    currentFY:        entry.fy,
    weeksInMonth:     calendar.filter((e) => e.fy === entry.fy && e.month === entry.month),
    currentWeekIndex: entry.week,
    previousMonth:    entry.previousMonth,
    previousMonthFY:  entry.previousMonthFY,
    nextMonth:        nextEntry.month,
    nextMonthFY:      nextEntry.fy,
    nextMonthWeeks,
  };
}
