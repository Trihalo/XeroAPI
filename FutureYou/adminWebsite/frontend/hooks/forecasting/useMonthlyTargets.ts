"use client";

import { useState, useEffect } from "react";
import { fcFetchMonthlyTargets } from "@/lib/forecasting-api";

export function useMonthlyTargets(selectedFY: string): Record<string, number> {
  const [targetByMonth, setTargetByMonth] = useState<Record<string, number>>({});

  useEffect(() => {
    fcFetchMonthlyTargets(selectedFY).then((data) => {
      const byMonth: Record<string, number> = {};
      data.forEach((row) => {
        byMonth[row.Month] = row.Target;
      });
      setTargetByMonth(byMonth);
    });
  }, [selectedFY]);

  return targetByMonth;
}
