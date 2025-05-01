// src/pages/Upload.jsx
import { useState } from "react";
import { uploadForecastToBQ } from "../api";
import Sidebar from "../components/Sidebar";
import { useNavigate } from "react-router-dom";

// Full calendar database (trimmed here for readability, paste full list when implementing)
const calendar = [
  { fy: "FY25", month: "Apr", week: 1, range: "1/4/25 - 5/4/25" },
  { fy: "FY25", month: "Apr", week: 2, range: "7/4/25 - 11/4/25" },
  { fy: "FY25", month: "Apr", week: 3, range: "14/4/25 - 18/4/25" },
  { fy: "FY25", month: "Apr", week: 4, range: "21/4/25 - 25/4/25" },
  { fy: "FY25", month: "May", week: 1, range: "28/4/25 - 2/5/25" },
  { fy: "FY25", month: "May", week: 2, range: "5/5/25 - 9/5/25" },
  { fy: "FY25", month: "May", week: 3, range: "12/5/25 - 16/5/25" },
  { fy: "FY25", month: "May", week: 4, range: "19/5/25 - 23/5/25" },
  { fy: "FY25", month: "Jun", week: 1, range: "26/5/25 - 30/5/25" },
  { fy: "FY25", month: "Jun", week: 2, range: "2/6/25 - 6/6/25" },
  { fy: "FY25", month: "Jun", week: 3, range: "9/6/25 - 13/6/25" },
  { fy: "FY25", month: "Jun", week: 4, range: "16/6/25 - 20/6/25" },
  { fy: "FY25", month: "Jun", week: 5, range: "23/6/25 - 27/6/25" },
  // Add all remaining months & weeks from your full dataset here
];

function Upload() {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    navigate("/", { replace: true });
  };

  const today = new Date();

  const matchedEntry = calendar.find((entry) => {
    const [startStr, endStr] = entry.range.split(" - ");
    const [sd, sm, sy] = startStr.split("/").map(Number);
    const [ed, em, ey] = endStr.split("/").map(Number);

    const start = new Date(sy < 100 ? sy + 2000 : sy, sm - 1, sd);
    const end = new Date(ey < 100 ? ey + 2000 : ey, em - 1, ed);

    return today >= start && today <= end;
  });

  const currentMonth = matchedEntry?.month ?? "Unknown";
  const currentFY = matchedEntry?.fy ?? "FY?";

  const weeksInMonth = calendar.filter(
    (e) => e.fy === currentFY && e.month === currentMonth
  );

  const name = localStorage.getItem("name") || "Unknown";

  const [rows, setRows] = useState(
    weeksInMonth.map((entry) => ({
      ...entry,
      revenue: "",
      notes: "",
      name: name,
    }))
  );
  const handleChange = (index, field, value) => {
    const updated = [...rows];
    updated[index][field] = value;
    setRows(updated);
  };

  const handleSubmit = async () => {
    console.log("Submitted Forecast:", rows);

    const username = localStorage.getItem("username") || "";
    const password = localStorage.getItem("password") || "";

    const result = await uploadForecastToBQ(rows, username, password);
  };

  return (
    <div className="min-h-screen flex bg-gray-200 text-base-content">
      <Sidebar onLogout={handleLogout} />

      <main className="flex-1 p-8">
        <div className="max-w mx-auto bg-white rounded-xl shadow p-6">
          <h1 className="text-2xl font-bold mb-6">
            {currentFY} {currentMonth} Forecast Upload
          </h1>
          <div className="text-sm text-gray-500 mb-10">
            For{" "}
            <span className="font-semibold">
              {localStorage.getItem("name")}
            </span>
          </div>

          <table className="table w-full">
            <thead>
              <tr>
                <th>Week</th>
                <th>Date Range</th>
                <th>Forecasted Perm Rev</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <tr key={idx}>
                  <td>Week {row.week}</td>
                  <td className="text-sm text-gray-500">{row.range}</td>
                  <td>
                    <input
                      type="number"
                      className="w-full bg-transparent focus:outline-none"
                      placeholder="$"
                      value={row.revenue}
                      onChange={(e) =>
                        handleChange(idx, "revenue", e.target.value)
                      }
                    />
                  </td>
                  <td>
                    <input
                      type="text"
                      className="w-full bg-transparent focus:outline-none"
                      placeholder="Optional notes"
                      value={row.notes}
                      onChange={(e) =>
                        handleChange(idx, "notes", e.target.value)
                      }
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <button className="btn btn-primary mt-6" onClick={handleSubmit}>
            Upload Forecast
          </button>
        </div>
      </main>
    </div>
  );
}

export default Upload;
