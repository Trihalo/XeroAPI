"use client";

import { useEffect, useState, useMemo } from "react";
import { AlertCircle } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { useRecruiterData } from "@/hooks/forecasting/useRecruiterData";
import { fcFetchLegends, type LegendsResponse } from "@/lib/forecasting-api";
import { FC_AUTH } from "@/lib/forecasting-cache";

const QUARTERS = ["Q1", "Q2", "Q3", "Q4"] as const;
const MONTHS   = ["Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar","Apr","May","Jun"] as const;
const CAL_TO_NAME = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

type Quarter = (typeof QUARTERS)[number];
type Month   = (typeof MONTHS)[number];
type TimeView = "Total" | "Quarter" | "Month";
type ViewMode = "Consultant" | "Area";

const FY = "FY26";

export default function LegendsPage() {
  const [revenueData, setRevenueData] = useState<LegendsResponse>({ consultantTotals: [], consultantTypeTotals: [] });
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState<string | null>(null);
  const [timeView, setTimeView]       = useState<TimeView>("Total");
  const [selectedQ, setSelectedQ]     = useState<Quarter>("Q1");
  const [selectedM, setSelectedM]     = useState<Month>("Jul");
  const [viewMode, setViewMode]       = useState<ViewMode>("Consultant");

  const { allRecruiters, loading: recruiterLoading } = useRecruiterData();
  const lastModified = FC_AUTH.getLastModified();

  useEffect(() => {
    setLoading(true);
    fcFetchLegends(FY)
      .then(setRevenueData)
      .catch(() => setError("Failed to load legends data."))
      .finally(() => setLoading(false));
  }, []);

  const { consultantTypeTotals } = revenueData;

  // ── Build lookup maps ─────────────────────────────────────────────────────
  const byQuarter = useMemo(() => {
    const acc: Record<string, Record<string, Record<string, Record<string, number>>>> = {};
    consultantTypeTotals.forEach(({ Consultant, Area, Type, Quarter: Q, TotalMargin }) => {
      acc.consultant ??= {};
      acc.area       ??= {};
      acc.consultant[Consultant] ??= {};
      acc.consultant[Consultant][Q] ??= { Perm: 0, Temp: 0 };
      acc.consultant[Consultant][Q][Type] += TotalMargin;
      acc.area[Area] ??= {};
      acc.area[Area][Q] ??= { Perm: 0, Temp: 0 };
      acc.area[Area][Q][Type] += TotalMargin;
    });
    return acc;
  }, [consultantTypeTotals]);

  const byMonth = useMemo(() => {
    const acc: Record<string, Record<string, Record<string, Record<string, number>>>> = {};
    consultantTypeTotals.forEach((row) => {
      const m: string | null =
        row.MonthName && (MONTHS as readonly string[]).includes(row.MonthName)
          ? row.MonthName
          : typeof row.Month === "number"
            ? CAL_TO_NAME[row.Month - 1]
            : null;
      if (!m) return;
      const { Consultant, Area, Type, TotalMargin } = row;
      acc.consultant ??= {};
      acc.area       ??= {};
      acc.consultant[Consultant] ??= {};
      acc.consultant[Consultant][m] ??= { Perm: 0, Temp: 0 };
      acc.consultant[Consultant][m][Type] += TotalMargin;
      acc.area[Area] ??= {};
      acc.area[Area][m] ??= { Perm: 0, Temp: 0 };
      acc.area[Area][m][Type] += TotalMargin;
    });
    return acc;
  }, [consultantTypeTotals]);

  function getPermTemp(entity: string) {
    const kind = viewMode === "Consultant" ? "consultant" : "area";
    let perm = 0;
    let temp = 0;
    if (timeView === "Total") {
      QUARTERS.forEach((q) => {
        perm += byQuarter?.[kind]?.[entity]?.[q]?.["Perm"] || 0;
        temp += byQuarter?.[kind]?.[entity]?.[q]?.["Temp"] || 0;
      });
    } else if (timeView === "Quarter") {
      perm = byQuarter?.[kind]?.[entity]?.[selectedQ]?.["Perm"] || 0;
      temp = byQuarter?.[kind]?.[entity]?.[selectedQ]?.["Temp"] || 0;
    } else {
      perm = byMonth?.[kind]?.[entity]?.[selectedM]?.["Perm"] || 0;
      temp = byMonth?.[kind]?.[entity]?.[selectedM]?.["Temp"] || 0;
    }
    return { perm, temp, total: perm + temp };
  }

  const uniqueConsultants = useMemo(
    () => Array.from(new Set(consultantTypeTotals.filter((r) => allRecruiters.includes(r.Consultant)).map((r) => r.Consultant))),
    [consultantTypeTotals, allRecruiters],
  );
  const uniqueAreas = useMemo(
    () => Array.from(new Set(consultantTypeTotals.filter((r) => allRecruiters.includes(r.Consultant)).map((r) => r.Area))),
    [consultantTypeTotals, allRecruiters],
  );

  const baseList = viewMode === "Consultant" ? uniqueConsultants : uniqueAreas;
  const sorted   = [...baseList].sort((a, b) => getPermTemp(b).total - getPermTemp(a).total);

  const sumCol = (which: "perm" | "temp" | "total") =>
    Math.round(sorted.reduce((s, e) => s + getPermTemp(e)[which], 0)).toLocaleString("en-AU");

  const isLoading = loading || recruiterLoading;

  const tabBtn = (active: boolean) =>
    `px-3 py-1.5 text-sm rounded-md font-medium transition-colors ${
      active ? "bg-navy text-white" : "bg-gray-100 text-dark-grey hover:bg-gray-200"
    }`;

  return (
    <div className="p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-navy">Legends Table — {FY}</h1>
        <p className="text-dark-grey text-sm mt-0.5">Historical revenue by consultant and area</p>
        {lastModified && (
          <p className="text-xs text-dark-grey mt-1">Data last updated: <b>{lastModified}</b></p>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="w-4 h-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4, 5, 6].map((i) => <Skeleton key={i} className="h-10 w-full max-w-xl" />)}
        </div>
      ) : sorted.length === 0 ? (
        <p className="text-sm text-dark-grey">No data available.</p>
      ) : (
        <>
          {/* Time view selector */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex gap-1">
              {(["Total", "Quarter", "Month"] as const).map((v) => (
                <button
                  key={v}
                  onClick={() => { setTimeView(v); if (v === "Quarter") setSelectedQ("Q1"); if (v === "Month") setSelectedM("Jul"); }}
                  className={tabBtn(timeView === v)}
                >
                  {v}
                </button>
              ))}
            </div>

            {timeView === "Quarter" && (
              <div className="flex gap-1">
                {QUARTERS.map((q) => (
                  <button key={q} onClick={() => setSelectedQ(q)} className={tabBtn(selectedQ === q)}>
                    {q}
                  </button>
                ))}
              </div>
            )}

            {timeView === "Month" && (
              <div className="flex flex-wrap gap-1">
                {MONTHS.map((m) => (
                  <button key={m} onClick={() => setSelectedM(m)} className={tabBtn(selectedM === m)}>
                    {m}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Group by */}
          <div className="flex items-center gap-3">
            <span className="text-sm text-dark-grey">Group by:</span>
            <div className="flex gap-1">
              {(["Consultant", "Area"] as const).map((v) => (
                <button key={v} onClick={() => setViewMode(v)} className={tabBtn(viewMode === v)}>
                  {v}
                </button>
              ))}
            </div>
          </div>

          {/* Table */}
          <ScrollArea className="w-full max-w-xl rounded-lg border border-gray-200">
            <table className="w-full text-sm text-left">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="py-2.5 px-4 font-semibold text-navy">
                    {viewMode === "Consultant" ? "Consultant" : "Area"}
                  </th>
                  <th className="py-2.5 px-4 font-semibold text-navy text-right">Perm</th>
                  <th className="py-2.5 px-4 font-semibold text-navy text-right">Temp</th>
                  <th className="py-2.5 px-4 font-semibold text-navy text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((entity, idx) => {
                  const { perm, temp, total } = getPermTemp(entity);
                  return (
                    <tr key={entity} className={`border-b border-gray-100 ${idx % 2 === 0 ? "bg-white" : "bg-gray-50/50"}`}>
                      <td className="py-2 px-4 whitespace-nowrap">{entity}</td>
                      <td className="py-2 px-4 text-right text-dark-grey">{Math.round(perm).toLocaleString("en-AU")}</td>
                      <td className="py-2 px-4 text-right text-dark-grey">{Math.round(temp).toLocaleString("en-AU")}</td>
                      <td className="py-2 px-4 text-right font-semibold text-navy">{Math.round(total).toLocaleString("en-AU")}</td>
                    </tr>
                  );
                })}
                <tr className="font-semibold bg-gray-50 border-t border-gray-200">
                  <td className="py-2.5 px-4">Total</td>
                  <td className="py-2.5 px-4 text-right">{sumCol("perm")}</td>
                  <td className="py-2.5 px-4 text-right">{sumCol("temp")}</td>
                  <td className="py-2.5 px-4 text-right text-navy">{sumCol("total")}</td>
                </tr>
              </tbody>
            </table>
            <ScrollBar orientation="horizontal" />
          </ScrollArea>
        </>
      )}
    </div>
  );
}
