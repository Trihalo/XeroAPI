import React, { useState, useEffect } from "react";
import TopNavbar from "../components/TopNavbar";
import {
  recruiterMapping,
  summaryMapping,
  headcountByArea,
  allAreas,
  allRecruiters,
} from "../data/recruiterMapping";
import { useNavigate } from "react-router-dom";
import calendar from "../data/calendar";
import { getCurrentMonthInfo } from "../utils/getCurrentMonthInfo";
import { fetchForecastSummary } from "../api";
import { getStoredInvoiceData } from "../utils/getInvoiceInfo";
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
  const [alertMessage, setAlertMessage] = useState(null);
  const [showAlert, setShowAlert] = useState(true);

  const {
    currentMonth,
    currentFY,
    weeksInMonth: currentWeeks,
    currentWeekIndex,
  } = getCurrentMonthInfo(calendar);

  // const currentMonth = "Jun";
  // const currentWeekIndex = 2;

  const weeks = currentWeeks.map((w) => w.week);
  const invoices = getStoredInvoiceData();
  const submittedRecruiters = useSubmittedRecruiters();

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
  } = useCumulativeActuals(currentMonth, currentFY, weeks);

  const {
    rawForecastRows,
    cumulativeForecasts,
    cumulativeForecastsByRecruiter,
  } = useCumulativeForecasts(currentFY, currentMonth);

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
  useEffect(() => {
    const fetchData = async () => {
      const summary = await fetchForecastSummary(currentFY, currentMonth);
      // Format forecastData for "view" tab
      const structured = Object.entries(recruiterMapping).map(
        ([category, recruiters]) => ({
          title: category,
          data: recruiters.map((name) => {
            const weeks = currentWeeks.map((w) => {
              const match = summary.find(
                (e) => e.name === name && Number(e.week) === w.week
              );
              return match ? Number(match.total_revenue) : 0;
            });

            const latestUpload = summary
              .filter((e) => e.name === name)
              .reduce(
                (max, curr) =>
                  Number(curr.uploadWeek) > Number(max.uploadWeek) ? curr : max,
                {
                  uploadWeek: 0,
                }
              );

            return { name, weeks, uploadWeek: latestUpload.uploadWeek };
          }),
        })
      );
      setForecastData(structured);
    };

    fetchData();
  }, [currentFY, currentMonth]);

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

  // --- 🛎️ Session Alert Message ---
  useEffect(() => {
    const message = sessionStorage.getItem("alertMessage");
    if (message) {
      setAlertMessage(message);
      sessionStorage.removeItem("alertMessage");
    }
  }, []);

  useEffect(() => {
    if (alertMessage) {
      const timer = setTimeout(() => setShowAlert(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [alertMessage]);

  // --- ✅ UI Render ---
  return (
    <div className="min-h-screen bg-gray-200 text-base-content flex flex-col">
      <TopNavbar userName={localStorage.getItem("name") || "User"} />
      <div className="flex-1 p-8">
        <div className="max-w mx-auto bg-white rounded-xl shadow p-10 pb-20 relative">
          <div className="flex justify-between items-start mb-6">
            <h1 className="text-2xl font-bold text-primary">
              Recruiter Forecasts
            </h1>
          </div>

          <div className="flex space-x-4 mb-8">
            {["input", "view", "summary"].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-1.5 rounded-lg shadow ${
                  activeTab === tab
                    ? "bg-red-400 text-white font-semibold"
                    : "bg-gray-300 text-gray-800 font-normal"
                }`}
              >
                {tab === "input"
                  ? "Forecast Input"
                  : tab === "view"
                  ? "View Forecasts"
                  : "Summary"}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          {activeTab === "input" && (
            <div className="space-y-8">
              {Object.entries(recruiterMapping).map(([category, names]) => (
                <Section key={category} title={category} names={names} />
              ))}
            </div>
          )}

          {activeTab === "view" && (
            <div className="text-gray-800 text-sm space-y-8">
              <div className="text-xl font-semibold text-primary">
                {currentFY} {currentMonth} Latest Forecasts
              </div>
              <div className="text-sm text-gray-400 mb-10">
                Red highlight represents actual invoiced revenue
              </div>
              {forecastData.map((section) => {
                const sectionRows = section.data.map(({ name }) => {
                  const allForecasts = rawForecastRows.filter(
                    (r) => r.name === name
                  );
                  const maxUploadWeek = Math.max(
                    ...allForecasts.map((r) => Number(r.uploadWeek || 0))
                  );
                  const latestRows = allForecasts.filter(
                    (r) => Number(r.uploadWeek) === maxUploadWeek
                  );
                  const paddedWeeks = currentWeeks.map((w) => {
                    const match = latestRows.find(
                      (r) => Number(r.week) === w.week
                    );
                    return match ? Number(match.total_revenue) : 0;
                  });
                  const finalWeeks = paddedWeeks.map((amt, i) => {
                    const weekNumber = i + 1;
                    return weekNumber < currentWeekIndex
                      ? actualsByRecruiterWeek[name]?.[weekNumber] || 0
                      : amt;
                  });
                  const rowTotal = finalWeeks.reduce((a, b) => a + b, 0);
                  return { name, finalWeeks, rowTotal };
                });

                const totals = currentWeeks.map((_, i) =>
                  sectionRows.reduce(
                    (sum, row) => sum + (row.finalWeeks[i] || 0),
                    0
                  )
                );
                const totalSum = totals.reduce((a, b) => a + b, 0);

                return (
                  <div key={section.title}>
                    <h3 className="text-lg font-semibold mb-5">
                      {section.title}
                    </h3>
                    <div className="overflow-x-auto mb-10">
                      <table className="min-w-full text-left border-collapse text-sm border-x border-gray-200">
                        <thead className="bg-gray-100 text-gray-700 border-x border-gray-200">
                          <tr>
                            <th className="py-2 px-4 font-semibold">Name</th>
                            {currentWeeks.map((week) => (
                              <th
                                key={week.week}
                                className="py-2 px-4 font-semibold"
                              >
                                Week {week.week}
                              </th>
                            ))}
                            <th className="py-2 px-4 font-semibold border-x border-gray-200">
                              Total
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {sectionRows.map(({ name, finalWeeks, rowTotal }) => (
                            <tr
                              key={name}
                              className="border-b border-x border-gray-200"
                            >
                              <td className="py-2 px-4">{name}</td>
                              {finalWeeks.map((amt, i) => (
                                <td
                                  key={i}
                                  className={`py-2 px-4 ${
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
                              <td className="py-2 px-4 font-medium">
                                {Math.round(rowTotal).toLocaleString()}
                              </td>
                            </tr>
                          ))}

                          <tr className="font-semibold text-black bg-gray-100">
                            <td className="py-2 px-4">Total</td>
                            {totals.map((amt, i) => (
                              <td key={i} className="py-2 px-4">
                                {Math.round(amt).toLocaleString()}
                              </td>
                            ))}
                            <td className="py-2 px-4">
                              {Math.round(totalSum).toLocaleString()}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                );
              })}
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

              <div className="overflow-x-auto">
                <table className="table table-sm min-w-full border-collapse">
                  <thead className="bg-gray-100 text-gray-700 border-x border-gray-200">
                    <tr>
                      <th className="text-left py-2 px-4">Area</th>
                      {currentWeeks.map((w) => (
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
                        <tr key={area} className="border-b border-gray-100">
                          <td className="py-2 px-4 font-medium text-sm border-x border-gray-200">
                            {area}
                          </td>
                          {currentWeeks.map((w) => (
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
                          <td className="py-2 px-4 text-sm text-left border-x border-gray-200">
                            {movement[area]?.join(", ") || ""}
                          </td>
                        </tr>
                      );
                    })}
                    <tr className="font-semibold bg-gray-100 border-t border-gray-300 ">
                      <td className="py-2 px-4 text-sm border-x border-gray-200">
                        Total
                      </td>
                      {currentWeeks.map((w) => {
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

          {alertMessage && showAlert && (
            <div className="fixed bottom-10 right-10 text-center">
              <div className="alert shadow-lg w-fit rounded-full bg-emerald-300 border-0">
                <div>
                  <span className="badge uppercase rounded-full bg-emerald-400 mr-4 p-4 border-0">
                    Success
                  </span>
                  <span>{alertMessage}</span>
                </div>
                <button className="btn btn-sm btn-ghost">✕</button>
              </div>
            </div>
          )}
        </div>
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
