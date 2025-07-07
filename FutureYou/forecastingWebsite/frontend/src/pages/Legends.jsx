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
  const fy = "FY26";

  const { allRecruiters, loading: recruiterLoading } = useRecruiterData();
  const [selectedQuarter, setSelectedQuarter] = useState("Total");
  const [viewMode, setViewMode] = useState("Consultant");

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      const data = await fetchLegendsRevenue(fy);
      setRevenueData(data);
      console.log("Legends data loaded:", data);
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

  const getAreaMargin = (area, type) => {
    if (selectedQuarter === "Total") {
      return ["Q1", "Q2", "Q3", "Q4"].reduce((sum, q) => {
        return sum + (areaTypeLookup[area]?.[q]?.[type] || 0);
      }, 0);
    }
    return areaTypeLookup[area]?.[selectedQuarter]?.[type] || 0;
  };

  const uniqueConsultants = Array.from(
    new Set(
      consultantTypeTotals
        .filter((row) => allRecruiters.includes(row.Consultant))
        .map((row) => row.Consultant)
    )
  );

  const uniqueAreas = Array.from(
    new Set(
      consultantTypeTotals
        .filter((row) => allRecruiters.includes(row.Consultant))
        .map((row) => row.Area)
    )
  );

  const areaTypeLookup = consultantTypeTotals.reduce((acc, row) => {
    const { Area, Type, Quarter, TotalMargin } = row;
    if (!acc[Area]) acc[Area] = {};
    if (!acc[Area][Quarter]) acc[Area][Quarter] = { Perm: 0, Temp: 0 };
    acc[Area][Quarter][Type] = (acc[Area][Quarter][Type] || 0) + TotalMargin;
    return acc;
  }, {});

  const sortedConsultants = uniqueConsultants.sort((a, b) => {
    const aTotal =
      getConsultantMargin(a, "Perm") + getConsultantMargin(a, "Temp");
    const bTotal =
      getConsultantMargin(b, "Perm") + getConsultantMargin(b, "Temp");
    return bTotal - aTotal;
  });

  const sortedAreas = uniqueAreas.sort((a, b) => {
    const aTotal = getAreaMargin(a, "Perm") + getAreaMargin(a, "Temp");
    const bTotal = getAreaMargin(b, "Perm") + getAreaMargin(b, "Temp");
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

              <div className="mb-6 flex gap-4 items-center">
                <div className="flex items-center gap-2">
                  <span className="text-sm">Group By:</span>
                  <div className="btn-group">
                    <button
                      className={`btn btn-sm gap-1 ${
                        viewMode === "Consultant"
                          ? "bg-secondary text-white"
                          : ""
                      }`}
                      onClick={() => setViewMode("Consultant")}
                    >
                      Consultant
                    </button>
                    <button
                      className={`btn btn-sm gap-1 ${
                        viewMode === "Area" ? "bg-secondary text-white" : ""
                      }`}
                      onClick={() => setViewMode("Area")}
                    >
                      Area
                    </button>
                  </div>
                </div>
              </div>

              <div className="w-full max-w-2xl overflow-x-auto rounded-lg border border-gray-200 mb-6">
                <table className="min-w-full table-fixed text-sm text-left">
                  <thead className="bg-base-300 text-base-content border-gray-200">
                    <tr>
                      <th className="w-2/5 py-2 px-4 whitespace-nowrap">
                        {viewMode === "Consultant" ? "Consultant" : "Area"}
                      </th>
                      <th className="w-1/5 py-2 px-4 text-right whitespace-nowrap">
                        Perm
                      </th>
                      <th className="w-1/5 py-2 px-4 text-right whitespace-nowrap">
                        Temp
                      </th>
                      <th className="w-1/5 py-2 px-4 text-right whitespace-nowrap">
                        Total
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {(viewMode === "Consultant"
                      ? sortedConsultants
                      : sortedAreas
                    ).map((item, index) => {
                      if (viewMode === "Consultant") {
                        const perm = getConsultantMargin(item, "Perm");
                        const temp = getConsultantMargin(item, "Temp");
                        const total = perm + temp;

                        return (
                          <tr
                            key={item}
                            className={`border-b border-gray-200 ${
                              index % 2 === 0 ? "bg-base-100" : "bg-base-200"
                            }`}
                          >
                            <td className="py-2 px-4 whitespace-nowrap">
                              {item}
                            </td>
                            <td className="py-2 px-4 text-right whitespace-nowrap">
                              {Math.round(perm).toLocaleString("en-AU")}
                            </td>
                            <td className="py-2 px-4 text-right whitespace-nowrap">
                              {Math.round(temp).toLocaleString("en-AU")}
                            </td>
                            <td className="py-2 px-4 text-right font-semibold whitespace-nowrap">
                              {Math.round(total).toLocaleString("en-AU")}
                            </td>
                          </tr>
                        );
                      } else {
                        const perm = getAreaMargin(item, "Perm");
                        const temp = getAreaMargin(item, "Temp");
                        const total = perm + temp;

                        return (
                          <tr
                            key={item}
                            className={`border-b border-gray-200 ${
                              index % 2 === 0 ? "bg-base-100" : "bg-base-200"
                            }`}
                          >
                            <td className="py-2 px-4 whitespace-nowrap">
                              {item}
                            </td>
                            <td className="py-2 px-4 text-right whitespace-nowrap">
                              {Math.round(perm).toLocaleString("en-AU")}
                            </td>
                            <td className="py-2 px-4 text-right whitespace-nowrap">
                              {Math.round(temp).toLocaleString("en-AU")}
                            </td>
                            <td className="py-2 px-4 text-right font-semibold whitespace-nowrap">
                              {Math.round(total).toLocaleString("en-AU")}
                            </td>
                          </tr>
                        );
                      }
                    })}
                    <tr className="font-semibold bg-base-300 border-t border-gray-300">
                      <td className="py-2 px-4 whitespace-nowrap">Total</td>
                      <td className="py-2 px-4 text-right whitespace-nowrap">
                        {Math.round(
                          (viewMode === "Consultant"
                            ? sortedConsultants
                            : sortedAreas
                          ).reduce(
                            (sum, item) =>
                              sum +
                              (viewMode === "Consultant"
                                ? getConsultantMargin(item, "Perm")
                                : getAreaMargin(item, "Perm")),
                            0
                          )
                        ).toLocaleString("en-AU")}
                      </td>
                      <td className="py-2 px-4 text-right whitespace-nowrap">
                        {Math.round(
                          (viewMode === "Consultant"
                            ? sortedConsultants
                            : sortedAreas
                          ).reduce(
                            (sum, item) =>
                              sum +
                              (viewMode === "Consultant"
                                ? getConsultantMargin(item, "Temp")
                                : getAreaMargin(item, "Temp")),
                            0
                          )
                        ).toLocaleString("en-AU")}
                      </td>
                      <td className="py-2 px-4 text-right whitespace-nowrap">
                        {Math.round(
                          (viewMode === "Consultant"
                            ? sortedConsultants
                            : sortedAreas
                          ).reduce((sum, item) => {
                            const perm =
                              viewMode === "Consultant"
                                ? getConsultantMargin(item, "Perm")
                                : getAreaMargin(item, "Perm");
                            const temp =
                              viewMode === "Consultant"
                                ? getConsultantMargin(item, "Temp")
                                : getAreaMargin(item, "Temp");
                            return sum + perm + temp;
                          }, 0)
                        ).toLocaleString("en-AU")}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

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
