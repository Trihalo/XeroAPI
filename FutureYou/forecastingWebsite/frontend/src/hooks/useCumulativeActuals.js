// src/hooks/useCumulativeActuals.js
import { useMemo } from "react";
import {
  initializeWeeklyMap,
  computeCumulativeTotals,
} from "../utils/calcHelpers";
import { getStoredInvoiceData } from "../utils/getInvoiceInfo";
import { allAreas, allRecruiters } from "../data/recruiterMapping";

export function useCumulativeActuals(currentMonth, currentFY, weeks) {
  const invoices = getStoredInvoiceData();

  return useMemo(() => {
    const actualsByRecruiterWeek = initializeWeeklyMap(allRecruiters, weeks);
    const actualsByArea = initializeWeeklyMap(allAreas, weeks);

    invoices.forEach(
      ({ Consultant, Area, Week, Margin, FutureYouMonth, FinancialYear }) => {
        if (FutureYouMonth === currentMonth && FinancialYear === currentFY) {
          const week = Number(Week);
          const margin = Number(Margin || 0);
          if (actualsByRecruiterWeek[Consultant]?.[week] !== undefined)
            actualsByRecruiterWeek[Consultant][week] += margin;
          if (actualsByArea[Area]?.[week] !== undefined)
            actualsByArea[Area][week] += margin;
        }
      }
    );

    const cumulativeActuals = computeCumulativeTotals(actualsByArea);
    const cumulativeActualsByRecruiter = computeCumulativeTotals(
      actualsByRecruiterWeek
    );

    return {
      actualsByRecruiterWeek,
      actualsByArea,
      cumulativeActuals,
      cumulativeActualsByRecruiter,
    };
  }, [currentMonth, currentFY, weeks, invoices]);
}
