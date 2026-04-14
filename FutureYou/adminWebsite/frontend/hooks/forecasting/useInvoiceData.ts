"use client";

import { useState, useEffect, useCallback } from "react";
import { fcFetchInvoices, type InvoiceRow } from "@/lib/forecasting-api";
import {
  getCached,
  setCache,
  clearCache,
  INVOICE_CACHE_KEY,
  PREV_INVOICE_CACHE_KEY,
} from "@/lib/forecasting-cache";
import { getCurrentMonthInfo } from "@/lib/calendar";

export interface InvoiceState {
  currentData: InvoiceRow[];
  prevData: InvoiceRow[];
  loading: boolean;
  error: string | null;
  lastFetchedAt: number | null;
  refresh: () => void;
}

export function useInvoiceData(): InvoiceState {
  const { currentMonth, currentFY, previousMonth, previousMonthFY } = getCurrentMonthInfo();

  const [currentData, setCurrentData] = useState<InvoiceRow[]>([]);
  const [prevData, setPrevData]       = useState<InvoiceRow[]>([]);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState<string | null>(null);
  const [lastFetchedAt, setLastFetchedAt] = useState<number | null>(null);
  const [forceRefresh, setForceRefresh] = useState(0);

  const refresh = useCallback(() => {
    clearCache(INVOICE_CACHE_KEY);
    clearCache(PREV_INVOICE_CACHE_KEY);
    setForceRefresh((n) => n + 1);
  }, []);

  useEffect(() => {
    const cached        = getCached<InvoiceRow[]>(INVOICE_CACHE_KEY);
    const cachedPrev    = getCached<InvoiceRow[]>(PREV_INVOICE_CACHE_KEY);

    if (cached && cachedPrev) {
      setCurrentData(cached);
      setPrevData(cachedPrev);
      // Recover fetchedAt from the raw localStorage entry for display
      try {
        const raw = localStorage.getItem(INVOICE_CACHE_KEY);
        if (raw) setLastFetchedAt(JSON.parse(raw).fetchedAt);
      } catch { /* ignore */ }
      return;
    }

    setLoading(true);
    setError(null);

    Promise.all([
      fcFetchInvoices(currentFY, currentMonth),
      fcFetchInvoices(previousMonthFY, previousMonth),
    ])
      .then(([cur, prev]) => {
        setCurrentData(cur);
        setPrevData(prev);
        setCache(INVOICE_CACHE_KEY, cur);
        setCache(PREV_INVOICE_CACHE_KEY, prev);
        setLastFetchedAt(Date.now());
      })
      .catch((err) => {
        console.error("Failed to fetch invoice data:", err);
        setError("Failed to load invoice data. Please try again.");
      })
      .finally(() => setLoading(false));
  }, [currentFY, currentMonth, previousMonthFY, previousMonth, forceRefresh]);

  return { currentData, prevData, loading, error, lastFetchedAt, refresh };
}
