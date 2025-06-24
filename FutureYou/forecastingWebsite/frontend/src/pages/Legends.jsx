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
  const fy = "FY25";

  const { allRecruiters, loading: recruiterLoading } = useRecruiterData();
  const [selectedQuarter, setSelectedQuarter] = useState("Total");

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      const data = await fetchLegendsRevenue(fy);
      setRevenueData(data);
      setLoading(false);
    };
    loadData();
  }, [fy]);

  const { consultantTotals = [], consultantTypeTotals = [] } = revenueData;

  const isLoading = loading || recruiterLoading;

  const typeLookup = consultantTypeTotals.reduce((acc, row) => {
    const { Consultant, Type, Quarter, TotalMargin } = row;
    if (!acc[Consultant]) acc[Consultant] = {};
    if (!acc[Consultant][Quarter])
      acc[Consultant][Quarter] = { Perm: 0, Temp: 0 };
    acc[Consultant][Quarter][Type] = TotalMargin;
    return acc;
  }, {});

  const getConsultantMargin = (consultant, type) => {
    if (selectedQuarter === "Total") {
      return ["Q1", "Q2", "Q3", "Q4"].reduce((sum, q) => {
        return sum + (typeLookup[consultant]?.[q]?.[type] || 0);
      }, 0);
    }
    return typeLookup[consultant]?.[selectedQuarter]?.[type] || 0;
  };

  const uniqueConsultants = Array.from(
    new Set(
      consultantTotals
        .filter((row) => allRecruiters.includes(row.Consultant))
        .map((row) => row.Consultant)
    )
  );

  const sortedConsultants = uniqueConsultants.sort((a, b) => {
    const aTotal =
      getConsultantMargin(a, "Perm") + getConsultantMargin(a, "Temp");
    const bTotal =
      getConsultantMargin(b, "Perm") + getConsultantMargin(b, "Temp");
    return bTotal - aTotal;
  });

  return (
    <div className="min-h-screen bg-base-300 text-base-content flex flex-col">
      <TopNavbar userName={localStorage.getItem("name") || "User"} />

      <div className="flex-1 p-8">
        <div className="bg-base-100 rounded-xl shadow p-12 relative mb-15">
          <h1 className="text-2xl font-bold mb-10">Legends Table - {fy}</h1>

          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-10">
              <div className="w-6 h-6 border-4 border-gray-300 border-t-primary rounded-full animate-spin"></div>
              <p className="mt-2 text-gray-500 text-sm">
                Loading legends table...
              </p>
            </div>
          ) : sortedConsultants.length === 0 ? (
            <div>No data available.</div>
          ) : (
            <>
              <div className="mb-6 flex gap-4">
                {["Total", "Q1", "Q2", "Q3", "Q4"].map((label) => (
                  <button
                    key={label}
                    onClick={() => setSelectedQuarter(label)}
                    className={`px-4 py-2 rounded-lg ${
                      selectedQuarter === label
                        ? "bg-secondary text-white"
                        : "bg-base-300 text-base-content"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              <table className="text-sm text-left border border-gray-200 mb-6 rounded-lg">
                <thead className="bg-base-300 text-base-content border-gray-200">
                  <tr>
                    <th className="py-2 px-4 text-left min-w-[200px]">
                      Consultant
                    </th>
                    <th className="py-2 px-4 text-right min-w-[200px]">Perm</th>
                    <th className="py-2 px-4 text-right min-w-[200px]">Temp</th>
                    <th className="py-2 px-4 text-right min-w-[200px]">
                      Total
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sortedConsultants.map((consultant, index) => {
                    const temp = getConsultantMargin(consultant, "Temp");
                    const perm = getConsultantMargin(consultant, "Perm");
                    const total = temp + perm;

                    return (
                      <tr
                        key={consultant}
                        className={`border-b border-gray-200 ${
                          index % 2 === 0 ? "bg-base-100" : "bg-base-200"
                        }`}
                      >
                        <td className="py-2 px-4">{consultant}</td>
                        <td className="py-2 px-4 text-right">
                          {Math.round(perm).toLocaleString("en-AU")}
                        </td>
                        <td className="py-2 px-4 text-right">
                          {Math.round(temp).toLocaleString("en-AU")}
                        </td>
                        <td className="py-2 px-4 text-right font-semibold">
                          {Math.round(total).toLocaleString("en-AU")}
                        </td>
                      </tr>
                    );
                  })}

                  {/* Totals Row */}
                  <tr className="font-semibold bg-base-300 border-t border-gray-300">
                    <td className="py-2 px-4">Total</td>
                    <td className="py-2 px-4 text-right">
                      {Math.round(
                        sortedConsultants.reduce(
                          (sum, c) => sum + getConsultantMargin(c, "Perm"),
                          0
                        )
                      ).toLocaleString("en-AU")}
                    </td>
                    <td className="py-2 px-4 text-right">
                      {Math.round(
                        sortedConsultants.reduce(
                          (sum, c) => sum + getConsultantMargin(c, "Temp"),
                          0
                        )
                      ).toLocaleString("en-AU")}
                    </td>
                    <td className="py-2 px-4 text-right">
                      {Math.round(
                        sortedConsultants.reduce((sum, c) => {
                          const temp = getConsultantMargin(c, "Temp");
                          const perm = getConsultantMargin(c, "Perm");
                          return sum + temp + perm;
                        }, 0)
                      ).toLocaleString("en-AU")}
                    </td>
                  </tr>
                </tbody>
              </table>

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
