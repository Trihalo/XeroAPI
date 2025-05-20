import React, { useState, useEffect, useRef, useMemo } from "react";
import TopNavbar from "../components/TopNavbar";
import { useRecruiterData } from "../hooks/useRecruiterData";
import { useNavigate } from "react-router-dom";
import calendar from "../data/calendar";
import { getCurrentMonthInfo } from "../utils/getCurrentMonthInfo";
import { fetchForecastSummary } from "../api";
import { useSubmittedRecruiters } from "../hooks/useSubmittedRecruiters";
import { useCumulativeActuals } from "../hooks/useCumulativeActuals";
import { useCumulativeForecasts } from "../hooks/useCumulativeForecasts";
import { buildRecruiterTogetherByWeek } from "../utils/calcHelpers";
import { useMonthlyTargets } from "../hooks/useMonthlyTargets";

// --- 🔧 Utility Functions ---
const initializeWeeklyMap = (keys, weeks) => {
  const map = {};
  keys.forEach((key) => {
    map[key] = {};
    weeks.forEach((w) => {
      map[key][w] = 0;
    });
  });
  return map;
};

const initializeTotalRow = (weeks) =>
  weeks.reduce((acc, w) => {
    acc[w] = 0;
    return acc;
  }, {});

const RenderKValue = ({ value }) => (
  <td className="py-2 px-4 text-sm text-right border-l border-gray-200">
    {value > 0 ? Math.round(value / 1000).toLocaleString("en-AU") : "-"}
  </td>
);

const getWeekToWeekMovement = (data, currentWeekIndex) => {
  const movementByArea = {};

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
};

