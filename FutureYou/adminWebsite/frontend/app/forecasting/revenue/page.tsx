"use client";

import { useMemo } from "react";
import { RefreshCw, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { getCurrentMonthInfo } from "@/lib/calendar";
import { useRecruiterData } from "@/hooks/forecasting/useRecruiterData";
import { useInvoiceData } from "@/hooks/forecasting/useInvoiceData";
import { useCumulativeActuals } from "@/hooks/forecasting/useCumulativeActuals";
import { useCumulativeForecasts } from "@/hooks/forecasting/useCumulativeForecasts";
import { useMonthlyTargets } from "@/hooks/forecasting/useMonthlyTargets";
import {
  buildRecruiterTogetherByWeek,
  groupRecruitersByAreaWeek,
} from "@/lib/calcHelpers";
import { FC_AUTH } from "@/lib/forecasting-cache";

function fmt(v: number): string {
  return v ? Math.round(v).toLocaleString("en-AU") : "-";
}

function fmtVariance(v: number): React.ReactNode {
  if (v < 0) return <span className="text-salmon">({Math.abs(v).toLocaleString("en-AU")})</span>;
  if (v > 0) return <span>{Math.round(v).toLocaleString("en-AU")}</span>;
  return "-";
}

export default function RevenuePage() {
  const { currentFY, currentMonth, currentWeekIndex, weeksInMonth } = useMemo(
    () => getCurrentMonthInfo(),
    [],
  );
  const weeks = useMemo(() => weeksInMonth.map((w) => w.week), [weeksInMonth]);

  const { allRecruiters, allAreas, summaryMapping, headcountByArea, recruiterToArea, loading: recruiterLoading, error: recruiterError } =
    useRecruiterData();

  const { currentData: invoices, loading: invoiceLoading, error: invoiceError, refresh, lastFetchedAt } =
    useInvoiceData();

  const targetByMonth = useMonthlyTargets(currentFY);

  const { actualsByArea, cumulativeActuals, cumulativeActualsByRecruiter } =
    useCumulativeActuals(currentMonth, currentFY, weeks, allRecruiters, allAreas, invoices);

  const { forecastByAreaForWeek, cumulativeForecastsByRecruiter } =
    useCumulativeForecasts(currentFY, currentMonth, recruiterToArea);

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

  const mtdRevenueByGroup = useMemo(
    () => groupRecruitersByAreaWeek(recruiterTogetherByWeek),
    [recruiterTogetherByWeek],
  );

  const rows = useMemo(
    () =>
      allAreas.map((area) => {
        const forecastThisWeek = forecastByAreaForWeek[area]?.[currentWeekIndex] || 0;
        const actualThisWeek = actualsByArea[area]?.[currentWeekIndex] || 0;
        const mtdRevenue = (cumulativeActuals[area]?.[currentWeekIndex] || 0) + actualThisWeek;
        const forecastMTD = mtdRevenueByGroup[area]?.[currentWeekIndex] || 0;
        const headcount = headcountByArea[area] || 0;
        return {
          area,
          forecastWeek: forecastThisWeek,
          actualWeek: actualThisWeek,
          variance: Math.round(actualThisWeek - forecastThisWeek),
          mtdRevenue,
          forecastMTD,
          headcount,
          forecastPerHead: headcount > 0 ? forecastMTD / headcount : undefined,
          actualPerHead: headcount > 0 ? mtdRevenue / headcount : undefined,
        };
      }),
    [allAreas, forecastByAreaForWeek, actualsByArea, cumulativeActuals, mtdRevenueByGroup, headcountByArea, currentWeekIndex],
  );

  const totals = useMemo(
    () =>
      rows.reduce(
        (acc, r) => ({
          forecastWeek: acc.forecastWeek + r.forecastWeek,
          actualWeek: acc.actualWeek + r.actualWeek,
          variance: acc.variance + r.variance,
          mtdRevenue: acc.mtdRevenue + r.mtdRevenue,
          forecastMTD: acc.forecastMTD + r.forecastMTD,
          headcount: acc.headcount + r.headcount,
        }),
        { forecastWeek: 0, actualWeek: 0, variance: 0, mtdRevenue: 0, forecastMTD: 0, headcount: 0 },
      ),
    [rows],
  );

  const isLoading = recruiterLoading || invoiceLoading;
  const error = recruiterError ?? invoiceError;
  const lastModified = FC_AUTH.getLastModified();

  return (
    <div className="p-6 md:p-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-navy">Revenue Dashboard</h1>
          <p className="text-dark-grey text-sm mt-0.5">
            {currentMonth} — Week {currentWeekIndex} Forecast vs Actual
          </p>
          {targetByMonth[currentMonth] && (
            <p className="text-sm text-dark-grey mt-1">
              Target:{" "}
              <b className="text-navy">${targetByMonth[currentMonth].toLocaleString("en-AU")}</b>
            </p>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={refresh}
          disabled={invoiceLoading}
          className="gap-2 shrink-0"
        >
          <RefreshCw className={`w-4 h-4 ${invoiceLoading ? "animate-spin" : ""}`} />
          Refresh Data
        </Button>
      </div>

      {lastFetchedAt && (
        <p className="text-xs text-dark-grey -mt-4">
          Invoice data cached at{" "}
          <b>{new Date(lastFetchedAt).toLocaleTimeString("en-AU", { hour: "2-digit", minute: "2-digit" })}</b>
          {lastModified && <> · BQ last updated: <b>{lastModified}</b></>}
        </p>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="w-4 h-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-11 w-full" />)}
        </div>
      ) : (
        <ScrollArea className="w-full rounded-lg border border-gray-200">
          <div className="min-w-[900px]">
            <table className="w-full text-sm text-left">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="py-3 px-4 font-semibold text-navy sticky left-0 bg-gray-50"></th>
                  {["Forecast", "Actual", "Variance", "Rev MTD", "Forecast MTD", "Headcount", "Forecast Prod.", "Actual Prod."].map((h) => (
                    <th key={h} className="py-3 px-4 text-right font-semibold text-navy whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.area} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2.5 px-4 font-medium text-gray-900 sticky left-0 bg-white">{r.area}</td>
                    <td className="py-2.5 px-4 text-right text-gray-900 tabular-nums">{fmt(r.forecastWeek)}</td>
                    <td className="py-2.5 px-4 text-right text-gray-900 tabular-nums">{fmt(r.actualWeek)}</td>
                    <td className="py-2.5 px-4 text-right tabular-nums">{fmtVariance(r.variance)}</td>
                    <td className="py-2.5 px-4 text-right text-gray-900 tabular-nums">{fmt(r.mtdRevenue)}</td>
                    <td className="py-2.5 px-4 text-right text-gray-900 tabular-nums">{fmt(r.forecastMTD)}</td>
                    <td className="py-2.5 px-4 text-right text-gray-900">{r.headcount || "-"}</td>
                    <td className="py-2.5 px-4 text-right text-gray-900 tabular-nums">{r.forecastPerHead !== undefined ? fmt(r.forecastPerHead) : "-"}</td>
                    <td className="py-2.5 px-4 text-right text-gray-900 tabular-nums">{r.actualPerHead !== undefined ? fmt(r.actualPerHead) : "-"}</td>
                  </tr>
                ))}
                <tr className="font-bold border-t border-gray-300 bg-gray-50">
                  <td className="py-2.5 px-4 text-navy sticky left-0 bg-gray-50">Total</td>
                  <td className="py-2.5 px-4 text-right text-gray-900 tabular-nums">{fmt(totals.forecastWeek)}</td>
                  <td className="py-2.5 px-4 text-right text-gray-900 tabular-nums">{fmt(totals.actualWeek)}</td>
                  <td className="py-2.5 px-4 text-right tabular-nums">{fmtVariance(Math.round(totals.actualWeek - totals.forecastWeek))}</td>
                  <td className="py-2.5 px-4 text-right text-gray-900 tabular-nums">{fmt(totals.mtdRevenue)}</td>
                  <td className="py-2.5 px-4 text-right text-gray-900 tabular-nums">{fmt(totals.forecastMTD)}</td>
                  <td className="py-2.5 px-4 text-right text-gray-900">{totals.headcount.toFixed(1)}</td>
                  <td className="py-2.5 px-4 text-right text-gray-900 tabular-nums">
                    {totals.headcount > 0 ? fmt(totals.forecastMTD / totals.headcount) : "-"}
                  </td>
                  <td className="py-2.5 px-4 text-right text-gray-900 tabular-nums">
                    {totals.headcount > 0 ? fmt(totals.mtdRevenue / totals.headcount) : "-"}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <ScrollBar orientation="horizontal" />
        </ScrollArea>
      )}
    </div>
  );
}
