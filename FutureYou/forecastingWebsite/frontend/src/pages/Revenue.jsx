import TopNavbar from "../components/TopNavbar.jsx";
import { useCumulativeActuals } from "../hooks/useCumulativeActuals.js";
import { useCumulativeForecasts } from "../hooks/useCumulativeForecasts.js";
import { useRecruiterData } from "../hooks/useRecruiterData";
import { useMonthlyTargets } from "../hooks/useMonthlyTargets.js";
import calendar from "../data/calendar.js";
import { getCurrentMonthInfo } from "../utils/getCurrentMonthInfo.js";
import {
  buildRecruiterTogetherByWeek,
  groupRecruitersByAreaWeek,
} from "../utils/calcHelpers";

function Revenue() {
  const { currentFY, currentMonth, currentWeekIndex, weeksInMonth } =
    getCurrentMonthInfo(calendar);
  const weeks = weeksInMonth.map((w) => w.week);
  const { summaryMapping, allRecruiters, allAreas, headcountByArea } =
    useRecruiterData();
  const targetByMonth = useMonthlyTargets(currentFY);
  const lastUpdatedTime = localStorage.getItem(
    "revenue_table_last_modified_time"
  );

  const { actualsByArea, cumulativeActuals, cumulativeActualsByRecruiter } =
    useCumulativeActuals(
      currentMonth,
      currentFY,
      weeks,
      allRecruiters,
      allAreas
    );

  const { forecastByAreaForWeek, cumulativeForecastsByRecruiter } =
    useCumulativeForecasts(currentFY, currentMonth, summaryMapping);

  const recruiterToArea = {};
  Object.entries(summaryMapping).forEach(([area, recruiters]) => {
    recruiters.forEach((recruiter) => {
      recruiterToArea[recruiter] = area;
    });
  });

  const recruiterTogetherByWeek = buildRecruiterTogetherByWeek({
    allRecruiters,
    recruiterToArea,
    cumulativeActualsByRecruiter,
    cumulativeForecastsByRecruiter,
  });

  const mtdRevenueByGroup = groupRecruitersByAreaWeek(recruiterTogetherByWeek);

  const rows = allAreas.map((area) => {
    const forecastThisWeek =
      forecastByAreaForWeek[area]?.[currentWeekIndex] || 0;
    const mtdRevenue = cumulativeActuals[area]?.[currentWeekIndex] || 0;
    const actualThisWeek = actualsByArea[area]?.[currentWeekIndex] || 0;
    const forecastMTD = mtdRevenueByGroup[area]?.[currentWeekIndex] || 0;
    const headcount = headcountByArea[area] || 0;
    const forecastPerHead = headcount > 0 ? forecastMTD / headcount : undefined;
    const actualPerHead = headcount > 0 ? mtdRevenue / headcount : undefined;

    return {
      area,
      forecastWeek: forecastThisWeek,
      actualWeek: actualThisWeek,
      variance: Math.round(actualThisWeek - forecastThisWeek, 0),
      mtdRevenue,
      forecastMTD,
      headcount,
      forecastPerHead,
      actualPerHead,
    };
  });

  const totals = rows.reduce(
    (acc, row) => {
      acc.forecastWeek += row.forecastWeek;
      acc.actualWeek += row.actualWeek;
      acc.variance += row.variance;
      acc.mtdRevenue += row.mtdRevenue;
      acc.forecastMTD += row.forecastMTD;
      acc.headcount += row.headcount;
      return acc;
    },
    {
      forecastWeek: 0,
      actualWeek: 0,
      variance: 0,
      mtdRevenue: 0,
      forecastMTD: 0,
      headcount: 0,
    }
  );

  const format = (v, showZero = false) =>
    v || (showZero ? "0" : "-")
      ? `${Math.round(v).toLocaleString("en-AU")}`
      : "-";

  const formatVariance = (v) =>
    v < 0 ? (
      <span className="text-secondary">
        ({Math.abs(v).toLocaleString("en-AU")})
      </span>
    ) : v > 0 ? (
      `${Math.round(v).toLocaleString("en-AU")}`
    ) : (
      "-"
    );

  return (
    <div className="min-h-screen bg-gray-200 text-base-content flex flex-col">
      <TopNavbar userName={localStorage.getItem("name") || "User"} />
      <div className="flex-1 p-8">
        <div className="max-w mx-auto bg-white rounded-xl shadow p-10 pb-20">
          <h1 className="text-xl font-bold mb-4">
            {currentMonth} Week {currentWeekIndex} Forecast vs Actual Revenue
          </h1>
          <div className="text-sm text-gray-500 mb-4">
            {targetByMonth[currentMonth] && (
              <span>
                Target:{" "}
                <b>${targetByMonth[currentMonth].toLocaleString("en-AU")}</b>
              </span>
            )}
          </div>

          <div className="overflow-x-auto border border-gray-300 mb-6 rounded-lg">
            <div className="min-w-[900px]">
              <table className="table table-sm text-sm w-full">
                <thead className="bg-gray-100 border-b">
                  <tr>
                    <th className="text-left px-3 py-2"></th>
                    <th className="px-3 py-2 text-right border-x border-gray-200">
                      Forecast
                    </th>
                    <th className="px-3 py-2 text-right border-x border-gray-200">
                      Actual
                    </th>
                    <th className="px-3 py-2 text-right border-x border-gray-200">
                      Variances
                    </th>
                    <th className="px-3 py-2 text-right border-x border-gray-200">
                      Rev MTD
                    </th>
                    <th className="px-3 py-2 text-right border-x border-gray-200">
                      Forecast MTD
                    </th>
                    <th className="px-3 py-2 text-right border-x border-gray-200">
                      Headcount
                    </th>
                    <th className="px-3 py-2 text-right border-x border-gray-200">
                      Forecast Productivity
                    </th>
                    <th className="px-3 py-2 text-right border-l border-gray-200">
                      Actual Productivity
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.area} className="border-t">
                      <td className="px-3 py-2 border-r border-gray-200">
                        {r.area}
                      </td>
                      <td className="text-right px-3 py-2 border-x border-gray-200">
                        {format(r.forecastWeek)}
                      </td>
                      <td className="text-right px-3 py-2 border-x border-gray-200">
                        {format(r.actualWeek)}
                      </td>
                      <td className="text-right px-3 py-2 border-x border-gray-200">
                        {formatVariance(r.variance)}
                      </td>
                      <td className="text-right px-3 py-2 border-x border-gray-200">
                        {format(r.mtdRevenue)}
                      </td>
                      <td className="text-right px-3 py-2 border-x border-gray-200">
                        {format(r.forecastMTD)}
                      </td>
                      <td className="text-right px-3 py-2 border-x border-gray-200">
                        {r.headcount || "-"}
                      </td>
                      <td className="text-right px-3 py-2 border-x border-gray-200">
                        {format(r.forecastPerHead)}
                      </td>
                      <td className="text-right px-3 py-2 border-l border-gray-200">
                        {format(r.actualPerHead)}
                      </td>
                    </tr>
                  ))}
                  <tr className="font-bold border-t bg-gray-100">
                    <td className="px-3 py-2">Total</td>
                    <td className="px-3 py-2 text-right border-x border-gray-200">
                      {format(totals.forecastWeek)}
                    </td>
                    <td className="px-3 py-2 text-right border-x border-gray-200">
                      {format(totals.actualWeek)}
                    </td>
                    <td className="px-3 py-2 text-right border-x border-gray-200">
                      {formatVariance(
                        Math.round(totals.actualWeek - totals.forecastWeek, 0)
                      )}
                    </td>
                    <td className="px-3 py-2 text-right border-x border-gray-200">
                      {format(totals.mtdRevenue)}
                    </td>
                    <td className="px-3 py-2 text-right border-x border-gray-200">
                      {format(totals.forecastMTD)}
                    </td>
                    <td className="px-3 py-2 text-right border-x border-gray-200">
                      {totals.headcount.toFixed(1)}
                    </td>
                    <td className="px-3 py-2 text-right border-x border-gray-200">
                      {format(totals.forecastMTD / totals.headcount)}
                    </td>
                    <td className="px-3 py-2 text-right border-l border-gray-200">
                      {totals.headcount > 0
                        ? format(totals.mtdRevenue / totals.headcount)
                        : "-"}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          {lastUpdatedTime && (
            <div className="text-sm text-gray-500 mt-1">
              Actual data last updated: <b>{lastUpdatedTime}</b>
            </div>
          )}
        </div>
      </div>
      <div className="text-gray-400 p-5 text-right">
        For any issues, please contact Leo@trihalo.com.au
      </div>
    </div>
  );
}

export default Revenue;
