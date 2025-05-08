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

  const invoices = getStoredInvoiceData();

  const {
    currentMonth,
    currentFY,
    weeksInMonth: currentWeeks,
    currentWeekIndex,
  } = getCurrentMonthInfo(calendar);

  const [forecastData, setForecastData] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      const summary = await fetchForecastSummary(currentFY, currentMonth);

      // Build weeks array for each recruiter
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

              return { name, weeks };
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
                {currentFY} {currentMonth} Forecasts
              </h2>
              {forecastData.map((section) => {
                const totals = Array(currentWeeks.length).fill(0);
                section.data.forEach((row) => {
                  const paddedWeeks = [...row.weeks];
                  while (paddedWeeks.length < currentWeeks.length)
                    paddedWeeks.push(0);
                  if (paddedWeeks.length > currentWeeks.length)
                    paddedWeeks.length = currentWeeks.length;

                  paddedWeeks.forEach((value, index) => {
                    totals[index] += value;
                  });
                });
                const totalSum = totals.reduce((a, b) => a + b, 0);

                return (
                  <div key={section.title}>
                    <h3 className="text-lg font-semibold mb-2">
                      {section.title}
                    </h3>
                    <div className="overflow-x-auto">
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
                          {section.data.map(({ name, weeks }) => {
                            const paddedWeeks = [...weeks];
                            while (paddedWeeks.length < currentWeeks.length)
                              paddedWeeks.push(0);
                            if (paddedWeeks.length > currentWeeks.length)
                              paddedWeeks.length = currentWeeks.length;

                            const rowTotal = paddedWeeks.reduce(
                              (a, b) => a + b,
                              0
                            );
                            return (
                              <tr
                                key={name}
                                className="border-b border-gray-200"
                              >
                                <td className="py-2 px-4">{name}</td>
                                {paddedWeeks.map((amt, i) => (
                                  <td
                                    key={i}
                                    className={`py-2 px-4 ${
                                      i + 1 < currentWeekIndex
                                        ? "bg-accent font-semibold"
                                        : ""
                                    }`}
                                  >
                                    {amt > 0 ? `${amt.toLocaleString()}` : "0"}
                                  </td>
                                ))}
                                <td className="py-2 px-4 font-medium">
                                  {rowTotal.toLocaleString()}
                                </td>
                              </tr>
                            );
                          })}

                          <tr className="font-semibold text-black bg-gray-100">
                            <td className="py-2 px-4">Total</td>
                            {totals.map((amt, i) => (
                              <td key={i} className="py-2 px-4">
                                {amt.toLocaleString()}
                              </td>
                            ))}
                            <td className="py-2 px-4">
                              {totalSum.toLocaleString()}
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
            <div className="text-gray-800 text-sm space-y-6">
              <h2 className="text-xl font-semibold text-primary">
                {currentMonth}
              </h2>
              <p className="text-sm text-gray-600 font-medium">
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
                      <th className="text-left py-2 px-4">Total</th>
                      <th className="text-left py-2 px-4">Headcount</th>
                      <th className="text-left py-2 px-4">Productivity</th>
                      <th className="text-left py-2 px-4">MTD Invoiced</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(summaryMapping).map(
                      ([area, recruiters]) => {
                        const rows = recruiters.map((name) => {
                          return (
                            forecastData
                              .flatMap((s) => s.data)
                              .find((r) => r.name === name) || {
                              name,
                              weeks: Array(currentWeeks.length).fill(0),
                            }
                          );
                        });

                        const areaTotals = Array(currentWeeks.length).fill(0);
                        rows.forEach((r) => {
                          r.weeks.forEach((v, i) => {
                            areaTotals[i] += v;
                          });
                        });

                        const totalSum = areaTotals.reduce((a, b) => a + b, 0);

                        return (
                          <tr key={area} className="border-b border-gray-100">
                            <td className="py-2 px-4 font-medium">{area}</td>
                            {areaTotals.map((v, i) => (
                              <td key={i} className="py-2 px-4">
                                {v > 0 ? `${Math.round(v / 1000)}` : "-"}
                              </td>
                            ))}
                            <td className="py-2 px-4 font-medium">
                              {Math.round(totalSum / 1000)}
                            </td>
                            <td className="py-2 px-4">
                              {headcountByArea[area] ?? "-"}
                            </td>
                            <td className="py-2 px-4">
                              {Math.floor(totalSum / 1000)}
                            </td>
                            <td className="py-2 px-4">0</td>
                          </tr>
                        );
                      }
                    )}

                    {/* Total row */}
                    <tr className="font-semibold bg-gray-100 border-t border-gray-300">
                      <td className="py-2 px-4">Total</td>
                      {(() => {
                        const totals = Array(currentWeeks.length).fill(0);
                        Object.values(summaryMapping).forEach((recruiters) => {
                          recruiters.forEach((name) => {
                            const r = forecastData
                              .flatMap((s) => s.data)
                              .find((r) => r.name === name);
                            if (r) {
                              r.weeks.forEach((v, i) => (totals[i] += v));
                            }
                          });
                        });

                        const grandTotal = totals.reduce((a, b) => a + b, 0);

                        return (
                          <>
                            {totals.map((v, i) => (
                              <td key={i} className="py-2 px-4">
                                {v > 0 ? `${Math.round(v / 1000)}` : "-"}
                              </td>
                            ))}
                            <td className="py-2 px-4 font-semibold">
                              {Math.round(grandTotal / 1000)}
                            </td>
                          </>
                        );
                      })()}

                      <td className="py-2 px-4 font-bold">
                        {Object.values(headcountByArea)
                          .reduce((a, b) => a + b, 0)
                          .toFixed(1)}
                      </td>

                      <td className="py-2 px-4">FILLER</td>
                      <td className="py-2 px-4">FILLER</td>
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
