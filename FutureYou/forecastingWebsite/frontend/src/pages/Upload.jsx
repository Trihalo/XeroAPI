// src/pages/Upload.jsx
import { useState, useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import TopNavbar from "../components/TopNavbar.jsx";
import calendar from "../data/calendar.js";
import { getCurrentMonthInfo } from "../utils/getCurrentMonthInfo.js";
import { uploadForecastToBQ, fetchForecastForRecruiter } from "../api";
import { getStoredInvoiceData } from "../utils/getInvoiceInfo";

function Upload() {
  const navigate = useNavigate();
  const { recruiterName } = useParams();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(true);
  const invoiceData = getStoredInvoiceData();

  const { currentFY, currentMonth, weeksInMonth, currentWeekIndex } =
    getCurrentMonthInfo(calendar);

  const actualsByWeek = useMemo(() => {
    const map = {};
    invoiceData.forEach((inv) => {
      if (inv.Consultant === recruiterName) {
        const weekNum = Number(inv.Week);
        if (!map[weekNum]) map[weekNum] = 0;
        map[weekNum] += Number(inv.Margin || 0);
      }
    });
    return map;
  }, [invoiceData, recruiterName]);

  const permInvoices = invoiceData
    .filter((inv) => inv.Consultant === recruiterName && inv.Type === "Perm")
    .sort((a, b) => Number(a.Week) - Number(b.Week));

  const tempInvoices = invoiceData.filter(
    (inv) => inv.Consultant === recruiterName && inv.Type === "Temp"
  );

  console.log("Perm Invoices:", permInvoices);
  useEffect(() => {
    const fetchData = async () => {
      setFetching(true);
      const populatedRows = await fetchForecastForRecruiter(
        recruiterName,
        currentFY,
        currentMonth,
        weeksInMonth
      );
      setRows(populatedRows);
      setFetching(false);
    };

    fetchData();
  }, [recruiterName, currentFY, currentMonth]);

  const handleChange = (index, field, value) => {
    const updated = [...rows];
    updated[index][field] = value;
    setRows(updated);
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const result = await uploadForecastToBQ(rows);
      if (result.success) {
        sessionStorage.setItem("alertMessage", result.message);
        navigate("/forecasts");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-gray-200 text-base-content flex-col">
      <TopNavbar userName={localStorage.getItem("name")} />
      <main className="flex-1 p-8">
        <div className="max-w mx-auto bg-white rounded-xl shadow p-6">
          <div className="flex items-baseline gap-6 mb-6">
            <h1 className="text-2xl font-bold">
              {currentFY} {currentMonth} Forecast Upload
            </h1>
            <button
              onClick={() => navigate(-1)}
              className="text-sm text-gray-400 hover:text-blue-900"
            >
              ← Go Back
            </button>
          </div>

          <div className="text-sm text-gray-500 mb-10">
            For <span className="font-semibold">{recruiterName}</span>
          </div>

          {fetching ? (
            <div className="text-center text-gray-500 py-10">
              <span className="loading loading-spinner loading-lg text-primary"></span>
              <p className="mt-4">Loading forecast data...</p>
            </div>
          ) : (
            <>
              <table className="table w-auto">
                <thead>
                  <tr>
                    <th>Week</th>
                    <th>Date Range</th>
                    <th>Actual Perm Rev</th>
                    <th>Forecasted Perm Rev</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, idx) => {
                    const isEditable = row.week >= currentWeekIndex;

                    return (
                      <tr key={idx}>
                        <td>Wk {row.week}</td>
                        <td className="text-sm text-gray-500">{row.range}</td>
                        <td>
                          {actualsByWeek[row.week]
                            ? `$${Math.round(
                                actualsByWeek[row.week]
                              ).toLocaleString()}`
                            : "-"}
                        </td>
                        <td>
                          <input
                            type="number"
                            className={`w-full bg-transparent focus:outline-none ${
                              !isEditable ? "opacity-60 cursor-not-allowed" : ""
                            }`}
                            placeholder="$"
                            value={row.revenue ?? ""}
                            onChange={(e) => {
                              if (!isEditable) return;
                              handleChange(idx, "revenue", e.target.value);
                            }}
                            disabled={!isEditable}
                          />
                        </td>
                        <td>
                          <input
                            type="text"
                            className={`w-full min-w-[300px] bg-transparent focus:outline-none ${
                              !isEditable ? "opacity-60 cursor-not-allowed" : ""
                            }`}
                            placeholder="Optional notes"
                            value={row.notes ?? ""}
                            onChange={(e) => {
                              if (!isEditable) return;
                              handleChange(idx, "notes", e.target.value);
                            }}
                            disabled={!isEditable}
                          />
                        </td>
                        <td>
                          {!isEditable && (
                            <span className="text-gray-400 text-xl">🔒</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              <button
                className="btn btn-secondary mt-6 flex items-center gap-2"
                onClick={handleSubmit}
                disabled={loading}
              >
                {loading && (
                  <span className="loading loading-spinner loading-sm text-white"></span>
                )}
                Upload Forecast
              </button>

              <div className="mt-12 space-y-8 text-sm">
                {/* PERM SECTION */}
                <div>
                  <h3 className="text-base font-semibold text-primary">
                    Actual Perm Invoiced Revenue for{" "}
                    <span className="text-secondary">{currentMonth}</span>
                  </h3>
                  {permInvoices.length === 0 ? (
                    <p className="text-sm text-gray-500 mt-2">
                      No perm invoices for {currentMonth}.
                    </p>
                  ) : (
                    <table className="table w-auto mt-2">
                      <thead>
                        <tr className="text-gray-500">
                          <th>Week</th>
                          <th>Inv. #</th>
                          <th>Client</th>
                          <th>Description</th>
                          <th>Margin</th>
                        </tr>
                      </thead>
                      <tbody>
                        {permInvoices.map((inv, idx) => (
                          <tr key={idx}>
                            <td>Wk {inv.Week}</td>
                            <td>{inv.InvoiceNumber}</td>
                            <td>{inv.ToClient || "-"}</td>
                            <td className="w-[300px]">
                              {inv.Description || "-"}
                            </td>
                            <td>
                              ${Math.round(inv.Margin || 0).toLocaleString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>

                {/* TEMP SECTION */}
                <div>
                  <h3 className="text-base font-semibold text-primary">
                    Actual Temp Invoiced Revenue for{" "}
                    <span className="text-secondary">{currentMonth}</span>
                  </h3>

                  {tempInvoices.length === 0 ? (
                    <p className="text-sm text-gray-500 mt-2">
                      No temp invoices for {currentMonth}.
                    </p>
                  ) : (
                    <table className="table w-auto mt-2">
                      <thead>
                        <tr className="text-gray-500">
                          <th>Week</th>
                          <th>Margin</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(() => {
                          const weeklySums = {};
                          tempInvoices.forEach((inv) => {
                            const w = inv.Week;
                            if (!weeklySums[w]) weeklySums[w] = 0;
                            weeklySums[w] += Number(inv.Margin || 0);
                          });

                          return Object.entries(weeklySums).map(
                            ([week, margin]) => (
                              <tr key={week}>
                                <td>Wk {week}</td>
                                <td>${Math.round(margin).toLocaleString()}</td>
                              </tr>
                            )
                          );
                        })()}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

export default Upload;
