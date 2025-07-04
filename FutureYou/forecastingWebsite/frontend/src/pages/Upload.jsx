import { useState, useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import TopNavbar from "../components/TopNavbar.jsx";
import calendar from "../data/calendar.js";
import { getCurrentMonthInfo } from "../utils/getCurrentMonthInfo.js";
import { uploadForecastToBQ, fetchForecastForRecruiter } from "../api";
import {
  getStoredInvoiceData,
  getStoredPrevInvoiceData,
} from "../utils/getInvoiceInfo";

function Upload() {
  const navigate = useNavigate();
  const { recruiterName } = useParams();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(true);
  const invoiceData = getStoredInvoiceData();
  const prevInvoiceData = getStoredPrevInvoiceData();
  const [alertMessage, setAlertMessage] = useState("");
  const [showAlert, setShowAlert] = useState(false);
  const [showingPreviousMonth, setShowingPreviousMonth] = useState(false);

  useEffect(() => {
    if (alertMessage) {
      const timer = setTimeout(() => setShowAlert(false), 5000);
      return () => clearTimeout(timer);
    }
  }, [alertMessage]);

  const {
    currentFY,
    currentMonth,
    weeksInMonth,
    currentWeekIndex,
    previousMonth,
    previousMonthFY,
  } = getCurrentMonthInfo(calendar);

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

  const permInvoicesPrev = prevInvoiceData
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
      sumActualsPast();
      setFetching(false);
    };

    fetchData();
  }, [recruiterName, currentFY, currentMonth]);
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

  // ============= SUMMATION FORMULAS =============

  const sumActualsPast = (type) => {
    return Object.entries(actualsByWeek[type] || {})
      .filter(([week]) => Number(week) < currentWeekIndex)
      .reduce((sum, [_, value]) => sum + value, 0);
  };

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
        setAlertMessage(result.message);
        setShowAlert(true);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-base-300 text-base-content flex-col">
      <TopNavbar userName={localStorage.getItem("name")} />
      <main className="flex-1 p-8">
        <div className="max-w mx-auto bg-base-100 rounded-xl shadow p-6">
          <div className="flex items-baseline gap-6 mb-6">
            <h1 className="text-2xl font-bold text-primary">
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
            <div className="flex flex-col items-center justify-center py-10">
              <div className="w-6 h-6 border-4 border-gray-300 border-t-primary rounded-full animate-spin"></div>
              <p className="mt-4">Loading forecast data...</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="table-auto text-sm">
                  <thead>
                    <tr className="bg-base-300 text-base-content border-b border-base-300">
                      <th className="text-left px-4 py-2 min-w-[60px] max-w-[80px]">
                        Week
                      </th>
                      <th className="text-left px-4 py-2 min-w-[120px] max-w-[160px]">
                        Date Range
                      </th>
                      <th className="text-left px-4 py-2 min-w-[120px] max-w-[160px]">
                        Forecast Perm
                      </th>
                      <th className="text-left px-4 py-2 min-w-[120px] max-w-[160px]">
                        Forecast Temp
                      </th>
                      <th className="text-left px-4 py-2 min-w-[120px] max-w-[160px]">
                        Actual Perm
                      </th>
                      <th className="text-left px-4 py-2 min-w-[120px] max-w-[160px]">
                        Actual Temp
                      </th>
                      <th className="text-left px-4 py-2 min-w-[120px] max-w-[160px]">
                        Actual Total
                      </th>
                      <th className="text-left px-4 py-2 min-w-[300px] max-w-[300px]">
                        Notes
                      </th>
                      <th className="px-2 py-2 w-[40px]"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, idx) => {
                      const isEditable = row.week >= currentWeekIndex;
                      return (
                        <tr
                          key={idx}
                          className="border-b border-base-300 border-x border-base-300"
                        >
                          <td className="px-4 py-2 text-nowrap border-x border-base-300">
                            Wk {row.week}
                          </td>
                          <td className="px-4 py-2 text-sm text-gray-500 text-nowrap border-x border-base-300">
                            {row.range}
                          </td>
                          <td
                            className={`px-4 py-2 border-x border-base-300 ${
                              !isEditable ? "bg-base-300" : ""
                            }`}
                          >
                            <input
                              type="number"
                              className={`bg-transparent focus:outline-none ${
                                !isEditable
                                  ? "opacity-40 cursor-not-allowed text-base-300"
                                  : ""
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

                          <td
                            className={`px-4 py-2 border-x border-base-300 border-r-5 ${
                              !isEditable ? "bg-base-300" : ""
                            }`}
                          >
                            <input
                              type="number"
                              className={`focus:outline-none ${
                                !isEditable
                                  ? "opacity-40 cursor-not-allowed text-base-300"
                                  : ""
                              }`}
                              placeholder="$"
                              value={row.tempRevenue ?? ""}
                              onChange={(e) => {
                                if (!isEditable) return;
                                handleChange(
                                  idx,
                                  "tempRevenue",
                                  e.target.value
                                );
                              }}
                              disabled={!isEditable}
                            />
                          </td>

                          <td
                            className={`px-4 py-2 whitespace-nowrap border-x border-base-300 ${
                              !isEditable ? "opacity-40 cursor-not-allowed" : ""
                            }`}
                          >
                            {actualsByWeek["Perm"][row.week]
                              ? `${Math.round(
                                  actualsByWeek["Perm"][row.week]
                                ).toLocaleString()}`
                              : "-"}
                          </td>
                          <td
                            className={`px-4 py-2 whitespace-nowrap border-x border-base-300 ${
                              !isEditable ? "opacity-40 cursor-not-allowed" : ""
                            }`}
                          >
                            {actualsByWeek["Temp"][row.week]
                              ? `${Math.round(
                                  actualsByWeek["Temp"][row.week]
                                ).toLocaleString()}`
                              : "-"}
                          </td>
                          <td
                            className={`px-4 py-2 whitespace-nowrap border-x border-base-300 ${
                              !isEditable ? "opacity-40 cursor-not-allowed" : ""
                            }`}
                          >
                            {!isEditable
                              ? (() => {
                                  const actualPerm =
                                    actualsByWeek["Perm"][row.week] || 0;
                                  const actualTemp =
                                    actualsByWeek["Temp"][row.week] || 0;
                                  const TotalRev = Math.round(
                                    actualPerm + actualTemp
                                  );

                                  const absTotal =
                                    Math.abs(TotalRev).toLocaleString();
                                  const formatted =
                                    TotalRev < 0
                                      ? `(${absTotal})`
                                      : `${absTotal}`;

                                  return (
                                    <span
                                      className={
                                        TotalRev < 0
                                          ? "text-secondary"
                                          : "text-gray-600"
                                      }
                                    >
                                      {formatted}
                                    </span>
                                  );
                                })()
                              : "-"}
                          </td>
                          <td className="px-4 py-2">
                            <input
                              type="text"
                              className={`w-full bg-transparent focus:outline-none ${
                                !isEditable
                                  ? "opacity-40 cursor-not-allowed"
                                  : ""
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
                          <td className="px-2 text-center">
                            {!isEditable && (
                              <span className="text-gray-400 text-xl">🔒</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
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

              <div className="mt-6 text-sm text-gray-500">
                <p>
                  <span className="font-semibold">
                    {recruiterName.split(" ")[0]}'s {currentMonth} Forecast:
                  </span>
                  <span className="text-sm space-x-4">
                    <span></span>
                    <span>
                      <strong>
                        {Math.round(sumActualsPast("Perm")).toLocaleString()}
                      </strong>
                      {""}
                      <span className="text-gray-500"> (Perm Actual) + </span>
                      <strong>
                        {Math.round(sumActualsPast("Temp")).toLocaleString()}
                      </strong>{" "}
                      <span className="text-gray-500"> (Temp Actual) + </span>
                      <strong>
                        {Math.round(
                          rows
                            .filter((row) => row.week >= currentWeekIndex)
                            .reduce(
                              (sum, row) =>
                                sum +
                                (Number(row.revenue) || 0) +
                                (Number(row.tempRevenue) || 0),
                              0
                            )
                        ).toLocaleString()}
                      </strong>{" "}
                      <span className="text-gray-500"> (Forecast) = </span>
                      <span className="text-primary text-lg">
                        <strong>
                          $
                          {Math.round(
                            sumActualsPast("Perm") +
                              sumActualsPast("Temp") +
                              rows
                                .filter((row) => row.week >= currentWeekIndex)
                                .reduce(
                                  (sum, row) =>
                                    sum +
                                    (Number(row.revenue) || 0) +
                                    (Number(row.tempRevenue) || 0),
                                  0
                                )
                          ).toLocaleString()}
                        </strong>
                      </span>
                    </span>
                  </span>
                </p>
              </div>
              <div className="mt-12 space-y-8 text-sm">
                {/* PERM SECTION */}
                <div>
                  <div className="mb-2 flex gap-4 items-center">
                    <button
                      className="btn btn-sm btn-soft"
                      onClick={() =>
                        setShowingPreviousMonth(!showingPreviousMonth)
                      }
                    >
                      {showingPreviousMonth
                        ? `Show Current Month's Invoices`
                        : `Show Previous Month's Invoices`}
                    </button>
                  </div>

                  <h3 className="text-base font-semibold text-primary">
                    Actual Perm Invoiced Revenue for{" "}
                    <span className="text-secondary">
                      {showingPreviousMonth ? previousMonth : currentMonth}
                    </span>
                    <span className="text-secondary">
                      {" ("}
                      {showingPreviousMonth ? previousMonthFY : currentFY}
                      {")"}
                    </span>
                  </h3>

                  {(showingPreviousMonth ? permInvoicesPrev : permInvoices)
                    .length === 0 ? (
                    <p className="text-sm text-gray-500 mt-2">
                      No perm invoices for{" "}
                      {showingPreviousMonth ? previousMonth : currentMonth}.
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
                        {(showingPreviousMonth
                          ? permInvoicesPrev
                          : permInvoices
                        ).map((inv, idx) => (
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
                      <tfoot>
                        <tr>
                          <td colSpan="3" className="text-right font-semibold">
                            Total Margin:
                          </td>
                          <td className="font-semibold">
                            $
                            {Math.round(
                              (showingPreviousMonth
                                ? permInvoicesPrev
                                : permInvoices
                              ).reduce(
                                (sum, inv) => sum + (Number(inv.Margin) || 0),
                                0
                              )
                            ).toLocaleString()}
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                  )}
                </div>
              </div>
            </>
          )}
          {alertMessage && showAlert && (
            <div className="fixed bottom-10 right-10 text-center z-50">
              <div className="alert shadow-lg w-fit rounded-full bg-emerald-300 border-0">
                <div className="flex items-center">
                  <span className="badge uppercase rounded-full bg-emerald-400 mr-4 p-4 border-0">
                    Success
                  </span>
                  <span>{alertMessage}</span>
                  <button
                    onClick={() => setShowAlert(false)}
                    className="btn btn-sm btn-ghost ml-4"
                  >
                    ✕
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default Upload;