// --- 📦 Main Component ---
function ForecastMain() {
  const [activeTab, setActiveTab] = useState("input");
  const [forecastData, setForecastData] = useState([]);

  const { currentMonth, currentFY, weeksInMonth, currentWeekIndex } = useMemo(
    () => getCurrentMonthInfo(calendar),
    [calendar]
  );

  const weeks = useMemo(() => weeksInMonth.map((w) => w.week), [weeksInMonth]);

  const submittedRecruiters = useSubmittedRecruiters();

  const { summaryMapping, allRecruiters, allAreas, headcountByArea } =
    useRecruiterData();

  const remainingRecruiters = allRecruiters.filter(
    (recruiter) => !submittedRecruiters.has(recruiter)
  );

  const recruiterToArea = {};
  Object.entries(summaryMapping).forEach(([area, recruiters]) => {
    recruiters.forEach((recruiter) => {
      recruiterToArea[recruiter] = area;
    });
  });

  // --- 🧮 Actuals by Recruiter & Area ---
  const {
    actualsByRecruiterWeek,
    cumulativeActuals,
    cumulativeActualsByRecruiter,
  } = useCumulativeActuals(
    currentMonth,
    currentFY,
    weeks,
    allRecruiters,
    allAreas
  );

  const {
    rawForecastRows,
    cumulativeForecasts,
    cumulativeForecastsByRecruiter,
  } = useCumulativeForecasts(currentFY, currentMonth, summaryMapping);

  const recruiterTogetherByWeek = buildRecruiterTogetherByWeek({
    allRecruiters,
    recruiterToArea,
    cumulativeActualsByRecruiter,
    cumulativeForecastsByRecruiter,
  });

  const movement = getWeekToWeekMovement(
    recruiterTogetherByWeek,
    currentWeekIndex
  );

  // --- 📤 Load Forecast Data ---
  const hasFetched = useRef(false);

  useEffect(() => {
    if (hasFetched.current) return;
    if (!summaryMapping || weeks.length === 0) return;

    const fetchData = async () => {
      const summary = await fetchForecastSummary(currentFY, currentMonth);
      const structured = Object.entries(summaryMapping).map(
        ([category, recruiters]) => ({
          title: category,
          data: recruiters.map((name) => {
            const paddedWeeks = weeks.map((weekNum) => {
              const match = summary.find(
                (e) => e.name === name && Number(e.week) === weekNum
              );
              return match ? Number(match.total_revenue) : 0;
            });

            const latestUpload = summary
              .filter((e) => e.name === name)
              .reduce(
                (max, curr) =>
                  Number(curr.uploadWeek) > Number(max.uploadWeek) ? curr : max,
                { uploadWeek: 0 }
              );

            return {
              name,
              weeks: paddedWeeks,
              uploadWeek: latestUpload.uploadWeek,
            };
          }),
        })
      );

      setForecastData(structured);
      hasFetched.current = true;
    };

    fetchData();
  }, [currentFY, currentMonth, summaryMapping, weeks]);

  const forecastViewSections = useMemo(() => {
    if (!forecastData.length || !weeksInMonth.length || !rawForecastRows.length)
      return [];

    return forecastData.map((section) => {
      const sectionRows = section.data.map(({ name }) => {
        const allForecasts = rawForecastRows.filter((r) => r.name === name);
        const maxUploadWeek = Math.max(
          ...allForecasts.map((r) => Number(r.uploadWeek || 0))
        );
        const latestRows = allForecasts.filter(
          (r) => Number(r.uploadWeek) === maxUploadWeek
        );

        const paddedWeeks = weeksInMonth.map((w) => {
          const match = latestRows.find((r) => Number(r.week) === w.week);
          return match ? Number(match.total_revenue) : 0;
        });

        const finalWeeks = paddedWeeks.map((amt, i) => {
          const weekNum = i + 1;
          return weekNum < currentWeekIndex
            ? actualsByRecruiterWeek[name]?.[weekNum] || 0
            : amt;
        });

        const rowTotal = finalWeeks.reduce((a, b) => a + b, 0);
        return { name, finalWeeks, rowTotal };
      });

      const sectionTotals = weeksInMonth.map((_, i) =>
        sectionRows.reduce((sum, row) => sum + (row.finalWeeks[i] || 0), 0)
      );
      const totalSum = sectionTotals.reduce((a, b) => a + b, 0);

      return {
        title: section.title,
        rows: sectionRows,
        totals: sectionTotals,
        totalSum,
      };
    });
  }, [
    forecastData,
    rawForecastRows,
    weeksInMonth,
    actualsByRecruiterWeek,
    currentWeekIndex,
  ]);

  const targetByMonth = useMonthlyTargets(currentFY);

  // --- 🧮 Aggregated Forecasts ---
  const aggregatedForecasts = initializeWeeklyMap(allAreas, weeks);
  aggregatedForecasts["Total"] = initializeTotalRow(weeks);

  Object.keys(aggregatedForecasts).forEach((area) => {
    if (area === "Total") return;

    weeks.forEach((week) => {
      const forecast = cumulativeForecasts[area]?.[week] || 0;
      const actual = cumulativeActuals[area]?.[week] || 0;
      const total = forecast + actual;

      aggregatedForecasts[area][week] = total;
      aggregatedForecasts["Total"][week] += total;
    });
  });

  // --- ✅ UI Render ---
  return (
    <div className="min-h-screen bg-gray-200 text-base-content flex flex-col">
      <TopNavbar userName={localStorage.getItem("name") || "User"} />
      <div className="flex-1 p-8">
        <div className="max-w-full mx-auto bg-white rounded-xl shadow px-4 sm:px-4 md:px-10 py-6 md:pb-20 relative">
          <div className="flex justify-between items-start mb-6">
            <h1 className="text-2xl font-bold text-primary">
              Recruiter Forecasts
            </h1>
          </div>

          <div className="flex flex-wrap justify-start gap-4 mb-15">
            {["input", "summary", "view"].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded-lg shadow transition min-w-[250px] ${
                  activeTab === tab
                    ? "bg-secondary text-white font-semibold"
                    : "bg-gray-200 text-gray-800 font-medium hover:bg-gray-300"
                }`}
              >
                {tab === "input"
                  ? "Forecast Input"
                  : tab === "view"
                  ? "Detailed Forecasts"
                  : "Forecast Summary"}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          {activeTab === "input" && (
            <div>
              <h2 className="text-xl font-semibold text-primary mb-10">
                Forecast Input
              </h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {Object.entries(summaryMapping).map(([category, names]) => (
                  <Section key={category} title={category} names={names} />
                ))}
              </div>
            </div>
          )}
          {activeTab === "view" && (
            <div className="text-gray-800 text-sm space-y-12">
              <h2 className="text-xl font-semibold text-primary mb-10">
                {currentFY} {currentMonth} Latest Forecasts
              </h2>
              <p className="text-sm text-gray-400 mb-10">
                Red highlight represents actual invoiced revenue
              </p>

              {forecastViewSections.length === 0 ? (
                <p className="text-center text-gray-500">
                  Loading forecast data...
                </p>
              ) : (
                forecastViewSections.map(
                  ({ title, rows, totals, totalSum }) => (
                    <div key={title}>
                      <h3 className="text-lg font-semibold mb-3">{title}</h3>
                      <div className="overflow-x-auto border border-gray-200 mb-6 rounded-lg">
                        <table className="table-fixed min-w-full text-sm text-left border-collapse border-gray-200">
                          <thead className="bg-gray-100 text-gray-700 border-gray-200">
                            <tr>
                              <th className="w-1/6 py-2 px-4 font-semibold">
                                Name
                              </th>
                              {weeksInMonth.map((week) => (
                                <th
                                  key={week.week}
                                  className="w-1/12 py-2 px-4 font-semibold"
                                >
                                  Wk {week.week}
                                </th>
                              ))}
                              <th className="w-1/12 py-2 px-4 font-semibold">
                                Total
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {rows.map(({ name, finalWeeks, rowTotal }) => (
                              <tr
                                key={name}
                                className="border-b border-gray-200"
                              >
                                <td className="py-2 px-4">{name}</td>
                                {finalWeeks.map((amt, i) => (
                                  <td
                                    key={i}
                                    className={`py-2 px-4 text-left ${
                                      i + 1 < currentWeekIndex
                                        ? "bg-accent border-x border-gray-200"
                                        : "border-x border-gray-200"
                                    }`}
                                  >
                                    {amt > 0
                                      ? Math.round(amt).toLocaleString()
                                      : "-"}
                                  </td>
                                ))}
                                <td className="py-2 px-4 text-left font-medium">
                                  {Math.round(rowTotal).toLocaleString()}
                                </td>
                              </tr>
                            ))}

                            <tr className="font-semibold text-black bg-gray-100">
                              <td className="py-2 px-4">Total</td>
                              {totals.map((amt, i) => (
                                <td key={i} className="py-2 px-4 text-left">
                                  {Math.round(amt).toLocaleString()}
                                </td>
                              ))}
                              <td className="py-2 px-4 text-left">
                                {Math.round(totalSum).toLocaleString()}
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )
                )
              )}
            </div>
          )}
          {activeTab === "summary" && (
            <div className="text-gray-800 text-md space-y-6">
              <h2 className="text-xl font-semibold text-primary">
                {currentFY} {currentMonth} Summary
              </h2>
              <p className="text-md text-gray-600 font-medium">
                Target{" "}
                <span className="font-bold ml-21">
                  $
                  {Math.round(
                    targetByMonth[currentMonth] / 1000
                  )?.toLocaleString("en-AU")}
                  K
                </span>
              </p>
              {remainingRecruiters.length > 0 && (
                <p className="text-sm text-gray-600 font-medium">
                  Missing forecasts{" "}
                  <span className="font-bold ml-5">
                    {remainingRecruiters.length} Recruiters
                  </span>
                  <span className="ml-2 text-gray-500">
                    (
                    {remainingRecruiters
                      .map((name) => name.split(" ")[0])
                      .join(", ")}
                    )
                  </span>
                </p>
              )}

              <div className="overflow-x-auto border border-gray-300 mb-6 rounded-lg">
                <table className="table table-sm text-sm min-w-full border-collapse">
                  <thead className="bg-gray-100 text-gray-700">
                    <tr>
                      <th className="text-left py-2 px-4">Area</th>
                      {weeksInMonth.map((w) => (
                        <th key={w.week} className="text-right py-2 px-4">
                          Wk {w.week}
                        </th>
                      ))}
                      <th className="text-right py-2 px-4">MTD Invoiced</th>
                      <th className="text-right py-2 px-4">Headcount</th>
                      <th className="text-right">Forecasted Productivity</th>
                      <th className="text-right py-2 px-4">w2w Movement</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(summaryMapping).map(([area]) => {
                      const weekMap = aggregatedForecasts[area] || {};
                      const headcount = headcountByArea[area] ?? "-";
                      const mtd =
                        cumulativeActuals?.[area]?.[currentWeekIndex] || 0;

                      return (
                        <tr key={area} className="border-gray-100">
                          <td className="py-2 px-4 text-sm">{area}</td>
                          {weeksInMonth.map((w) => (
                            <RenderKValue
                              key={w.week}
                              value={
                                w.week <= currentWeekIndex ? weekMap[w.week] : 0
                              }
                            />
                          ))}
                          <RenderKValue value={mtd} />
                          {/* headcount */}
                          <td className="py-2 px-4 text-sm text-right border-x border-gray-200">
                            {headcount}
                          </td>
                          {/* productivity */}
                          <td className="py-2 px-4 text-sm text-right border-x border-gray-200">
                            {headcount !== "-" && headcount !== 0
                              ? Math.round(
                                  weekMap[currentWeekIndex] / (1000 * headcount)
                                ).toLocaleString("en-AU")
                              : "-"}
                          </td>
                          {/* w2w movement */}
                          <td className="py-2 px-4 text-sm text-left">
                            {movement[area]?.join(", ") || ""}
                          </td>
                        </tr>
                      );
                    })}
                    <tr className="font-semibold bg-gray-100 border-gray-300 ">
                      <td className="py-2 px-4 text-sm">Total</td>
                      {weeksInMonth.map((w) => {
                        const val = aggregatedForecasts["Total"]?.[w.week] || 0;
                        return (
                          <td
                            key={w.week}
                            className="py-2 px-4 text-sm text-right"
                          >
                            {w.week <= currentWeekIndex
                              ? Math.round(val / 1000).toLocaleString("en-AU")
                              : "-"}
                          </td>
                        );
                      })}
                      <td className="py-2 px-4 text-sm text-right">
                        {Math.round(
                          (cumulativeActuals["Total"]?.[currentWeekIndex] ||
                            0) / 1000
                        ).toLocaleString("en-AU")}
                      </td>
                      <td className="py-2 px-4 text-sm text-right">
                        {Object.values(headcountByArea)
                          .reduce((a, b) => a + b, 0)
                          .toFixed(1)}
                      </td>
                      <td className="py-2 px-4 text-sm text-right">
                        {(() => {
                          const totalHeadcount = Object.values(
                            headcountByArea
                          ).reduce((a, b) => a + b, 0);
                          const totalMTD =
                            aggregatedForecasts["Total"][currentWeekIndex] || 0;
                          return totalHeadcount
                            ? Math.round(
                                totalMTD / (1000 * totalHeadcount)
                              ).toLocaleString("en-AU")
                            : "-";
                        })()}
                      </td>
                      <td className="py-2 px-4 text-sm text-right"></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
      <div className="text-gray-400 p-5 text-right">
        For any issues, please contact Leo@trihalo.com.au
      </div>
    </div>
  );
}

// --- 👤 Recruiter Section Button Grid ---
function Section({ title, names }) {
  const navigate = useNavigate();
  return (
    <div>
      <h3 className="text-lg font-medium mb-3">{title}</h3>
      <div className="flex flex-wrap gap-3">
        {names.map((name) => (
          <button
            key={name}
            onClick={() => navigate(`/forecasts/${encodeURIComponent(name)}`)}
            className="bg-blue-100 text-primary font-small px-4 py-1.5 rounded-full"
          >
            {name}
          </button>
        ))}
      </div>
    </div>
  );
}

export default ForecastMain;
