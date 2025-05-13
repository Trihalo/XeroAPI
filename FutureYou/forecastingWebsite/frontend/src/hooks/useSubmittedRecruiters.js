import { useEffect, useState } from "react";
import { fetchForecastWeekly } from "../api";
import { getCurrentMonthInfo } from "../utils/getCurrentMonthInfo";
import calendar from "../data/calendar";

export function useSubmittedRecruiters() {
  const [submittedRecruiters, setSubmittedRecruiters] = useState(new Set());

  const { currentMonth, currentFY, currentWeekIndex } =
    getCurrentMonthInfo(calendar);

  // const currentWeekIndex = 2; // Hardcoded for testing
  useEffect(() => {
    const fetchData = async () => {
      const result = await fetchForecastWeekly(
        currentFY,
        currentMonth,
        currentWeekIndex
      );

      const names = result.map((item) => item.name);
      setSubmittedRecruiters(new Set(names));
    };

    fetchData();
  }, [currentFY, currentMonth, currentWeekIndex]);

  return submittedRecruiters;
}
