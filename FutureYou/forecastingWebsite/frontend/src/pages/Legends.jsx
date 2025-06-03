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
    if (!acc[row.Consultant]) {
      acc[row.Consultant] = {};
    }
    acc[row.Consultant][row.Type] = row.TotalMargin;
    return acc;
  }, {});

  const filteredConsultantTotals = consultantTotals.filter((row) =>
    allRecruiters.includes(row.Consultant)
  );

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
          ) : filteredConsultantTotals.length === 0 ? (
            <div>No data available.</div>
          ) : (
            <>
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
                  {filteredConsultantTotals.map((row, index) => {
                    const consultant = row.Consultant;
                    const total = row.TotalMargin || 0;
                    const temp = typeLookup[consultant]?.["Temp"] || 0;
                    const perm = typeLookup[consultant]?.["Perm"] || 0;

                    return (
                      <tr
                        key={index}
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

                  {/* Total row */}
                  <tr className="font-semibold bg-base-300 border-t border-gray-300">
                    <td className="py-2 px-4">Total</td>
                    <td className="py-2 px-4 text-right">
                      {Math.round(
                        filteredConsultantTotals.reduce((sum, row) => {
                          const perm =
                            typeLookup[row.Consultant]?.["Perm"] || 0;
                          return sum + perm;
                        }, 0)
                      ).toLocaleString("en-AU")}
                    </td>
                    <td className="py-2 px-4 text-right">
                      {Math.round(
                        filteredConsultantTotals.reduce((sum, row) => {
                          const temp =
                            typeLookup[row.Consultant]?.["Temp"] || 0;
                          return sum + temp;
                        }, 0)
                      ).toLocaleString("en-AU")}
                    </td>
                    <td className="py-2 px-4 text-right">
                      {Math.round(
                        filteredConsultantTotals.reduce(
                          (sum, row) => sum + (row.TotalMargin || 0),
                          0
                        )
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
