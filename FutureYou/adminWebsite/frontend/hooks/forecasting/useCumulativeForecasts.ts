"use client";

import { useState, useEffect } from "react";
import { fcFetchForecastSummary, type ForecastSummaryRow } from "@/lib/forecasting-api";

export function useCumulativeForecasts(
  currentFY: string,
  currentMonth: string,
  summaryMapping: Record<string, string[]> | null,
) {
  const [rawForecastRows, setRawForecastRows]                           = useState<ForecastSummaryRow[]>([]);
  const [cumulativeForecasts, setCumulativeForecasts]                   = useState<Record<string, Record<number, number>>>({});
  const [cumulativeForecastsByRecruiter, setCumulativeForecastsByRecruiter] = useState<Record<string, Record<number, number>>>({});
  const [forecastByAreaForWeek, setForecastByAreaForWeek]               = useState<Record<string, Record<number, number>>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    if (!summaryMapping || Object.keys(summaryMapping).length === 0) return;

    setLoading(true);
    setError(null);

    fcFetchForecastSummary(currentFY, currentMonth)
      .then((summary) => {
        // Attach area to each row
        const enriched = summary.map((entry) => {
          const area = Object.entries(summaryMapping).find(([, names]) =>
            names.includes(entry.name),
          )?.[0];
          return { ...entry, area: area ?? "Unknown" };
        });

        setRawForecastRows(enriched);

        const forecasts:   Record<string, Record<number, number>> = {};
        const byRecruiter: Record<string, Record<number, number>> = {};
        const byAreaWeek:  Record<string, Record<number, number>> = {};

        enriched.forEach(({ week, total_revenue, uploadWeek, area, name }) => {
          const w       = Number(week);
          const u       = Number(uploadWeek);
          const revenue = Number(total_revenue);

          if (!forecasts[area])            forecasts[area] = {};
          if (!forecasts[area][u])         forecasts[area][u] = 0;
          if (w >= u) forecasts[area][u] += revenue;

          if (!byRecruiter[name])          byRecruiter[name] = {};
          if (!byRecruiter[name][u])       byRecruiter[name][u] = 0;
          if (w >= u) byRecruiter[name][u] += revenue;

          if (w === u) {
            if (!byAreaWeek[area])         byAreaWeek[area] = {};
            if (!byAreaWeek[area][w])      byAreaWeek[area][w] = 0;
            byAreaWeek[area][w] += revenue;
          }
        });

        setCumulativeForecasts(forecasts);
        setCumulativeForecastsByRecruiter(byRecruiter);
        setForecastByAreaForWeek(byAreaWeek);
      })
      .catch((err) => {
        console.error("Failed to fetch forecasts:", err);
        setError("Failed to load forecast data.");
      })
      .finally(() => setLoading(false));
  }, [currentFY, currentMonth, summaryMapping]);

  return { rawForecastRows, cumulativeForecasts, cumulativeForecastsByRecruiter, forecastByAreaForWeek, loading, error };
}
