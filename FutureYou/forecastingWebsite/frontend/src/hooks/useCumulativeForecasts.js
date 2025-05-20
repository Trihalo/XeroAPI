// src/hooks/useCumulativeForecasts.js
import { useState, useEffect } from "react";
import { fetchForecastSummary } from "../api";

export function useCumulativeForecasts(
  currentFY,
  currentMonth,
  summaryMapping
) {
  const [rawForecastRows, setRawForecastRows] = useState([]);
  const [cumulativeForecasts, setCumulativeForecasts] = useState({});
  const [cumulativeForecastsByRecruiter, setCumulativeForecastsByRecruiter] =
    useState({});
  const [forecastByAreaForWeek, setForecastByAreaForWeek] = useState({});

  useEffect(() => {
    const fetchData = async () => {
      const summary = await fetchForecastSummary(currentFY, currentMonth);

      summary.forEach((entry) => {
        for (const [area, names] of Object.entries(summaryMapping)) {
          if (names.includes(entry.name)) {
            entry.area = area;
            break;
          }
        }
      });

      setRawForecastRows(summary);

      const forecasts = {};
      const forecastsByRecruiter = {};
      const forecastByArea = {};

      summary.forEach(({ week, total_revenue, uploadWeek, area, name }) => {
        const w = Number(week);
        const u = Number(uploadWeek);
        const revenue = Number(total_revenue);

        if (!forecasts[area]) forecasts[area] = {};
        if (!forecasts[area][u]) forecasts[area][u] = 0;
        if (w >= u) forecasts[area][u] += revenue;

        if (!forecastsByRecruiter[name]) forecastsByRecruiter[name] = {};
        if (!forecastsByRecruiter[name][u]) forecastsByRecruiter[name][u] = 0;
        if (w >= u) forecastsByRecruiter[name][u] += revenue;

        if (w === u) {
          if (!forecastByArea[area]) forecastByArea[area] = {};
          if (!forecastByArea[area][w]) forecastByArea[area][w] = 0;
          forecastByArea[area][w] += revenue;
        }
      });

      setCumulativeForecasts(forecasts);
      setCumulativeForecastsByRecruiter(forecastsByRecruiter);
      setForecastByAreaForWeek(forecastByArea);
    };

    if (summaryMapping) {
      fetchData();
    }
  }, [currentFY, currentMonth, summaryMapping]);

  return {
    rawForecastRows,
    cumulativeForecasts,
    cumulativeForecastsByRecruiter,
    forecastByAreaForWeek,
  };
}
