import React, { useState, useEffect, useRef } from "react";
import TopNavbar from "../components/TopNavbar";
import {
  recruiterMapping,
  summaryMapping,
  headcountByArea,
} from "../data/recruiterMapping";
import { useNavigate } from "react-router-dom";
import calendar from "../data/calendar";
import { getCurrentMonthInfo } from "../utils/getCurrentMonthInfo";
import { fetchForecastSummary } from "../api";
import { getStoredInvoiceData } from "../utils/getInvoiceInfo";

function ForecastMain() {
  const [activeTab, setActiveTab] = useState("input");
  const [rawForecastRows, setRawForecastRows] = useState([]);
  const {
    currentMonth,
    currentFY,
    weeksInMonth: currentWeeks,
    currentWeekIndex,
  } = getCurrentMonthInfo(calendar);

  // For testing purposes
  // const { weeksInMonth: currentWeeks } = getCurrentMonthInfo(calendar);
  // const currentFY = "FY25";
  // const currentMonth = "May";
  // const currentWeekIndex = 3;

  const invoices = getStoredInvoiceData();

  const actualsByRecruiterWeek = {};
  const actualsByArea = {};

  invoices.forEach((inv) => {
    const {
      Consultant: name,
      Area: area,
      Week,
      Margin,
      FutureYouMonth,
      FinancialYear,
    } = inv;

    if (FutureYouMonth === currentMonth && FinancialYear === currentFY) {
      const week = Number(Week);
      const margin = Number(Margin || 0);

      // Recruiter-level map
      if (!actualsByRecruiterWeek[name]) actualsByRecruiterWeek[name] = {};
      if (!actualsByRecruiterWeek[name][week])
        actualsByRecruiterWeek[name][week] = 0;
      actualsByRecruiterWeek[name][week] += margin;

      // Area-level map
      if (!actualsByArea[area]) actualsByArea[area] = {};
      if (!actualsByArea[area][week]) actualsByArea[area][week] = 0;
      actualsByArea[area][week] += margin;
    }
  });

  const [forecastData, setForecastData] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      const summary = await fetchForecastSummary(currentFY, currentMonth);
      setRawForecastRows(summary);

      // Still needed for "view" tab
      const structured = Object.entries(recruiterMapping).map(
        ([category, recruiters]) => {
          return {
            title: category,
            data: recruiters.map((name) => {
              const weeks = currentWeeks.map((week) => {
                const match = summary.find(
                  (entry) =>
                    entry.name === name && Number(entry.week) === week.week
                );
                return match ? Number(match.total_revenue) : 0;
              });

              const latestUpload = summary
                .filter((entry) => entry.name === name)
                .reduce(
                  (max, curr) =>
                    Number(curr.uploadWeek) > Number(max.uploadWeek)
                      ? curr
                      : max,
                  { uploadWeek: 0 }
                );

              return {
                name,
                weeks,
                uploadWeek: latestUpload.uploadWeek,
              };
            }),
          };
        }
      );
      setForecastData(structured);
    };

    fetchData();
  }, [currentFY, currentMonth]);

  // for recruiter success messages
  const [alertMessage, setAlertMessage] = useState(null);

  useEffect(() => {
    const message = sessionStorage.getItem("alertMessage");
    if (message) {
      setAlertMessage(message);
      sessionStorage.removeItem("alertMessage");
    }
  }, []);

  const [showAlert, setShowAlert] = useState(true);

  useEffect(() => {
    if (alertMessage) {
      const timer = setTimeout(() => setShowAlert(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [alertMessage]);

  return (
    <div className="min-h-screen bg-gray-200 text-base-content flex flex-col">
      <TopNavbar userName={localStorage.getItem("name") || "User"} />

      <div className="flex-1 p-8">
        <div className="max-w mx-auto bg-white rounded-xl shadow p-6 relative">
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
              <h2 className="text-xl font-semibold text-primary">
                {currentFY} {currentMonth} Latest Forecasts
              </h2>
              {forecastData.map((section) => {
                const sectionRows = section.data.map(({ name }) => {
                  // Find all uploads for this recruiter
                  const allForecasts = rawForecastRows.filter(
                    (r) => r.name === name
                  );

                  // Pick the rows from the highest uploadWeek
                  const maxUploadWeek = Math.max(
                    ...allForecasts.map((r) => Number(r.uploadWeek || 0))
                  );

                  const latestRows = allForecasts.filter(
                    (r) => Number(r.uploadWeek) === maxUploadWeek
                  );

                  // Build padded forecast array from those latest rows
                  const paddedWeeks = currentWeeks.map((w) => {
                    const matching = latestRows.find(
                      (r) => Number(r.week) === w.week
                    );
                    return matching ? Number(matching.total_revenue) : 0;
                  });

                  // Override with actuals for past weeks
                  const finalWeeks = paddedWeeks.map((forecastAmt, i) => {
                    const weekNumber = i + 1;
                    if (weekNumber < currentWeekIndex) {
                      const actual =
                        actualsByRecruiterWeek[name]?.[weekNumber] || 0;
                      return actual;
                    }
                    return forecastAmt;
                  });

                  const rowTotal = finalWeeks.reduce((a, b) => a + b, 0);

                  return { name, finalWeeks, rowTotal };
                });

                // compute section totals from finalWeeks
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
                      <table className="min-w-full text-left border-collapse text-sm">
                        <thead className="bg-gray-100 text-gray-700">
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
                            <th className="py-2 px-4 font-semibold">Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sectionRows.map(({ name, finalWeeks, rowTotal }) => (
                            <tr key={name} className="border-b border-gray-200">
                              <td className="py-2 px-4">{name}</td>
                              {finalWeeks.map((amt, i) => (
                                <td
                                  key={i}
                                  className={`py-2 px-4 ${
                                    i + 1 < currentWeekIndex
                                      ? "bg-accent font-semibold"
                                      : ""
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
                {currentMonth}
              </h2>
              <p className="text-md text-gray-600 font-medium">
                Target <span className="font-bold">550k</span>
              </p>

              <div className="overflow-x-auto">
                <table className="table table-sm min-w-full border-collapse">
                  <thead className="bg-gray-100 text-gray-700">
                    <tr>
                      <th className="text-left py-2 px-4">Area</th>
                      {currentWeeks.map((w) => (
                        <th key={w.week} className="text-left py-2 px-4">
                          Wk {w.week}
                        </th>
                      ))}
                      <th className="text-left py-2 px-4">MTD Invoiced</th>
                      <th className="text-left py-2 px-4">Headcount</th>
                      <th className="text-left py-2 px-4">Productivity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(summaryMapping).map(
                      ([area, recruiters]) => {
                        // MTD invoiced (weeks already completed)
                        const mtdInvoiced = Array.from(
                          { length: currentWeekIndex },
                          (_, i) => {
                            const week = i + 1;
                            return actualsByArea[area]?.[week] || 0;
                          }
                        ).reduce((a, b) => a + b, 0);

                        // Weekly forecast+actual row
                        const row = currentWeeks.map((w) => {
                          if (w.week > currentWeekIndex) return "-";

                          const forecastRows = rawForecastRows.filter(
                            (r) =>
                              recruiters.includes(r.name) &&
                              Number(r.uploadWeek) === w.week &&
                              Number(r.week) >= w.week
                          );

                          const actualRows = invoices.filter(
                            (inv) =>
                              recruiters.includes(inv.Consultant) &&
                              inv.FutureYouMonth === currentMonth &&
                              inv.FinancialYear === currentFY &&
                              Number(inv.Week) < w.week
                          );

                          const forecastSum = forecastRows.reduce(
                            (acc, r) => acc + Number(r.total_revenue || 0),
                            0
                          );

                          const actualSum = actualRows.reduce(
                            (acc, r) => acc + Number(r.Margin || 0),
                            0
                          );

                          return forecastSum + actualSum;
                        });

                        return (
                          <tr key={area} className="border-b border-gray-100">
                            <td className="py-2 px-4 font-medium text-sm">
                              {area}
                            </td>
                            {row.map((val, idx) => (
                              <td key={idx} className="py-2 px-4 text-sm">
                                {val === "-" ? "-" : Math.round(val / 1000)}
                              </td>
                            ))}
                            <td className="py-2 px-4 text-sm">
                              {mtdInvoiced > 0
                                ? Math.round(mtdInvoiced / 1000)
                                : "-"}
                            </td>
                            <td className="py-2 px-4 text-sm">
                              {headcountByArea[area] ?? "-"}
                            </td>
                            <td className="py-2 px-4 text-sm">
                              {row[0] !== "-" && headcountByArea[area]
                                ? Math.round(
                                    row[0] / headcountByArea[area] / 1000
                                  )
                                : "-"}
                            </td>
                          </tr>
                        );
                      }
                    )}

                    {/* Totals Row */}
                    <tr className="font-semibold bg-gray-100 border-t border-gray-300">
                      <td className="py-2 px-4 text-sm">Total</td>
                      {currentWeeks.map((w) => {
                        if (w.week > currentWeekIndex) {
                          return (
                            <td
                              key={w.week}
                              className="py-2 px-4 text-gray-400 text-sm"
                            >
                              -
                            </td>
                          );
                        }

                        const forecastRows = rawForecastRows.filter(
                          (r) =>
                            Number(r.uploadWeek) === w.week &&
                            Number(r.week) >= w.week
                        );

                        const actualRows = invoices.filter(
                          (inv) =>
                            Number(inv.Week) < w.week &&
                            inv.FutureYouMonth === currentMonth &&
                            inv.FinancialYear === currentFY
                        );

                        const forecastSum = forecastRows.reduce(
                          (acc, r) => acc + Number(r.total_revenue || 0),
                          0
                        );

                        const actualSum = actualRows.reduce(
                          (acc, r) => acc + Number(r.Margin || 0),
                          0
                        );

                        const total = forecastSum + actualSum;

                        return (
                          <td key={w.week} className="py-2 px-4">
                            {total > 0 ? Math.round(total / 1000) : "-"}
                          </td>
                        );
                      })}
                      <td className="py-2 px-4 text-sm">FILLER</td>
                      <td className="py-2 px-4 text-sm">
                        {Object.values(headcountByArea)
                          .reduce((a, b) => a + b, 0)
                          .toFixed(1)}
                      </td>
                      <td className="py-2 px-4 text-sm">FILLER</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="text-xs text-gray-500 mt-6">
            For any issues, please contact{" "}
            <a href="mailto:Leo@trihalo.com.au" className="underline">
              Leo@trihalo.com.au
            </a>
          </div>
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
