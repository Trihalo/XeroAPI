"use client";

import { useState, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";
import { getCurrentMonthInfo } from "@/lib/calendar";
import { useRecruiterData } from "@/hooks/forecasting/useRecruiterData";
import { useInvoiceData } from "@/hooks/forecasting/useInvoiceData";
import { useCumulativeActuals } from "@/hooks/forecasting/useCumulativeActuals";
import { useCumulativeForecasts } from "@/hooks/forecasting/useCumulativeForecasts";
import { useSubmittedRecruiters } from "@/hooks/forecasting/useSubmittedRecruiters";
import { useMonthlyTargets } from "@/hooks/forecasting/useMonthlyTargets";
import {
  buildRecruiterTogetherByWeek,
  initializeWeeklyMap,
  fmtK,
  fmtDollar,
} from "@/lib/calcHelpers";
import { fcFetchForecastSummary } from "@/lib/forecasting-api";

function getWeekToWeekMovement(
  data: Record<string, { area: string; weeks: Record<number, number> }>,
  currentWeekIndex: number
): Record<string, string[]> {
  const movementByArea: Record<string, string[]> = {};
  Object.entries(data).forEach(([recruiter, { area, weeks }]) => {
    const current = weeks[currentWeekIndex] || 0;
    const prev = weeks[currentWeekIndex - 1] || 0;
    const diff = current - prev;
    if (!movementByArea[area]) movementByArea[area] = [];
    const firstName = recruiter.split(" ")[0];
    const sign = diff >= 0 ? "+" : "-";
    const value = Math.round(Math.abs(diff) / 1000);
    if (value === 0) return;
    movementByArea[area].push(`${firstName} ${sign}${value}K`);
  });
  return movementByArea;
}

export default function ForecastingPage() {
  const router = useRouter();
  const calInfo = useMemo(() => getCurrentMonthInfo(), []);
  const {
    currentMonth,
    currentFY,
    weeksInMonth,
    currentWeekIndex,
    nextMonth,
    nextMonthFY,
    nextMonthWeeks,
  } = calInfo;

  const [viewNext, setViewNext] = useState(false);

  const activeMonth = viewNext ? nextMonth : currentMonth;
  const activeFY = viewNext ? nextMonthFY : currentFY;
  const activeWeeks = viewNext ? nextMonthWeeks : weeksInMonth;
  // For next month, show all weeks in the summary (no data yet, but forecasts may exist).
  // For current month, only show up to today's week.
  const activeWeekIndex = viewNext
    ? Math.max(...nextMonthWeeks.map((e) => e.week))
    : currentWeekIndex;

  const weeks = useMemo(() => activeWeeks.map((w) => w.week), [activeWeeks]);

  const {
    loading: recruiterLoading,
    error: recruiterError,
    allRecruiters,
    allAreas,
    summaryMapping,
    headcountByArea,
    recruiterToArea,
  } = useRecruiterData();
  const {
    currentData: invoices,
    loading: invoiceLoading,
    error: invoiceError,
  } = useInvoiceData();
  const submitted = useSubmittedRecruiters(
    activeFY,
    activeMonth,
    activeWeekIndex
  );
  const targetByMonth = useMonthlyTargets(activeFY);

  const {
    actualsByRecruiterWeek,
    cumulativeActuals,
    cumulativeActualsByRecruiter,
  } = useCumulativeActuals(
    activeMonth,
    activeFY,
    weeks,
    allRecruiters,
    allAreas,
    invoices
  );

  const {
    rawForecastRows,
    cumulativeForecasts,
    cumulativeForecastsByRecruiter,
  } = useCumulativeForecasts(activeFY, activeMonth, recruiterToArea);

  const recruiterTogetherByWeek = useMemo(
    () =>
      buildRecruiterTogetherByWeek({
        allRecruiters,
        recruiterToArea,
        cumulativeActualsByRecruiter,
        cumulativeForecastsByRecruiter,
      }),
    [
      allRecruiters,
      recruiterToArea,
      cumulativeActualsByRecruiter,
      cumulativeForecastsByRecruiter,
    ]
  );

  const movement = useMemo(
    () => getWeekToWeekMovement(recruiterTogetherByWeek, activeWeekIndex),
    [recruiterTogetherByWeek, activeWeekIndex]
  );

  // Aggregated forecasts for summary tab
  const aggregatedForecasts = useMemo(() => {
    const map = initializeWeeklyMap([...allAreas, "Total"], weeks);
    allAreas.forEach((area) => {
      weeks.forEach((week) => {
        const forecast = cumulativeForecasts[area]?.[week] || 0;
        const actual = cumulativeActuals[area]?.[week] || 0;
        const total = forecast + actual;
        map[area][week] = total;
        map["Total"][week] += total;
      });
    });
    return map;
  }, [allAreas, weeks, cumulativeForecasts, cumulativeActuals]);

  // ── View tab data ─────────────────────────────────────────────────────────
  const [forecastData, setForecastData] = useState<
    {
      title: string;
      data: { name: string; weeks: number[]; uploadWeek: number }[];
    }[]
  >([]);
  const [viewLoading, setViewLoading] = useState(false);
  const [viewError, setViewError] = useState<string | null>(null);
  const hasFetchedView = useRef(false);

  async function fetchViewData() {
    if (!Object.keys(summaryMapping).length || !weeks.length) return;
    setViewLoading(true);
    setViewError(null);
    try {
      const summary = await fcFetchForecastSummary(activeFY, activeMonth);
      const revenueMap: Record<string, Record<number, number>> = {};
      const latestUploadMap: Record<string, number> = {};

      for (const row of summary) {
        const upWk = Number(row.uploadWeek);
        if (!latestUploadMap[row.name] || upWk > latestUploadMap[row.name]) {
          latestUploadMap[row.name] = upWk;
        }
      }
      for (const row of summary) {
        if (Number(row.uploadWeek) === latestUploadMap[row.name]) {
          if (!revenueMap[row.name]) revenueMap[row.name] = {};
          revenueMap[row.name][Number(row.week)] = Number(row.total_revenue);
        }
      }

      const structured = Object.entries(summaryMapping).map(
        ([category, names]) => ({
          title: category,
          data: names.map((name) => {
            const paddedWeeks = weeks.map((weekNum) => revenueMap[name]?.[weekNum] || 0);
            return {
              name,
              weeks: paddedWeeks,
              uploadWeek: latestUploadMap[name] || 0,
            };
          }),
        })
      );
      setForecastData(structured);
      hasFetchedView.current = true;
    } catch {
      setViewError("Failed to load detailed forecast data.");
    } finally {
      setViewLoading(false);
    }
  }

  const forecastViewSections = useMemo(() => {
    if (!forecastData.length || !activeWeeks.length) return [];

    return forecastData.map((section) => {
      const sectionRows = section.data.map((rowData) => {
        const paddedWeeks = rowData.weeks;
        const finalWeeks = paddedWeeks.map((amt, i) => {
          const weekNum = i + 1;
          return weekNum < activeWeekIndex
            ? actualsByRecruiterWeek[rowData.name]?.[weekNum] || 0
            : amt;
        });
        return {
          name: rowData.name,
          finalWeeks,
          rowTotal: finalWeeks.reduce((a, b) => a + b, 0),
        };
      });
      const totals = activeWeeks.map((_, i) =>
        sectionRows.reduce((s, r) => s + (r.finalWeeks[i] || 0), 0)
      );
      const totalSum = totals.reduce((a, b) => a + b, 0);
      return { title: section.title, rows: sectionRows, totals, totalSum };
    });
  }, [
    forecastData,
    activeWeeks,
    actualsByRecruiterWeek,
    activeWeekIndex,
  ]);

  const remainingRecruiters = allRecruiters.filter((r) => !submitted.has(r));

  const isLoading = recruiterLoading || invoiceLoading;

  return (
    <div className="p-6 md:p-8 flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-navy">Recruiter Forecasts</h1>
          <p className="text-dark-grey text-sm mt-0.5">
            {activeFY} — {activeMonth}
          </p>
        </div>
        <div className="flex gap-1 mt-1">
          {(["Current Month", "Next Month"] as const).map((label) => {
            const isNext = label === "Next Month";
            const active = viewNext === isNext;
            return (
              <button
                key={label}
                onClick={() => {
                  setViewNext(isNext);
                  hasFetchedView.current = false;
                }}
                className={`px-3 py-1.5 text-sm rounded-md font-medium transition-colors ${active
                    ? "bg-navy text-white"
                    : "bg-gray-100 text-dark-grey hover:bg-gray-200"
                  }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {(recruiterError || invoiceError) && (
        <Alert variant="destructive">
          <AlertCircle className="w-4 h-4" />
          <AlertDescription>{recruiterError ?? invoiceError}</AlertDescription>
        </Alert>
      )}

      <Tabs
        defaultValue="input"
        onValueChange={(tab) => {
          if (tab === "view" && !hasFetchedView.current) fetchViewData();
        }}
      >
        <div className="border-b border-gray-200 mb-4">
          <TabsList className="bg-transparent p-0 rounded-none h-auto gap-0">
            {(["Forecast Input", "Summary", "Detailed View"] as const).map((label) => {
              const value = label === "Forecast Input" ? "input" : label === "Summary" ? "summary" : "view";
              return (
                <TabsTrigger
                  key={value}
                  value={value}
                  className="rounded-none border-b-2 border-transparent data-[state=active]:border-navy data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:text-navy px-4 py-2 text-sm font-medium text-dark-grey hover:text-navy transition-colors"
                >
                  {label}
                </TabsTrigger>
              );
            })}
          </TabsList>
        </div>

        {/* ── INPUT TAB ─────────────────────────────────────────────────── */}
        <TabsContent value="input">
          <div className="space-y-4">
            {remainingRecruiters.length > 0 && (
              <p className="text-sm text-dark-grey">
                <span className="font-semibold text-salmon">
                  {remainingRecruiters.length}
                </span>{" "}
                recruiter
                {remainingRecruiters.length !== 1 ? "s" : ""} yet to submit (
                {remainingRecruiters.map((n) => n.split(" ")[0]).join(", ")})
              </p>
            )}

            {isLoading ? (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="space-y-3">
                    <Skeleton className="h-5 w-40" />
                    <div className="flex flex-wrap gap-2">
                      {[1, 2, 3].map((j) => (
                        <Skeleton key={j} className="h-8 w-24 rounded-full" />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {Object.entries(summaryMapping).map(([area, names]) => {
                  const allSubmitted = names.every((n) => submitted.has(n));
                  const someSubmitted = names.some((n) => submitted.has(n));
                  return (
                    <div
                      key={area}
                      className="rounded-xl border border-gray-200 bg-white overflow-hidden"
                    >
                      {/* Area header — clicking opens the area upload page */}
                      <button
                        onClick={() => {
                          const params = new URLSearchParams({
                            area,
                            month: activeMonth,
                            fy: activeFY,
                            weekIndex: viewNext
                              ? "1"
                              : String(currentWeekIndex),
                          });
                          router.push(
                            `/forecasting/upload?${params.toString()}`
                          );
                        }}
                        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-100 hover:bg-navy/5 transition-colors group"
                      >
                        <span className="text-sm font-semibold text-navy group-hover:text-navy">
                          {area}
                        </span>
                        <span
                          className={`text-xs font-medium ${allSubmitted
                              ? "text-salmon"
                              : someSubmitted
                                ? "text-dark-grey"
                                : "text-dark-grey"
                            }`}
                        >
                          {allSubmitted
                            ? "All submitted ✓"
                            : someSubmitted
                              ? `${names.filter((n) => submitted.has(n)).length
                              }/${names.length} submitted`
                              : "Open →"}
                        </span>
                      </button>

                      {/* Recruiter list — non-clickable, shows submitted status */}
                      <ul className="px-4 py-3 space-y-1.5">
                        {names.map((name) => (
                          <li
                            key={name}
                            className="flex items-center justify-between text-sm"
                          >
                            <span
                              className={
                                submitted.has(name)
                                  ? "text-navy font-medium"
                                  : "text-dark-grey"
                              }
                            >
                              {name}
                            </span>
                            {submitted.has(name) && (
                              <span className="text-xs font-bold text-salmon">
                                ✓
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  );
                })}
              </div>
            )}

          </div>
        </TabsContent>

        {/* ── SUMMARY TAB ───────────────────────────────────────────────── */}
        <TabsContent value="summary">
          <div className="space-y-4">
            <div className="flex gap-6 text-sm text-dark-grey flex-wrap">
              {targetByMonth[currentMonth] && (
                <span>
                  Target:{" "}
                  <b className="text-navy">
                    $
                    {Math.round(
                      targetByMonth[currentMonth] / 1000
                    ).toLocaleString("en-AU")}
                    K
                  </b>
                </span>
              )}
              {remainingRecruiters.length > 0 && (
                <span>
                  Missing:{" "}
                  <b className="text-salmon">
                    {remainingRecruiters.length} recruiters
                  </b>
                </span>
              )}
            </div>

            {isLoading ? (
              <div className="space-y-2">
                {[1, 2, 3, 4, 5].map((i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : (
              <ScrollArea className="w-full overflow-x-auto">
                <div className="inline-block rounded-lg border border-gray-200 overflow-hidden">
                  <table className="w-auto text-sm text-left table-fixed">
                    <colgroup>
                      <col className="w-56" />{/* Area */}
                      {activeWeeks.map((w) => <col key={w.week} className="w-[100px]" />)}
                      <col className="w-[120px]" />{/* MTD */}
                      <col className="w-[70px]" />{/* HC */}
                      <col className="w-[100px]" />{/* Prod. */}
                      <col className="w-40" />{/* w2w */}
                    </colgroup>
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr className="divide-x divide-gray-200">
                        <th className="text-left py-2.5 px-4 font-semibold text-navy whitespace-nowrap sticky left-0 bg-gray-50">
                          Area
                        </th>
                        {activeWeeks.map((w) => (
                          <th key={w.week} className="text-right py-2.5 px-4 font-semibold text-navy whitespace-nowrap">
                            Wk {w.week}
                          </th>
                        ))}
                        <th className="text-right py-2.5 px-4 font-semibold text-navy whitespace-nowrap">
                          MTD
                        </th>
                        <th className="text-right py-2.5 px-4 font-semibold text-navy whitespace-nowrap">
                          HC
                        </th>
                        <th className="text-right py-2.5 px-4 font-semibold text-navy whitespace-nowrap">
                          Prod.
                        </th>
                        <th className="text-right py-2.5 px-4 font-semibold text-navy whitespace-nowrap">
                          w2w
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(summaryMapping).map(([area]) => {
                        const weekMap = aggregatedForecasts[area] || {};
                        const headcount = headcountByArea[area] ?? 0;
                        const mtd = cumulativeActuals?.[area]?.[activeWeekIndex] || 0;
                        const prod =
                          headcount > 0
                            ? Math.round(weekMap[activeWeekIndex] / (1000 * headcount)).toLocaleString("en-AU")
                            : "-";
                        return (
                          <tr key={area} className="border-b border-gray-100 hover:bg-gray-50 divide-x divide-gray-200">
                            <td className="py-2.5 px-4 text-sm font-medium text-gray-900 truncate sticky left-0 bg-white">
                              {area}
                            </td>
                            {activeWeeks.map((w) => (
                              <td key={w.week} className="py-2.5 px-4 text-right text-sm text-gray-900 tabular-nums">
                                {w.week <= activeWeekIndex ? fmtK(weekMap[w.week] || 0) : "-"}
                              </td>
                            ))}
                            <td className="py-2.5 px-4 text-right text-sm text-gray-900 tabular-nums">
                              {fmtK(mtd)}
                            </td>
                            <td className="py-2.5 px-4 text-right text-sm text-gray-900">
                              {headcount || "-"}
                            </td>
                            <td className="py-2.5 px-4 text-right text-sm text-gray-900 tabular-nums">
                              {prod}
                            </td>
                            <td className="py-2.5 px-4 text-right text-xs text-dark-grey">
                              {movement[area]?.join(", ") || ""}
                            </td>
                          </tr>
                        );
                      })}
                      <tr className="font-semibold bg-gray-100 border-t-2 border-gray-300 divide-x divide-gray-200">
                        <td className="py-2.5 px-4 text-sm text-navy sticky left-0 bg-gray-100">
                          Total
                        </td>
                        {activeWeeks.map((w) => (
                          <td key={w.week} className="py-2.5 px-4 text-right text-sm text-gray-900 tabular-nums">
                            {w.week <= activeWeekIndex
                              ? Math.round((aggregatedForecasts["Total"]?.[w.week] || 0) / 1000).toLocaleString("en-AU")
                              : "-"}
                          </td>
                        ))}
                        <td className="py-2.5 px-4 text-right text-sm text-gray-900 tabular-nums">
                          {Math.round((cumulativeActuals["Total"]?.[activeWeekIndex] || 0) / 1000).toLocaleString("en-AU")}
                        </td>
                        <td className="py-2.5 px-4 text-right text-sm text-gray-900">
                          {Object.values(headcountByArea).reduce((a, b) => a + b, 0).toFixed(1)}
                        </td>
                        <td className="py-2.5 px-4 text-right text-sm text-gray-900 tabular-nums">
                          {(() => {
                            const hc = Object.values(headcountByArea).reduce((a, b) => a + b, 0);
                            const total = aggregatedForecasts["Total"]?.[activeWeekIndex] || 0;
                            return hc ? Math.round(total / (1000 * hc)).toLocaleString("en-AU") : "-";
                          })()}
                        </td>
                        <td />
                      </tr>
                    </tbody>
                  </table>
                </div>
                <ScrollBar orientation="horizontal" />
              </ScrollArea>
            )}
          </div>
        </TabsContent>

        {/* ── DETAILED VIEW TAB ─────────────────────────────────────────── */}
        <TabsContent value="view">
          <div className="space-y-6">
            <p className="text-xs text-dark-grey">
              Cells highlighted in{" "}
              <span className="font-semibold text-salmon">salmon</span>{" "}
              represent actual invoiced revenue.
            </p>

            {viewError && (
              <Alert variant="destructive">
                <AlertCircle className="w-4 h-4" />
                <AlertDescription>
                  {viewError}{" "}
                  <button onClick={fetchViewData} className="underline ml-1">
                    Retry
                  </button>
                </AlertDescription>
              </Alert>
            )}

            {viewLoading ? (
              <div className="space-y-8">
                {[1, 2].map((i) => (
                  <div key={i} className="space-y-2">
                    <Skeleton className="h-5 w-48" />
                    {[1, 2, 3, 4].map((j) => (
                      <Skeleton key={j} className="h-9 w-full" />
                    ))}
                  </div>
                ))}
              </div>
            ) : forecastViewSections.length === 0 ? (
              <p className="text-sm text-dark-grey">
                No forecast data available.
              </p>
            ) : (
              forecastViewSections.map(({ title, rows, totals, totalSum }) => (
                <div key={title}>
                  <h3 className="text-sm font-semibold text-navy mb-2">
                    {title}
                  </h3>
                  <ScrollArea className="w-full overflow-x-auto">
                    <div className="inline-block rounded-lg border border-gray-200 overflow-hidden">
                      <table className="w-auto text-sm text-left table-fixed">
                        <colgroup>
                          <col className="w-[400px]" />{/* Name */}
                          {activeWeeks.map((w) => (
                            <col key={w.week} className="w-[140px]" />
                          ))}
                          <col className="w-40" />{/* Total */}
                        </colgroup>
                        <thead className="bg-gray-50 border-b border-gray-200">
                          <tr className="divide-x divide-gray-200">
                            <th className="py-2.5 px-4 font-semibold text-navy whitespace-nowrap sticky left-0 bg-gray-50">
                              Name
                            </th>
                            {activeWeeks.map((w) => (
                              <th
                                key={w.week}
                                className="py-2.5 px-4 font-semibold text-navy text-right whitespace-nowrap"
                              >
                                Wk {w.week}
                              </th>
                            ))}
                            <th className="py-2.5 px-4 font-semibold text-navy text-right whitespace-nowrap border-l-2 border-gray-300 bg-navy/5">
                              Total
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {rows.map(({ name, finalWeeks, rowTotal }) => (
                            <tr
                              key={name}
                              className="border-b border-gray-100 divide-x divide-gray-200"
                            >
                              <td className="py-2 px-4 font-medium text-gray-900 truncate sticky left-0 bg-white">
                                {name}
                              </td>
                              {finalWeeks.map((amt, i) => (
                                <td
                                  key={i}
                                  className={`py-2 px-4 text-right tabular-nums ${i + 1 < activeWeekIndex
                                      ? "bg-salmon/10 text-salmon font-medium"
                                      : "text-gray-900"
                                    }`}
                                >
                                  {fmtDollar(amt)}
                                </td>
                              ))}
                              <td className="py-2 px-4 text-right font-semibold text-gray-900 tabular-nums border-l-2 border-gray-300 bg-navy/5">
                                {fmtDollar(rowTotal)}
                              </td>
                            </tr>
                          ))}
                          <tr className="font-semibold bg-gray-100 border-t-2 border-gray-300 divide-x divide-gray-200">
                            <td className="py-2 px-4 text-navy sticky left-0 bg-gray-100">
                              Total
                            </td>
                            {totals.map((amt, i) => (
                              <td
                                key={i}
                                className="py-2 px-4 text-right text-gray-900 tabular-nums"
                              >
                                {fmtDollar(amt)}
                              </td>
                            ))}
                            <td className="py-2 px-4 text-right font-bold text-navy tabular-nums border-l-2 border-gray-300 bg-navy/10">
                              {fmtDollar(totalSum)}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <ScrollBar orientation="horizontal" />
                  </ScrollArea>
                </div>
              ))
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
