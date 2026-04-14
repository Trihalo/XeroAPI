"use client";

import { useMemo } from "react";
import { initializeWeeklyMap, computeCumulativeTotals } from "@/lib/calcHelpers";
import type { InvoiceRow } from "@/lib/forecasting-api";

export function useCumulativeActuals(
  currentMonth: string,
  currentFY: string,
  weeks: number[],
  allRecruiters: string[],
  allAreas: string[],
  invoices: InvoiceRow[],
) {
  return useMemo(() => {
    const actualsByRecruiterWeek = initializeWeeklyMap(allRecruiters, weeks);
    const actualsByArea          = initializeWeeklyMap(allAreas, weeks);

    invoices.forEach(({ Consultant, Area, Week, Margin, FutureYouMonth, FinancialYear }) => {
      if (FutureYouMonth !== currentMonth || FinancialYear !== currentFY) return;
      const week   = Number(Week);
      const margin = Number(Margin || 0);
      if (actualsByRecruiterWeek[Consultant]?.[week] !== undefined)
        actualsByRecruiterWeek[Consultant][week] += margin;
      if (actualsByArea[Area]?.[week] !== undefined)
        actualsByArea[Area][week] += margin;
    });

    return {
      actualsByRecruiterWeek,
      actualsByArea,
      cumulativeActuals:            computeCumulativeTotals(actualsByArea),
      cumulativeActualsByRecruiter: computeCumulativeTotals(actualsByRecruiterWeek),
    };
  }, [currentMonth, currentFY, weeks, allRecruiters, allAreas, invoices]);
}
