import axios from "axios";

const API_BASE_URL = "http://localhost:8080"; // Update if using a different host

// 🔹 Reusable function to trigger any workflow
export const triggerWorkflow = async (workflowKey, authUser) => {
  try {
    const response = await axios.post(
      `${API_BASE_URL}/trigger/${workflowKey}`,
      { user: authUser }
    );

    if (response.data.success) {
      return {
        success: true,
        message: response.data.message,
      };
    } else {
      console.error("API Error:", response.data.error);
      return { success: false, message: `❌ ${response.data.error}` };
    }
  } catch (error) {
    console.error("Request failed:", error);

    let errorMessage = "❌ Error contacting the backend.";
    if (error.response) {
      // Backend responded with an error status code
      console.error("Backend Error:", error.response.data);
      errorMessage = `❌ Server error: ${error.response.status} - ${error.response.statusText}`;
    } else if (error.request) {
      // No response received
      errorMessage =
        "❌ No response from the backend. Check if the server is running.";
    }

    return { success: false, message: errorMessage };
  }
};

// 🔹 Specific API calls mapped to workflow keys
export const triggerTestEmail = () => triggerWorkflow("test-email");
export const triggerFutureYouReports = () =>
  triggerWorkflow("futureyou-reports");
export const triggerH2cocoTradeFinance = () =>
  triggerWorkflow("h2coco-trade-finance");
export const triggerCosmoBillsApprover = () =>
  triggerWorkflow("cosmo-bills-approver");

export const testApiCall = async () => {
  try {
    await new Promise((res) => setTimeout(res, 5000));
    if (Math.random() > 0.5) {
      throw new Error("❌ Simulated API failure.");
    }

    const response = await axios.get(`${API_BASE_URL}/test-api`);

    return response.data;
  } catch (error) {
    console.error("Error calling test API:", error);
    throw new Error(
      error.message || "❌ Test API failed due to network error."
    );
  }
};

export const uploadFile = async (file) => {
  if (!file) {
    return { success: false, message: "❌ No file selected." };
  }

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await axios.post(`${API_BASE_URL}/upload-file`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });

    return response.data; // Return success or failure message
  } catch (error) {
    console.error("Upload failed:", error.response?.data || error.message);
    return { success: false, message: "❌ Upload failed." };
  }
};

export const authenticateUser = async (username, password) => {
  try {
    const response = await fetch(`${API_BASE_URL}/authenticate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      throw new Error("Authentication failed");
    }

    const data = await response.json();
    return {
      success: data.success,
      message: data.message,
      user: data.user || null,
    };
  } catch (error) {
    return { success: false, message: "Authentication request failed" };
  }
};
