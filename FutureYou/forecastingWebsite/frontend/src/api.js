import axios from "axios";

const API_BASE_URL =
  import.meta.env.MODE === "development"
    ? "http://localhost:8080"
    : import.meta.env.VITE_API_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem("token");
  return {
    Authorization: token ? `Bearer ${token}` : "",
  };
};

export const login = async (username, password) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/login`, {
      username,
      password,
    });

    if (response.data.success) {
      return {
        success: true,
        message: response.data.message,
        token: response.data.token,
        role: response.data.role,
        name: response.data.name,
        revenue_table_last_modified_time:
          response.data.revenue_table_last_modified_time,
      };
    } else {
      console.error("API Error:", response.data.error);
      return { success: false, message: `❌ ${response.data.error}` };
    }
  } catch (error) {
    console.error("Request failed:", error);

    let errorMessage = "❌ Error contacting the backend.";
    if (error.response) {
      console.error("Backend Error:", error.response.data);
      errorMessage = `❌ ${error.response.data.error}`;
    } else if (error.request) {
      errorMessage =
        "❌ No response from the backend. Check if the server is running.";
    }

    return { success: false, message: errorMessage };
  }
};

export const changePassword = async (username, oldPassword, newPassword) => {
  const response = await fetch(`${API_BASE_URL}/change-password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ username, oldPassword, newPassword }),
  });

  return await response.json();
};

export const uploadForecastToBQ = async (rows) => {
  try {
    const uploadUser = localStorage.getItem("name") || "Unknown User";

    const enrichedRows = rows.map((row) => ({
      ...row,
      uploadUser,
    }));
    const response = await axios.post(
      `${API_BASE_URL}/forecasts`,
      { forecasts: enrichedRows },
      { headers: getAuthHeaders() }
    );
    if (response.data.success) {
      return { success: true, message: response.data.message };
    } else {
      console.error("Upload error:", response.data);
      alert(`❌ Upload failed: ${response.data.error || "Unknown error"}`);
      return { success: false };
    }
  } catch (error) {
    console.error("Request failed:", error);
    alert("❌ Failed to connect to backend.");
    return { success: false };
  }
};

export const fetchForecastForRecruiter = async (
  recruiterName,
  fy,
  month,
  weeksInMonth
) => {
  try {
    const res = await axios.get(
      `${API_BASE_URL}/forecasts/${encodeURIComponent(recruiterName)}`,
      {
        params: { fy, month },
        headers: getAuthHeaders(),
      }
    );
    const existing = res.data;
    return weeksInMonth.map((entry) => {
      const match = existing.find((e) => String(e.week) === String(entry.week));
      return {
        ...entry,
        revenue: match?.revenue != null ? String(match.revenue) : "",
        tempRevenue:
          match?.tempRevenue != null ? String(match.tempRevenue) : "",
        notes: match?.notes ?? "",
        name: recruiterName,
        uploadTimestamp: match?.uploadTimestamp ?? "",
        uploadUser: match?.uploadUser ?? "",
        uploadMonth: match?.uploadMonth ?? "",
        uploadWeek: match?.uploadWeek ?? "",
        uploadYear: match?.uploadYear ?? "",
      };
    });
  } catch (error) {
    console.error("❌ Forecast fetch failed:", error);

    // Return fallback empty rows
    return weeksInMonth.map((entry) => ({
      ...entry,
      revenue: "",
      tempRevenue: "",
      notes: "",
      name: recruiterName,
    }));
  }
};

export const fetchForecastSummary = async (fy, month) => {
  try {
    const res = await axios.get(`${API_BASE_URL}/forecasts/view`, {
      params: { fy, month },
      headers: getAuthHeaders(),
    });
    return res.data;
  } catch (error) {
    console.error("❌ Failed to fetch forecast summary:", error);
    return [];
  }
};

export const fetchForecastWeekly = async (fy, month, uploadWeek) => {
  try {
    const res = await axios.get(`${API_BASE_URL}/forecasts/weekly`, {
      params: { fy, month, uploadWeek },
      headers: getAuthHeaders(),
    });
    return res.data;
  } catch (error) {
    console.error("❌ Failed to fetch forecast weekly:", error);
    return [];
  }
};

export const submitMonthlyTarget = async ({ fy, month, amount }) => {
  try {
    const uploadUser = localStorage.getItem("name") || "Unknown User";
    const uploadTimestamp = new Date().toISOString();
    const response = await axios.post(
      `${API_BASE_URL}/monthly-targets`,
      {
        FinancialYear: fy,
        Month: month,
        Target: amount,
        uploadUser,
        uploadTimestamp,
      },
      {
        headers: getAuthHeaders(),
      }
    );
    if (response.data.success) {
      return { success: true, message: response.data.message };
    } else {
      console.error("❌ Submit target error:", response.data);
      return {
        success: false,
        message: response.data.error || "Unknown error",
      };
    }
  } catch (error) {
    console.error("❌ Request failed:", error);
    return { success: false, message: "Failed to connect to backend." };
  }
};

export const fetchMonthlyTargets = async (fy) => {
  try {
    const response = await axios.get(`${API_BASE_URL}/monthly-targets`, {
      params: { fy },
      headers: getAuthHeaders(),
    });
    return response.data; // Expected: array of { Month, Target }
  } catch (error) {
    console.error("❌ Failed to fetch monthly targets:", error);
    return [];
  }
};

// =================== FIRESTORE APIs =========================

export const getAreas = async () => {
  try {
    const res = await fetch(`${API_BASE_URL}/areas`, {
      headers: getAuthHeaders(),
    });
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
};

export const getRecruiters = async () => {
  try {
    const res = await fetch(`${API_BASE_URL}/recruiters`, {
      headers: getAuthHeaders(),
    });
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
};

export const addRecruiter = async (name, area) => {
  const res = await fetch(`${API_BASE_URL}/recruiters`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ name, area }),
  });
  return await res.json();
};

export const deleteRecruiter = async (id) => {
  const res = await fetch(`${API_BASE_URL}/recruiters/${id}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  return await res.json();
};

export const updateHeadcount = async (id, headcount) => {
  const res = await fetch(`${API_BASE_URL}/areas/${id}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ headcount }),
  });
  return await res.json();
};
