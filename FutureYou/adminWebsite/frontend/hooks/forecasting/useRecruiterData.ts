"use client";

import { useEffect, useState, useMemo } from "react";
import { fcGetRecruiters, fcGetAreas, type Recruiter, type Area } from "@/lib/forecasting-api";

const AREA_ORDER = [
  "Accounting & Finance",
  "Legal",
  "Executive",
  "Sales, Marketing & Digital",
  "Technology",
  "Business Support",
  "SC, Eng & Manufacturing",
];

export function useRecruiterData(refreshKey = 0) {
  const [recruiters, setRecruiters] = useState<Recruiter[]>([]);
  const [areas, setAreas]           = useState<Area[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([fcGetRecruiters(), fcGetAreas()])
      .then(([r, a]) => {
        setRecruiters(r);
        setAreas(a);
      })
      .catch((err) => {
        console.error("Failed to load recruiter data:", err);
        setError("Failed to load recruiter data.");
      })
      .finally(() => setLoading(false));
  }, [refreshKey]);

  const allRecruiters = useMemo(() => recruiters.map((r) => r.name), [recruiters]);

  const allAreas = useMemo(() => {
    const names = new Set(areas.map((a) => a.name));
    return AREA_ORDER.filter((n) => names.has(n));
  }, [areas]);

  const summaryMapping = useMemo<Record<string, string[]>>(() => {
    return allAreas.reduce(
      (acc, area) => {
        acc[area] = recruiters.filter((r) => r.area === area).map((r) => r.name);
        return acc;
      },
      {} as Record<string, string[]>,
    );
  }, [recruiters, allAreas]);

  const headcountByArea = useMemo<Record<string, number>>(() => {
    return areas.reduce(
      (acc, a) => {
        acc[a.name] = a.headcount;
        return acc;
      },
      {} as Record<string, number>,
    );
  }, [areas]);

  const recruiterToArea = useMemo<Record<string, string>>(() => {
    const map: Record<string, string> = {};
    Object.entries(summaryMapping).forEach(([area, names]) => {
      names.forEach((name) => {
        map[name] = area;
      });
    });
    return map;
  }, [summaryMapping]);

  return { loading, error, recruiters, areas, allRecruiters, allAreas, summaryMapping, headcountByArea, recruiterToArea };
}
