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
import { FC_AUTH } from "@/lib/forecasting-cache";

function getWeekToWeekMovement(
  data: Record<string, { area: string; weeks: Record<number, number> }>,
  currentWeekIndex: number,
): Record<string, string[]> {
  const movementByArea: Record<string, string[]> = {};
  Object.entries(data).forEach(([recruiter, { area, weeks }]) => {
    const current = weeks[currentWeekIndex] || 0;
    const prev    = weeks[currentWeekIndex - 1] || 0;
    const diff    = current - prev;
    if (!movementByArea[area]) movementByArea[area] = [];
    const firstName = recruiter.split(" ")[0];
    const sign      = diff >= 0 ? "+" : "-";
    const value     = Math.round(Math.abs(diff) / 1000);
    if (value === 0) return;
    movementByArea[area].push(`${firstName} ${sign}${value}K`);
  });
  return movementByArea;
}

export default function ForecastingPage() {
  const router = useRouter();
  const calInfo = useMemo(() => getCurrentMonthInfo(), []);
  const {
    currentMonth, currentFY, weeksInMonth, currentWeekIndex,
    nextMonth, nextMonthFY, nextMonthWeeks,
  } = calInfo;

  const [viewNext, setViewNext] = useState(false);

  const activeMonth     = viewNext ? nextMonth     : currentMonth;
  const activeFY        = viewNext ? nextMonthFY   : currentFY;
  const activeWeeks     = viewNext ? nextMonthWeeks : weeksInMonth;
  // For next month, show all weeks in the summary (no data yet, but forecasts may exist).
  // For current month, only show up to today's week.
  const activeWeekIndex = viewNext
    ? Math.max(...nextMonthWeeks.map((e) => e.week))
    : currentWeekIndex;

  const weeks = useMemo(() => activeWeeks.map((w) => w.week), [activeWeeks]);

  const { loading: recruiterLoading, error: recruiterError, allRecruiters, allAreas, summaryMapping, headcountByArea, recruiterToArea } =
    useRecruiterData();
  const { currentData: invoices, loading: invoiceLoading, error: invoiceError } = useInvoiceData();
  const submitted = useSubmittedRecruiters(activeFY, activeMonth, activeWeekIndex);
  const targetByMonth = useMonthlyTargets(activeFY);

  const { actualsByRecruiterWeek, cumulativeActuals, cumulativeActualsByRecruiter } =
    useCumulativeActuals(activeMonth, activeFY, weeks, allRecruiters, allAreas, invoices);

  const { rawForecastRows, cumulativeForecasts, cumulativeForecastsByRecruiter } =
    useCumulativeForecasts(activeFY, activeMonth, summaryMapping);

  const recruiterTogetherByWeek = useMemo(
    () =>
      buildRecruiterTogetherByWeek({
        allRecruiters,
        recruiterToArea,
        cumulativeActualsByRecruiter,
        cumulativeForecastsByRecruiter,
      }),
    [allRecruiters, recruiterToArea, cumulativeActualsByRecruiter, cumulativeForecastsByRecruiter],
  );

  const movement = useMemo(
    () => getWeekToWeekMovement(recruiterTogetherByWeek, activeWeekIndex),
    [recruiterTogetherByWeek, activeWeekIndex],
  );

  // Aggregated forecasts for summary tab
  const aggregatedForecasts = useMemo(() => {
    const map = initializeWeeklyMap([...allAreas, "Total"], weeks);
    allAreas.forEach((area) => {
      weeks.forEach((week) => {
        const forecast = cumulativeForecasts[area]?.[week] || 0;
        const actual   = cumulativeActuals[area]?.[week] || 0;
        const total    = forecast + actual;
        map[area][week]     = total;
        map["Total"][week] += total;
      });
    });
    return map;
  }, [allAreas, weeks, cumulativeForecasts, cumulativeActuals]);

  // ── View tab data ─────────────────────────────────────────────────────────
  const [forecastData, setForecastData] = useState<
    { title: string; data: { name: string; weeks: number[]; uploadWeek: number }[] }[]
  >([]);
  const [viewLoading, setViewLoading] = useState(false);
  const [viewError, setViewError]     = useState<string | null>(null);
  const hasFetchedView = useRef(false);

  async function fetchViewData() {
    if (!Object.keys(summaryMapping).length || !weeks.length) return;
    setViewLoading(true);
    setViewError(null);
    try {
      const summary = await fcFetchForecastSummary(activeFY, activeMonth);
      const structured = Object.entries(summaryMapping).map(([category, names]) => ({
        title: category,
        data: names.map((name) => {
          const paddedWeeks = weeks.map((weekNum) => {
            const match = summary.find((e) => e.name === name && Number(e.week) === weekNum);
            return match ? Number(match.total_revenue) : 0;
          });
          const latestUpload = summary
            .filter((e) => e.name === name)
            .reduce((max, curr) => (Number(curr.uploadWeek) > Number(max.uploadWeek) ? curr : max), {
              uploadWeek: 0,
            } as { uploadWeek: number });
          return { name, weeks: paddedWeeks, uploadWeek: latestUpload.uploadWeek };
        }),
      }));
      setForecastData(structured);
      hasFetchedView.current = true;
    } catch {
      setViewError("Failed to load detailed forecast data.");
    } finally {
      setViewLoading(false);
    }
  }

  const forecastViewSections = useMemo(() => {
    if (!forecastData.length || !activeWeeks.length || !rawForecastRows.length) return [];
    return forecastData.map((section) => {
      const sectionRows = section.data.map(({ name }) => {
        const allForecasts = rawForecastRows.filter((r) => r.name === name);
        const maxUploadWeek = Math.max(...allForecasts.map((r) => Number(r.uploadWeek || 0)));
        const latestRows    = allForecasts.filter((r) => Number(r.uploadWeek) === maxUploadWeek);
        const paddedWeeks   = activeWeeks.map((w) => {
          const match = latestRows.find((r) => Number(r.week) === w.week);
          return match ? Number(match.total_revenue) : 0;
        });
        const finalWeeks = paddedWeeks.map((amt, i) => {
          const weekNum = i + 1;
          return weekNum < activeWeekIndex ? actualsByRecruiterWeek[name]?.[weekNum] || 0 : amt;
        });
        return { name, finalWeeks, rowTotal: finalWeeks.reduce((a, b) => a + b, 0) };
      });
      const totals   = activeWeeks.map((_, i) => sectionRows.reduce((s, r) => s + (r.finalWeeks[i] || 0), 0));
      const totalSum = totals.reduce((a, b) => a + b, 0);
      return { title: section.title, rows: sectionRows, totals, totalSum };
    });
  }, [forecastData, rawForecastRows, activeWeeks, actualsByRecruiterWeek, activeWeekIndex]);

  const remainingRecruiters = allRecruiters.filter((r) => !submitted.has(r));
  const isAdmin = FC_AUTH.getRole() === "admin";

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
                onClick={() => { setViewNext(isNext); hasFetchedView.current = false; }}
                className={`px-3 py-1.5 text-sm rounded-md font-medium transition-colors ${
                  active ? "bg-navy text-white" : "bg-gray-100 text-dark-grey hover:bg-gray-200"
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
        <TabsList className="mb-2">
          <TabsTrigger value="input">Forecast Input</TabsTrigger>
          <TabsTrigger value="summary">Summary</TabsTrigger>
          <TabsTrigger value="view">Detailed View</TabsTrigger>
        </TabsList>

        {/* ── INPUT TAB ─────────────────────────────────────────────────── */}
        <TabsContent value="input">
          <div className="space-y-4">
            {remainingRecruiters.length > 0 && (
              <p className="text-sm text-dark-grey">
                <span className="font-semibold text-salmon">{remainingRecruiters.length}</span> recruiter
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
                      {[1, 2, 3].map((j) => <Skeleton key={j} className="h-8 w-24 rounded-full" />)}
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
                    <div key={area} className="rounded-xl border border-gray-200 bg-white overflow-hidden">
                      {/* Area header — clicking opens the area upload page */}
                      <button
                        onClick={() => {
                          const params = new URLSearchParams({
                            area,
                            month: activeMonth,
                            fy: activeFY,
                            weekIndex: viewNext ? "1" : String(currentWeekIndex),
                          });
                          router.push(`/forecasting/upload?${params.toString()}`);
                        }}
                        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-100 hover:bg-navy/5 transition-colors group"
                      >
                        <span className="text-sm font-semibold text-navy group-hover:text-navy">
                          {area}
                        </span>
                        <span className={`text-xs font-medium ${allSubmitted ? "text-salmon" : someSubmitted ? "text-dark-grey" : "text-dark-grey"}`}>
                          {allSubmitted
                            ? "All submitted ✓"
                            : someSubmitted
                              ? `${names.filter((n) => submitted.has(n)).length}/${names.length} submitted`
                              : "Open →"}
                        </span>
                      </button>

                      {/* Recruiter list — non-clickable, shows submitted status */}
                      <ul className="px-4 py-3 space-y-1.5">
                        {names.map((name) => (
                          <li key={name} className="flex items-center justify-between text-sm">
                            <span className={submitted.has(name) ? "text-navy font-medium" : "text-dark-grey"}>
                              {name}
                            </span>
                            {submitted.has(name) && (
                              <span className="text-xs font-bold text-salmon">✓</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  );
                })}
              </div>
            )}

            {isAdmin && (
              <div className="flex gap-3 mt-4 pt-4 border-t border-gray-100">
                <button
                  onClick={() => router.push("/forecasting/revenue")}
                  className="text-sm text-navy font-medium underline underline-offset-2"
                >
                  Revenue Dashboard
                </button>
                <button
                  onClick={() => router.push("/forecasting/admin")}
                  className="text-sm text-navy font-medium underline underline-offset-2"
                >
                  Admin Panel
                </button>
                <button
                  onClick={() => router.push("/forecasting/legends")}
                  className="text-sm text-navy font-medium underline underline-offset-2"
                >
                  Legends Table
                </button>
              </div>
            )}
            {!isAdmin && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <button
                  onClick={() => router.push("/forecasting/legends")}
                  className="text-sm text-navy font-medium underline underline-offset-2"
                >
                  Legends Table
                </button>
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
                    ${Math.round(targetByMonth[currentMonth] / 1000).toLocaleString("en-AU")}K
                  </b>
                </span>
              )}
              {remainingRecruiters.length > 0 && (
                <span>
                  Missing:{" "}
                  <b className="text-salmon">{remainingRecruiters.length} recruiters</b>
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
              <ScrollArea className="w-full rounded-lg border border-gray-200">
                <div className="min-w-[700px]">
                  <table className="w-full text-sm text-left">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr className="divide-x divide-gray-200">
                        <th className="text-left py-3 px-4 font-semibold text-navy sticky left-0 bg-gray-50">
                          Area
                        </th>
                        {activeWeeks.map((w) => (
                          <th key={w.week} className="text-right py-3 px-4 font-semibold text-navy whitespace-nowrap">
                            Wk {w.week}
                          </th>
                        ))}
                        <th className="text-right py-3 px-4 font-semibold text-navy">MTD</th>
                        <th className="text-right py-3 px-4 font-semibold text-navy">HC</th>
                        <th className="text-right py-3 px-4 font-semibold text-navy">Prod.</th>
                        <th className="text-right py-3 px-4 font-semibold text-navy">w2w</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(summaryMapping).map(([area]) => {
                        const weekMap  = aggregatedForecasts[area] || {};
                        const headcount = headcountByArea[area] ?? 0;
                        const mtd       = cumulativeActuals?.[area]?.[activeWeekIndex] || 0;
                        const prod      = headcount > 0
                          ? Math.round(weekMap[activeWeekIndex] / (1000 * headcount)).toLocaleString("en-AU")
                          : "-";
                        return (
                          <tr key={area} className="border-b border-gray-200 hover:bg-gray-50 divide-x divide-gray-200">
                            <td className="py-2.5 px-4 text-sm font-medium sticky left-0 bg-white">{area}</td>
                            {activeWeeks.map((w) => (
                              <td key={w.week} className="py-2.5 px-4 text-right text-sm text-dark-grey">
                                {w.week <= activeWeekIndex ? fmtK(weekMap[w.week] || 0) : "-"}
                              </td>
                            ))}
                            <td className="py-2.5 px-4 text-right text-sm">{fmtK(mtd)}</td>
                            <td className="py-2.5 px-4 text-right text-sm">{headcount || "-"}</td>
                            <td className="py-2.5 px-4 text-right text-sm">{prod}</td>
                            <td className="py-2.5 px-4 text-right text-xs text-dark-grey">
                              {movement[area]?.join(", ") || ""}
                            </td>
                          </tr>
                        );
                      })}
                      <tr className="font-bold border-t border-gray-300 bg-gray-50 divide-x divide-gray-200">
                        <td className="py-2.5 px-4 text-sm sticky left-0 bg-gray-50">Total</td>
                        {activeWeeks.map((w) => (
                          <td key={w.week} className="py-2.5 px-4 text-right text-sm">
                            {w.week <= activeWeekIndex
                              ? Math.round((aggregatedForecasts["Total"]?.[w.week] || 0) / 1000).toLocaleString("en-AU")
                              : "-"}
                          </td>
                        ))}
                        <td className="py-2.5 px-4 text-right text-sm">
                          {Math.round((cumulativeActuals["Total"]?.[activeWeekIndex] || 0) / 1000).toLocaleString("en-AU")}
                        </td>
                        <td className="py-2.5 px-4 text-right text-sm">
                          {Object.values(headcountByArea).reduce((a, b) => a + b, 0).toFixed(1)}
                        </td>
                        <td className="py-2.5 px-4 text-right text-sm">
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
              <span className="font-semibold text-salmon">salmon</span> represent actual invoiced revenue.
            </p>

            {viewError && (
              <Alert variant="destructive">
                <AlertCircle className="w-4 h-4" />
                <AlertDescription>
                  {viewError}{" "}
                  <button onClick={fetchViewData} className="underline ml-1">Retry</button>
                </AlertDescription>
              </Alert>
            )}

            {viewLoading ? (
              <div className="space-y-8">
                {[1, 2].map((i) => (
                  <div key={i} className="space-y-2">
                    <Skeleton className="h-5 w-48" />
                    {[1, 2, 3, 4].map((j) => <Skeleton key={j} className="h-9 w-full" />)}
                  </div>
                ))}
              </div>
            ) : forecastViewSections.length === 0 ? (
              <p className="text-sm text-dark-grey">No forecast data available.</p>
            ) : (
              forecastViewSections.map(({ title, rows, totals, totalSum }) => (
                <div key={title}>
                  <h3 className="text-sm font-semibold text-navy mb-2">{title}</h3>
                  <ScrollArea className="w-full rounded-lg border border-gray-200">
                    <div className="min-w-[600px]">
                      <table className="w-full text-sm text-left">
                        <thead className="bg-gray-50 border-b border-gray-200">
                          <tr>
                            <th className="py-2.5 px-4 font-semibold text-navy sticky left-0 bg-gray-50">
                              Name
                            </th>
                            {activeWeeks.map((w) => (
                              <th key={w.week} className="py-2.5 px-4 font-semibold text-navy text-right">
                                Wk {w.week}
                              </th>
                            ))}
                            <th className="py-2.5 px-4 font-semibold text-navy text-right">Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rows.map(({ name, finalWeeks, rowTotal }) => (
                            <tr key={name} className="border-b border-gray-100">
                              <td className="py-2 px-4 sticky left-0 bg-white">{name}</td>
                              {finalWeeks.map((amt, i) => (
                                <td
                                  key={i}
                                  className={`py-2 px-4 text-right ${
                                    i + 1 < activeWeekIndex
                                      ? "bg-salmon/10 text-salmon font-medium"
                                      : ""
                                  }`}
                                >
                                  {fmtDollar(amt)}
                                </td>
                              ))}
                              <td className="py-2 px-4 text-right font-medium">{fmtDollar(rowTotal)}</td>
                            </tr>
                          ))}
                          <tr className="font-semibold bg-gray-50 border-t border-gray-200">
                            <td className="py-2 px-4 sticky left-0 bg-gray-50">Total</td>
                            {totals.map((amt, i) => (
                              <td key={i} className="py-2 px-4 text-right">{fmtDollar(amt)}</td>
                            ))}
                            <td className="py-2 px-4 text-right font-bold">{fmtDollar(totalSum)}</td>
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
