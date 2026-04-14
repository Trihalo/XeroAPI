"use client";

import { useEffect, useState } from "react";
import { fcFetchForecastWeekly } from "@/lib/forecasting-api";

export function useSubmittedRecruiters(
  currentFY: string,
  currentMonth: string,
  currentWeekIndex: number,
): Set<string> {
  const [submitted, setSubmitted] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!currentFY || !currentMonth || !currentWeekIndex) return;
    fcFetchForecastWeekly(currentFY, currentMonth, currentWeekIndex).then((rows) => {
      setSubmitted(new Set(rows.map((r) => r.name)));
    });
  }, [currentFY, currentMonth, currentWeekIndex]);

  return submitted;
}
