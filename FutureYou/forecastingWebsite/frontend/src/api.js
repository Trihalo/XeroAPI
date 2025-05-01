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

export const uploadForecastToBQ = async (rows, username, password) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/forecasts`, {
      username,
      password,
      forecasts: rows,
    });

    if (response.data.success) {
      alert("✅ Forecast uploaded to BigQuery!");
      return { success: true };
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
