// src/hooks/useMonthlyTargets.js
import { useState, useEffect } from "react";
import { fetchMonthlyTargets } from "../api";

export function useMonthlyTargets(selectedFY) {
  const [targetByMonth, setTargetByMonth] = useState({});

  useEffect(() => {
    const fetchAndSetTargetSummary = async () => {
      const data = await fetchMonthlyTargets(selectedFY);
      const byMonth = {};
      data.forEach((row) => {
        byMonth[row.Month] = row.Target;
      });
      setTargetByMonth(byMonth);
    };

    fetchAndSetTargetSummary();
  }, [selectedFY]);

  return targetByMonth;
}
