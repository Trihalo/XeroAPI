import axios from "axios";

const API_BASE_URL =
  import.meta.env.MODE === "development"
    ? "http://localhost:8080"
    : import.meta.env.VITE_API_URL;

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
      const backendData = error.response.data;
      console.error("Backend Error:", backendData);

      if (backendData.error) {
        // Use error message from backend JSON
        errorMessage = `❌ ${backendData.error}`;
      } else {
        errorMessage = `❌ Server error: ${error.response.status} - ${error.response.statusText}`;
      }
    } else if (error.request) {
      // No response received
      errorMessage =
        "❌ No response from the backend. Check if the server is running.";
    }

    return { success: false, message: errorMessage };
  }
};

// 🔹 Specific API calls mapped to workflow keys
export const triggerTestEmail = (userData) =>
  triggerWorkflow("test-email", userData);
export const triggerFutureYouReports = (userData) =>
  triggerWorkflow("futureyou-reports", userData);
export const triggerUpdateFYATBDatabase = (userData) =>
  triggerWorkflow("futureyou-atb-database", userData);
export const triggerH2cocoSupplierPayment = (userData) =>
  triggerWorkflow("h2coco-supplier-payment", userData);
export const triggerH2cocoInvoiceApprover = (userData) =>
  triggerWorkflow("h2coco-invoice-approver", userData);
export const triggerCosmoBillsApprover = (userData) =>
  triggerWorkflow("cosmo-bills-approver", userData);
export const triggerUpdateRevenueDatabase = (userData) =>
  triggerWorkflow("futureyou-revenue-database", userData);

export const testApiCall = async (userData) => {
  try {
    await new Promise((res) => setTimeout(res, 5000));
    if (Math.random() > 1) {
      throw new Error("❌ Simulated API failure.");
    }

    const response = await axios.post(`${API_BASE_URL}/test-api`, {
      ...userData,
    });

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
