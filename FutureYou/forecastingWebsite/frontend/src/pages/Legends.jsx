import { useEffect, useState } from "react";
import TopNavbar from "../components/TopNavbar.jsx";
import { fetchLegendsRevenue } from "../api.js";
import { useRecruiterData } from "../hooks/useRecruiterData.js";

function Legends() {
  const [revenueData, setRevenueData] = useState({});
  const [loading, setLoading] = useState(true);
  const lastUpdatedTime = localStorage.getItem(
    "revenue_table_last_modified_time"
  );
  const fy = "FY26";

  const { allRecruiters, loading: recruiterLoading } = useRecruiterData();

  // View state
  const [timeView, setTimeView] = useState("Total"); // "Total" | "Quarter" | "Month"
  const [selectedQuarter, setSelectedQuarter] = useState("Q1");
  const [selectedMonth, setSelectedMonth] = useState("Jul");
  const [viewMode, setViewMode] = useState("Consultant"); // "Consultant" | "Area"

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      const data = await fetchLegendsRevenue(fy);
      setRevenueData(data);
      setLoading(false);
    };
    loadData();
  }, [fy]);

  const { consultantTypeTotals = [] } = revenueData;
  const isLoading = loading || recruiterLoading;

  // ---------- Lookups ----------
  const QUARTERS = ["Q1", "Q2", "Q3", "Q4"];
  const MONTHS = [
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
  ];
  const CAL_TO_NAME = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];

  const normalizeMonthKey = (row) => {
    if (row.MonthName && MONTHS.includes(row.MonthName)) return row.MonthName;
    if (typeof row.Month === "number") return CAL_TO_NAME[row.Month - 1]; // 1..12
    return null;
  };

  // Quarter lookup
  const byQuarter = consultantTypeTotals.reduce((acc, row) => {
    const { Consultant, Area, Type, Quarter, TotalMargin } = row;
    acc.consultant ??= {};
    acc.area ??= {};
    // consultant
    acc.consultant[Consultant] ??= {};
    acc.consultant[Consultant][Quarter] ??= { Perm: 0, Temp: 0 };
    acc.consultant[Consultant][Quarter][Type] += TotalMargin;
    // area
    acc.area[Area] ??= {};
    acc.area[Area][Quarter] ??= { Perm: 0, Temp: 0 };
    acc.area[Area][Quarter][Type] += TotalMargin;
    return acc;
  }, {});

  // Month lookup
  const byMonth = consultantTypeTotals.reduce((acc, row) => {
    const m = normalizeMonthKey(row);
    if (!m) return acc;
    const { Consultant, Area, Type, TotalMargin } = row;
    acc.consultant ??= {};
    acc.area ??= {};
    // consultant
    acc.consultant[Consultant] ??= {};
    acc.consultant[Consultant][m] ??= { Perm: 0, Temp: 0 };
    acc.consultant[Consultant][m][Type] += TotalMargin;
    // area
    acc.area[Area] ??= {};
    acc.area[Area][m] ??= { Perm: 0, Temp: 0 };
    acc.area[Area][m][Type] += TotalMargin;
    return acc;
  }, {});

  // ---------- Helpers to read the active view ----------
  const getFY = (kind, entity, type) =>
    QUARTERS.reduce(
      (s, q) => s + (byQuarter[kind]?.[entity]?.[q]?.[type] || 0),
      0
    );

  const getQuarter = (kind, entity, type) =>
    byQuarter[kind]?.[entity]?.[selectedQuarter]?.[type] || 0;

  const getMonth = (kind, entity, type) =>
    byMonth[kind]?.[entity]?.[selectedMonth]?.[type] || 0;

  const getPermTempForEntity = (entity) => {
    const kind = viewMode === "Consultant" ? "consultant" : "area";
    const read =
      timeView === "Total"
        ? (t) => getFY(kind, entity, t)
        : timeView === "Quarter"
        ? (t) => getQuarter(kind, entity, t)
        : (t) => getMonth(kind, entity, t);

    const perm = read("Perm");
    const temp = read("Temp");
    return { perm, temp, total: perm + temp };
  };

  // ---------- Lists & sorting ----------
  const uniqueConsultants = Array.from(
    new Set(
      consultantTypeTotals
        .filter((row) => allRecruiters.includes(row.Consultant))
        .map((row) => row.Consultant)
    )
  );

  const uniqueAreas = Array.from(
    new Set(
      consultantTypeTotals
        .filter((row) => allRecruiters.includes(row.Consultant))
        .map((row) => row.Area)
    )
  );

  const baseList = viewMode === "Consultant" ? uniqueConsultants : uniqueAreas;

  const sortedEntities = [...baseList].sort((a, b) => {
    const ta = getPermTempForEntity(a).total;
    const tb = getPermTempForEntity(b).total;
    return tb - ta;
  });

  // Totals row helpers
  const sumColumn = (which /* "Perm" | "Temp" | "Total" */) =>
    Math.round(
      sortedEntities.reduce((s, e) => {
        const { perm, temp, total } = getPermTempForEntity(e);
        return s + (which === "Perm" ? perm : which === "Temp" ? temp : total);
      }, 0)
    ).toLocaleString("en-AU");

  // ---------- UI ----------
  return (
    <div className="min-h-screen bg-base-300 text-base-content flex flex-col">
      <TopNavbar userName={localStorage.getItem("name") || "User"} />

      <div className="flex-1 p-8">
        <div className="bg-base-100 rounded-xl shadow p-12 relative mb-15">
          <h1 className="text-2xl font-bold mb-10">Legends Table - {fy}</h1>

          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-10">
              <div className="w-6 h-6 border-4 border-gray-300 border-t-primary rounded-full animate-spin" />
              <p className="mt-2 text-gray-500 text-sm">
                Loading legends table...
              </p>
            </div>
          ) : sortedEntities.length === 0 ? (
            <div>No data available.</div>
          ) : (
            <>
              {/* Time view selector */}
              <div className="mb-6 flex flex-wrap items-center gap-3">
                <div className="btn-group">
                  {["Total", "Quarter", "Month"].map((label) => (
                    <button
                      key={label}
                      onClick={() => {
                        setTimeView(label);
                        if (label === "Quarter") setSelectedQuarter("Q1");
                        if (label === "Month") setSelectedMonth("Jul");
                      }}
                      className={`btn btn-sm ${
                        timeView === label ? "bg-secondary text-white" : ""
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {timeView === "Quarter" && (
                  <div className="ml-2 flex gap-2">
                    {QUARTERS.map((q) => (
                      <button
                        key={q}
                        onClick={() => setSelectedQuarter(q)}
                        className={`btn btn-sm ${
                          selectedQuarter === q
                            ? "bg-secondary text-white"
                            : "bg-base-300 text-base-content"
                        }`}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                )}

                {timeView === "Month" && (
                  <div className="ml-2 flex gap-2">
                    {MONTHS.map((m) => (
                      <button
                        key={m}
                        onClick={() => setSelectedMonth(m)}
                        className={`btn btn-sm ${
                          selectedMonth === m
                            ? "bg-secondary text-white"
                            : "bg-base-300 text-base-content"
                        }`}
                      >
                        {m}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Group by */}
              <div className="mb-6 flex gap-4 items-center">
                <div className="flex items-center gap-2">
                  <span className="text-sm">Group By:</span>
                  <div className="btn-group">
                    <button
                      className={`btn btn-sm gap-1 ${
                        viewMode === "Consultant"
                          ? "bg-secondary text-white"
                          : ""
                      }`}
                      onClick={() => setViewMode("Consultant")}
                    >
                      Consultant
                    </button>
                    <button
                      className={`btn btn-sm gap-1 ${
                        viewMode === "Area" ? "bg-secondary text-white" : ""
                      }`}
                      onClick={() => setViewMode("Area")}
                    >
                      Area
                    </button>
                  </div>
                </div>
              </div>

              {/* Single compact table that adapts to the active view */}
              <div className="w-full max-w-2xl overflow-x-auto rounded-lg border border-gray-200 mb-6">
                <table className="min-w-full table-fixed text-sm text-left">
                  <thead className="bg-base-300 text-base-content border-gray-200">
                    <tr>
                      <th className="w-2/5 py-2 px-4 whitespace-nowrap">
                        {viewMode === "Consultant" ? "Consultant" : "Area"}
                      </th>
                      <th className="w-1/5 py-2 px-4 text-right whitespace-nowrap">
                        Perm
                      </th>
                      <th className="w-1/5 py-2 px-4 text-right whitespace-nowrap">
                        Temp
                      </th>
                      <th className="w-1/5 py-2 px-4 text-right whitespace-nowrap">
                        Total
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedEntities.map((entity, index) => {
                      const { perm, temp, total } =
                        getPermTempForEntity(entity);
                      return (
                        <tr
                          key={entity}
                          className={`border-b border-gray-200 ${
                            index % 2 === 0 ? "bg-base-100" : "bg-base-200"
                          }`}
                        >
                          <td className="py-2 px-4 whitespace-nowrap">
                            {entity}
                          </td>
                          <td className="py-2 px-4 text-right whitespace-nowrap">
                            {Math.round(perm).toLocaleString("en-AU")}
                          </td>
                          <td className="py-2 px-4 text-right whitespace-nowrap">
                            {Math.round(temp).toLocaleString("en-AU")}
                          </td>
                          <td className="py-2 px-4 text-right font-semibold whitespace-nowrap">
                            {Math.round(total).toLocaleString("en-AU")}
                          </td>
                        </tr>
                      );
                    })}
                    <tr className="font-semibold bg-base-300 border-t border-gray-300">
                      <td className="py-2 px-4 whitespace-nowrap">Total</td>
                      <td className="py-2 px-4 text-right whitespace-nowrap">
                        {sumColumn("Perm")}
                      </td>
                      <td className="py-2 px-4 text-right whitespace-nowrap">
                        {sumColumn("Temp")}
                      </td>
                      <td className="py-2 px-4 text-right whitespace-nowrap">
                        {sumColumn("Total")}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {lastUpdatedTime && (
                <div className="text-sm text-gray-500 mt-1">
                  Actual data last updated: <b>{lastUpdatedTime}</b>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <div className="text-gray-400 p-5 text-right text-sm">
        For any issues, please contact{" "}
        <a href="mailto:leoshi@future-you.com.au" className="underline">
          leoshi@future-you.com.au
        </a>
      </div>
    </div>
  );
}

export default Legends;
