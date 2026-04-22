"use client";

import { Suspense, useState, useEffect, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeft, Lock, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { getCurrentMonthInfo } from "@/lib/calendar";
import { useInvoiceData } from "@/hooks/forecasting/useInvoiceData";
import { useRecruiterData } from "@/hooks/forecasting/useRecruiterData";
import {
  fcFetchForecastForRecruiter,
  fcUploadForecast,
  type ForecastRow,
  type InvoiceRow,
} from "@/lib/forecasting-api";

// ── Per-recruiter invoice panel ───────────────────────────────────────────────

function InvoicePanel({
  name,
  currentData,
  prevData,
  previousMonth,
  currentMonth,
}: {
  name: string;
  currentData: InvoiceRow[];
  prevData: InvoiceRow[];
  previousMonth: string;
  currentMonth: string;
}) {
  const [showPrev, setShowPrev] = useState(false);
  const source = showPrev ? prevData : currentData;

  const list = source
    .filter((inv) => inv.Consultant === name)
    .sort((a, b) => Number(a.Week) - Number(b.Week));

  const permList = list.filter((inv) => inv.Type === "Perm");
  const tempList = list.filter((inv) => inv.Type === "Temp");
  const permTotal = Math.round(permList.reduce((s, inv) => s + (Number(inv.Margin) || 0), 0));
  const tempTotal = Math.round(tempList.reduce((s, inv) => s + (Number(inv.Margin) || 0), 0));

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <span className="text-sm text-dark-grey">
          Showing: <span className="font-medium text-navy">{showPrev ? previousMonth : currentMonth}</span>
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowPrev((v) => !v)}
          className="text-xs h-7"
        >
          {showPrev ? "Show Current Month" : "Show Previous Month"}
        </Button>
      </div>

      {permList.length === 0 && tempTotal === 0 ? (
        <p className="text-sm text-dark-grey">
          No invoice revenue for {showPrev ? previousMonth : currentMonth}.
        </p>
      ) : (
        <div className="overflow-x-auto max-w-2xl">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-dark-grey border-b border-gray-100">
                <th className="text-left py-2 pr-6">Week</th>
                <th className="text-left py-2 pr-6">Inv #</th>
                <th className="text-left py-2 pr-6">Client</th>
                <th className="text-right py-2">Margin</th>
              </tr>
            </thead>
            <tbody>
              {permList.map((inv, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-1.5 pr-6">Wk {inv.Week}</td>
                  <td className="py-1.5 pr-6 text-dark-grey">{inv.InvoiceNumber}</td>
                  <td className="py-1.5 pr-6 text-dark-grey">{inv.ToClient || "-"}</td>
                  <td className="py-1.5 text-right font-medium">
                    ${Math.round(Number(inv.Margin) || 0).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t border-gray-200">
              {tempTotal > 0 && (
                <tr>
                  <td colSpan={3} className="py-1.5 text-right text-dark-grey pr-4 italic text-xs">
                    Temp total:
                  </td>
                  <td className="py-1.5 text-right font-medium">${tempTotal.toLocaleString()}</td>
                </tr>
              )}
              <tr>
                <td colSpan={3} className="py-1.5 text-right font-semibold pr-4">Total Margin:</td>
                <td className="py-1.5 text-right font-semibold text-navy">
                  ${(permTotal + tempTotal).toLocaleString()}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Per-recruiter forecast section ───────────────────────────────────────────

function RecruiterSection({
  name,
  rows,
  currentWeekIndex,
  currentMonth,
  currentData,
  prevData,
  previousMonth,
  invoiceLoading,
  invoiceError,
  isSubmitting,
  isSubmitted,
  onChange,
  onSubmit,
}: {
  name: string;
  rows: ForecastRow[];
  currentWeekIndex: number;
  currentMonth: string;
  currentData: InvoiceRow[];
  prevData: InvoiceRow[];
  previousMonth: string;
  invoiceLoading: boolean;
  invoiceError: string | null;
  isSubmitting: boolean;
  isSubmitted: boolean;
  onChange: (weekIdx: number, field: "revenue" | "tempRevenue" | "notes", value: string) => void;
  onSubmit: () => void;
}) {
  const [invoiceOpen, setInvoiceOpen] = useState(false);

  const actualsByWeek = useMemo(() => {
    const map: Record<string, Record<number, number>> = { Perm: {}, Temp: {} };
    currentData.forEach((inv) => {
      if (inv.Consultant !== name) return;
      const w = Number(inv.Week);
      if (!map[inv.Type]) return;
      map[inv.Type][w] = (map[inv.Type][w] || 0) + Number(inv.Margin || 0);
    });
    return map;
  }, [currentData, name]);

  const sumActualsPast = (type: string) =>
    Object.entries(actualsByWeek[type] || {})
      .filter(([week]) => Number(week) < currentWeekIndex)
      .reduce((sum, [, val]) => sum + val, 0);

  const forecastSum = rows
    .filter((r) => r.week >= currentWeekIndex)
    .reduce((s, r) => s + (Number(r.revenue) || 0) + (Number(r.tempRevenue) || 0), 0);

  const totalProjected = Math.round(sumActualsPast("Perm") + sumActualsPast("Temp") + forecastSum);

  const latestUpload = useMemo(() => {
    const valid = rows.filter((r) => r.uploadTimestamp && r.uploadUser);
    return valid.length ? { time: valid[0].uploadTimestamp, user: valid[0].uploadUser } : null;
  }, [rows]);

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      {/* Recruiter header */}
      <div className="px-5 py-3.5 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
        <h2 className="text-base font-semibold text-navy">{name}</h2>
        {isSubmitted && (
          <span className="text-xs font-semibold text-salmon">✓ Submitted</span>
        )}
      </div>

      <div className="p-5 space-y-4">
        {/* Forecast table */}
        <ScrollArea className="w-full rounded-lg border border-gray-200">
          <div className="min-w-[720px]">
            <table className="w-full text-sm text-left">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="py-2.5 px-4 font-semibold text-navy">Week</th>
                  <th className="py-2.5 px-4 font-semibold text-navy whitespace-nowrap">Date Range</th>
                  <th className="py-2.5 px-4 font-semibold text-navy whitespace-nowrap">Forecast Perm</th>
                  <th className="py-2.5 px-4 font-semibold text-navy whitespace-nowrap">Forecast Temp</th>
                  <th className="py-2.5 px-4 font-semibold text-navy whitespace-nowrap">Actual Perm</th>
                  <th className="py-2.5 px-4 font-semibold text-navy whitespace-nowrap">Actual Temp</th>
                  <th className="py-2.5 px-4 font-semibold text-navy whitespace-nowrap">Actual Total</th>
                  <th className="py-2.5 px-4 font-semibold text-navy">Notes</th>
                  <th className="py-2.5 px-2 w-8" />
                </tr>
              </thead>
              <tbody>
                {rows.map((row, idx) => {
                  const editable = row.week >= currentWeekIndex;
                  const permActual = actualsByWeek["Perm"][row.week] || 0;
                  const tempActual = actualsByWeek["Temp"][row.week] || 0;
                  const totalActual = Math.round(permActual + tempActual);

                  return (
                    <tr key={idx} className={`border-b border-gray-100 ${!editable ? "bg-gray-50" : ""}`}>
                      <td className="py-2.5 px-4 font-medium text-navy">Wk {row.week}</td>
                      <td className="py-2.5 px-4 text-xs text-dark-grey whitespace-nowrap">{row.range}</td>

                      <td className="py-2.5 px-4">
                        <input
                          type="number"
                          className={`w-24 rounded border px-2 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-navy/30 ${!editable ? "opacity-40 cursor-not-allowed bg-gray-100" : "border-gray-200"
                            }`}
                          placeholder="$"
                          value={row.revenue ?? ""}
                          onChange={(e) => editable && onChange(idx, "revenue", e.target.value)}
                          disabled={!editable}
                        />
                      </td>

                      <td className="py-2.5 px-4">
                        <input
                          type="number"
                          className={`w-24 rounded border px-2 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-navy/30 ${!editable ? "opacity-40 cursor-not-allowed bg-gray-100" : "border-gray-200"
                            }`}
                          placeholder="$"
                          value={row.tempRevenue ?? ""}
                          onChange={(e) => editable && onChange(idx, "tempRevenue", e.target.value)}
                          disabled={!editable}
                        />
                      </td>

                      <td className={`py-2.5 px-4 text-right text-sm ${!editable ? "opacity-40" : ""}`}>
                        {permActual ? Math.round(permActual).toLocaleString() : "-"}
                      </td>

                      <td className={`py-2.5 px-4 text-right text-sm ${!editable ? "opacity-40" : ""}`}>
                        {tempActual ? Math.round(tempActual).toLocaleString() : "-"}
                      </td>

                      <td className={`py-2.5 px-4 text-right text-sm ${!editable ? "" : "text-dark-grey"}`}>
                        {!editable ? (
                          <span className={totalActual < 0 ? "text-salmon" : ""}>
                            {totalActual < 0
                              ? `(${Math.abs(totalActual).toLocaleString()})`
                              : totalActual
                                ? totalActual.toLocaleString()
                                : "-"}
                          </span>
                        ) : "-"}
                      </td>

                      <td className="py-2.5 px-4">
                        <input
                          type="text"
                          className={`w-48 rounded border px-2 py-1 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-navy/30 ${!editable ? "opacity-40 cursor-not-allowed bg-gray-100" : "border-gray-200"
                            }`}
                          placeholder="Optional notes"
                          value={row.notes ?? ""}
                          onChange={(e) => editable && onChange(idx, "notes", e.target.value)}
                          disabled={!editable}
                        />
                      </td>

                      <td className="py-2.5 px-2 text-center">
                        {!editable && <Lock className="w-3.5 h-3.5 text-gray-300 mx-auto" />}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <ScrollBar orientation="horizontal" />
        </ScrollArea>

        {latestUpload && (
          <p className="text-xs text-dark-grey">
            Last updated at <b>{latestUpload.time}</b> by <b>{latestUpload.user}</b>
          </p>
        )}

        {/* Summary line */}
        <div className="text-sm text-dark-grey bg-gray-50 rounded-lg px-4 py-3 border border-gray-100">
          <span className="font-semibold text-navy">{name.split(" ")[0]}&apos;s {currentMonth} Forecast: </span>
          <span>{Math.round(sumActualsPast("Perm")).toLocaleString()} (Perm Actual) + </span>
          <span>{Math.round(sumActualsPast("Temp")).toLocaleString()} (Temp Actual) + </span>
          <span>{Math.round(forecastSum).toLocaleString()} (Forecast) = </span>
          <span className="text-navy font-bold text-base">${totalProjected.toLocaleString()}</span>
        </div>

        {/* Invoice collapsible */}
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <button
            onClick={() => setInvoiceOpen((v) => !v)}
            className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium text-navy bg-gray-50 hover:bg-gray-100 transition-colors"
          >
            <span>Actual Invoiced Revenue</span>
            {invoiceOpen
              ? <ChevronUp className="w-4 h-4 text-dark-grey" />
              : <ChevronDown className="w-4 h-4 text-dark-grey" />}
          </button>
          {invoiceOpen && (
            <div className="p-4">
              {invoiceLoading ? (
                <Skeleton className="h-24 w-full" />
              ) : invoiceError ? (
                <Alert variant="destructive">
                  <AlertCircle className="w-4 h-4" />
                  <AlertDescription>{invoiceError}</AlertDescription>
                </Alert>
              ) : (
                <InvoicePanel
                  name={name}
                  currentData={currentData}
                  prevData={prevData}
                  previousMonth={previousMonth}
                  currentMonth={currentMonth}
                />
              )}
            </div>
          )}
        </div>

        {/* Submit button */}
        <Button
          onClick={onSubmit}
          disabled={isSubmitting || isSubmitted}
          className="bg-salmon hover:bg-salmon/90 text-white"
        >
          {isSubmitting ? (
            <><RefreshCw className="w-4 h-4 mr-2 animate-spin" />Uploading…</>
          ) : isSubmitted ? (
            "✓ Submitted"
          ) : (
            `Upload ${name.split(" ")[0]}'s Forecast`
          )}
        </Button>
      </div>
    </div>
  );
}

// ── Main upload content ───────────────────────────────────────────────────────

function UploadContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const area = searchParams.get("area") ?? "";

  const calInfo = useMemo(() => getCurrentMonthInfo(), []);

  // Use URL params if provided (e.g. next-month upload), otherwise fall back to current month
  const activeFY = searchParams.get("fy") ?? calInfo.currentFY;
  const activeMonth = searchParams.get("month") ?? calInfo.currentMonth;
  const activeWeekIndex = Number(searchParams.get("weekIndex") ?? calInfo.currentWeekIndex);
  const weeksInMonth = activeFY === calInfo.currentFY && activeMonth === calInfo.currentMonth
    ? calInfo.weeksInMonth
    : activeFY === calInfo.nextMonthFY && activeMonth === calInfo.nextMonth
      ? calInfo.nextMonthWeeks
      : calInfo.weeksInMonth;
  const previousMonth = calInfo.previousMonth;

  const { summaryMapping, loading: recruiterLoading } = useRecruiterData();
  const { currentData, prevData, loading: invoiceLoading, error: invoiceError } = useInvoiceData();

  const recruitersInArea = useMemo(
    () => (area && summaryMapping[area] ? summaryMapping[area] : []),
    [area, summaryMapping],
  );

  const [allRows, setAllRows] = useState<Record<string, ForecastRow[]>>({});
  const [fetching, setFetching] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<Set<string>>(new Set());
  const [submitted, setSubmitted] = useState<Set<string>>(new Set());

  // Fetch forecasts for all recruiters in area in parallel
  useEffect(() => {
    if (!recruitersInArea.length) {
      setFetching(false);
      return;
    }
    setFetching(true);
    setFetchError(null);
    setAllRows({});
    Promise.all(
      recruitersInArea.map((name) =>
        fcFetchForecastForRecruiter(name, activeFY, activeMonth, weeksInMonth).then((rows) => ({
          name,
          rows: rows.map((row) => ({
            ...row,
            uploadMonth: activeMonth,
            uploadWeek: activeWeekIndex,
            uploadYear: activeFY,
          })),
        })),
      ),
    )
      .then((results) => {
        const map: Record<string, ForecastRow[]> = {};
        results.forEach(({ name, rows }) => { map[name] = rows; });
        setAllRows(map);
      })
      .catch(() => setFetchError("Failed to load existing forecast data."))
      .finally(() => setFetching(false));
  }, [recruitersInArea, activeFY, activeMonth, activeWeekIndex, weeksInMonth]);

  function handleChange(
    name: string,
    weekIdx: number,
    field: "revenue" | "tempRevenue" | "notes",
    value: string,
  ) {
    setAllRows((prev) => {
      const rows = [...(prev[name] ?? [])];
      rows[weekIdx] = { ...rows[weekIdx], [field]: value };
      return { ...prev, [name]: rows };
    });
  }

  async function handleSubmit(name: string) {
    setSubmitting((prev) => new Set(prev).add(name));
    try {
      const result = await fcUploadForecast(allRows[name] ?? []);
      if (result.success) {
        toast.success(result.message ?? `${name.split(" ")[0]}'s forecast uploaded.`);
        setSubmitted((prev) => new Set(prev).add(name));
      } else {
        toast.error(result.error ?? "Upload failed.");
      }
    } catch {
      toast.error("Failed to connect to server.");
    } finally {
      setSubmitting((prev) => { const s = new Set(prev); s.delete(name); return s; });
    }
  }

  if (!area) {
    return (
      <div className="p-8">
        <p className="text-dark-grey text-sm">No area specified.</p>
        <Button variant="ghost" onClick={() => router.back()} className="mt-4">
          <ArrowLeft className="w-4 h-4 mr-2" /> Go Back
        </Button>
      </div>
    );
  }

  const isLoading = recruiterLoading || fetching;

  return (
    <div className="p-6 md:p-8 space-y-6">
      {/* Header */}
      <div>
        <button
          onClick={() => router.back()}
          className="text-sm text-dark-grey hover:text-navy flex items-center gap-1 mb-1"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back
        </button>
        <h1 className="text-xl sm:text-2xl font-bold text-navy">
          {activeFY} {activeMonth} — Forecast Upload
        </h1>
        <p className="text-sm text-dark-grey mt-0.5">
          Area: <span className="font-semibold text-navy">{area}</span>
        </p>
      </div>

      {fetchError && (
        <Alert variant="destructive">
          <AlertCircle className="w-4 h-4" />
          <AlertDescription>{fetchError}</AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="space-y-6">
          {[1, 2].map((i) => (
            <div key={i} className="rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-5 py-3.5 bg-gray-50 border-b border-gray-100">
                <Skeleton className="h-5 w-36" />
              </div>
              <div className="p-5 space-y-3">
                {[1, 2, 3, 4].map((j) => <Skeleton key={j} className="h-11 w-full" />)}
              </div>
            </div>
          ))}
        </div>
      ) : recruitersInArea.length === 0 ? (
        <p className="text-sm text-dark-grey">No recruiters found for this area.</p>
      ) : (
        <div className="space-y-8">
          {recruitersInArea.map((name) => (
            <RecruiterSection
              key={name}
              name={name}
              rows={allRows[name] ?? []}
              currentWeekIndex={activeWeekIndex}
              currentMonth={activeMonth}
              currentData={currentData}
              prevData={prevData}
              previousMonth={previousMonth}
              invoiceLoading={invoiceLoading}
              invoiceError={invoiceError}
              isSubmitting={submitting.has(name)}
              isSubmitted={submitted.has(name)}
              onChange={(weekIdx, field, value) => handleChange(name, weekIdx, field, value)}
              onSubmit={() => handleSubmit(name)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function UploadPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 space-y-4">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-40" />
          <div className="space-y-2 mt-6">
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-11 w-full" />)}
          </div>
        </div>
      }
    >
      <UploadContent />
    </Suspense>
  );
}
