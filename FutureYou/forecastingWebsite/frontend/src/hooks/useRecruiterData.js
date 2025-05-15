// src/hooks/useRecruiterData.js
import { useEffect, useState, useMemo } from "react";
import { getRecruiters, getAreas } from "../api"; // Adjust path as needed

export function useRecruiterData(refreshKey = 0) {
  const [recruiters, setRecruiters] = useState([]);
  const [areas, setAreas] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const r = await getRecruiters(); // [{ name, area }]
        const a = await getAreas(); // [{ name, headcount }]
        setRecruiters(r);
        setAreas(a);
      } catch (err) {
        console.error("❌ Error loading recruiter data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetch();
  }, [refreshKey]); // 🔁 re-fetch if refreshKey changes

  const AREA_ORDER = [
    "Accounting & Finance",
    "Legal",
    "Executive",
    "Sales, Marketing & Digital",
    "Technology",
    "Business Support",
    "SC, Eng & Manufacturing",
  ];

  const allRecruiters = useMemo(
    () => recruiters.map((r) => r.name),
    [recruiters]
  );

  const allAreas = useMemo(() => {
    const unsortedAreas = areas.map((a) => a.name);
    return AREA_ORDER.filter((name) => unsortedAreas.includes(name));
  }, [areas]);

  const summaryMapping = useMemo(() => {
    return allAreas.reduce((acc, area) => {
      acc[area] = recruiters.filter((r) => r.area === area).map((r) => r.name);
      return acc;
    }, {});
  }, [recruiters, allAreas]);

  const headcountByArea = useMemo(() => {
    return areas.reduce((acc, a) => {
      acc[a.name] = a.headcount;
      return acc;
    }, {});
  }, [areas]);

  return {
    loading,
    recruiters,
    areas,
    allRecruiters,
    allAreas,
    summaryMapping,
    headcountByArea,
  };
}
