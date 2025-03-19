import axios from "axios";

const API_BASE_URL = "http://localhost:8080";

export const triggerTestEmail = async () => {
  try {
    const response = await axios.post(`${API_BASE_URL}/test-email`);

    if (response.data.success) {
      return {
        success: true,
        message: "✅ Test Email sent successfully!",
      };
    } else {
      console.error(response.data.error);
      return { success: false, message: "❌ Failed to trigger action." };
    }
  } catch (error) {
    console.error("Error triggering GitHub Action:", error);
    return { success: false, message: "❌ Error contacting the backend." };
  }
};

export const testApiCall = async () => {
  return new Promise(async (resolve, reject) => {
    try {
      // Simulating API delay (5 seconds)
      await new Promise((res) => setTimeout(res, 5000));

      // Randomly simulate success/failure (for testing)
      const isSuccess = Math.random() > 0.5;
      console.log("isSuccess:", isSuccess);

      // Making API request
      let response = null;
      if (isSuccess) {
        response = await axios.get(`${API_BASE_URL}/test-api`);
      }

      if (isSuccess) {
        resolve(response.data.message || "✅ API call was successful!");
      } else {
        reject("❌ Simulated API failure!");
      }
    } catch (error) {
      console.error("Error calling test API:", error);
      reject("❌ Test API failed due to network error.");
    }
  });
};
