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

  // For testing purposes
  // const { weeksInMonth } = getCurrentMonthInfo(calendar);
  // const currentFY = "FY25";
  // const currentMonth = "May";
  // const currentWeekIndex = 2;

  const actualsByWeek = useMemo(() => {
    const map = {
      Perm: {},
      Temp: {},
    };

    invoiceData.forEach((inv) => {
      if (inv.Consultant === recruiterName) {
        const weekNum = Number(inv.Week);
        const type = inv.Type;
        if (!map[type]) return;
        if (!map[type][weekNum]) map[type][weekNum] = 0;
        map[type][weekNum] += Number(inv.Margin || 0);
      }
    });

    return map;
  }, [invoiceData, recruiterName]);

  const permInvoices = invoiceData
    .filter((inv) => inv.Consultant === recruiterName && inv.Type === "Perm")
    .sort((a, b) => Number(a.Week) - Number(b.Week));

  useEffect(() => {
    const fetchData = async () => {
      setFetching(true);
      const populatedRows = await fetchForecastForRecruiter(
        recruiterName,
        currentFY,
        currentMonth,
        weeksInMonth
      );

      const enrichedRows = populatedRows.map((row) => ({
        ...row,
        revenue: row.revenue ?? 0,
        tempRevenue: row.tempRevenue ?? 0,
        uploadMonth: currentMonth,
        uploadWeek: currentWeekIndex,
        uploadYear: currentFY,
        name: recruiterName,
        key: `${row.fy}:${row.month}:${row.week}:${recruiterName}`,
      }));

      setRows(enrichedRows);
      setFetching(false);
    };

    fetchData();
  }, [recruiterName, currentFY, currentMonth]);

  console.log("Rows for latestUpload check:", rows);

  const latestUpload = useMemo(() => {
    if (!rows.length) return null;
    const validRows = rows.filter((r) => r.uploadTimestamp && r.uploadUser);
    if (!validRows.length) return null;
    const latest = validRows[0];

    return {
      time: latest.uploadTimestamp,
      user: latest.uploadUser,
    };
  }, [rows]);

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
                    <th>Forecast Perm</th>
                    <th>Forecast Temp</th>
                    <th>Actual Perm</th>
                    <th>Actual Temp</th>
                    <th>Total Variance</th>
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
                            type="number"
                            className={`w-full bg-transparent focus:outline-none ${
                              !isEditable ? "opacity-60 cursor-not-allowed" : ""
                            }`}
                            placeholder="$"
                            value={row.tempRevenue ?? ""}
                            onChange={(e) => {
                              if (!isEditable) return;
                              handleChange(idx, "tempRevenue", e.target.value);
                            }}
                            disabled={!isEditable}
                          />
                        </td>
                        <td>
                          {actualsByWeek["Perm"][row.week]
                            ? `$${Math.round(
                                actualsByWeek["Perm"][row.week]
                              ).toLocaleString()}`
                            : "-"}
                        </td>
                        <td>
                          {actualsByWeek["Temp"][row.week]
                            ? `$${Math.round(
                                actualsByWeek["Temp"][row.week]
                              ).toLocaleString()}`
                            : "-"}
                        </td>
                        <td>hello!</td>
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

              {latestUpload && (
                <div className="text-sm text-gray-400 mb-2 mt-4">
                  Last updated at{" "}
                  <span className="font-medium">{latestUpload.time}</span> by{" "}
                  <span className="font-medium">{latestUpload.user}</span>.
                </div>
              )}

              <button
                className="btn btn-secondary mt-4 flex items-center gap-2"
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
                          <th>Margin</th>
                        </tr>
                      </thead>
                      <tbody>
                        {permInvoices.map((inv, idx) => (
                          <tr key={idx}>
                            <td>Wk {inv.Week}</td>
                            <td>{inv.InvoiceNumber}</td>
                            <td>{inv.ToClient || "-"}</td>
                            <td>
                              ${Math.round(inv.Margin || 0).toLocaleString()}
                            </td>
                          </tr>
                        ))}
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
