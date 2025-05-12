import axios from "axios";

const API_BASE_URL =
  import.meta.env.MODE === "development"
    ? "http://localhost:8080"
    : import.meta.env.VITE_API_URL;

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
      errorMessage = `❌ Server error: ${error.response.status} - ${error.response.statusText}`;
    } else if (error.request) {
      errorMessage =
        "❌ No response from the backend. Check if the server is running.";
    }

    return { success: false, message: errorMessage };
  }
};

export const uploadForecastToBQ = async (rows) => {
  try {
    const uploadUser = localStorage.getItem("name") || "Unknown User";

    const enrichedRows = rows.map((row) => ({
      ...row,
      uploadUser,
    }));

    const response = await axios.post(`${API_BASE_URL}/forecasts`, {
      forecasts: enrichedRows,
    });

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
      }
    );

    const existing = res.data;
    console.log("Fetched existing forecasts:", existing);

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
    });

    return res.data; // array of { name, week, total_revenue }
  } catch (error) {
    console.error("❌ Failed to fetch forecast summary:", error);
    return [];
  }
};
