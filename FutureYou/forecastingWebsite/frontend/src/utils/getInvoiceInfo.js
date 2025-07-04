import axios from "axios";
import { getCurrentMonthInfo } from "./getCurrentMonthInfo";
import calendar from "../data/calendar";

const API_BASE_URL =
  import.meta.env.MODE === "development"
    ? "http://localhost:8080"
    : import.meta.env.VITE_API_URL;

export const fetchAndStoreInvoiceData = async () => {
  const { currentMonth, currentFY, previousMonth, previousMonthFY } =
    getCurrentMonthInfo(calendar);
  const token = localStorage.getItem("token");

  try {
    // Fire both API calls in parallel
    const [currentRes, previousRes] = await Promise.all([
      axios.get(`${API_BASE_URL}/invoices`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        params: {
          fy: currentFY,
          month: currentMonth,
        },
      }),
      axios.get(`${API_BASE_URL}/invoices`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        params: {
          fy: previousMonthFY,
          month: previousMonth,
        },
      }),
    ]);

    const currentData = currentRes.data;
    const previousData = previousRes.data;
    sessionStorage.setItem("invoiceData", JSON.stringify(currentData));
    sessionStorage.setItem("prevInvoiceData", JSON.stringify(previousData));
    console.log(
      "✅ Current month invoice data stored in sessionStorage (invoiceData)"
    );
    console.log(
      "✅ Previous month invoice data stored in sessionStorage (prevInvoiceData)"
    );

    return {
      currentData,
      previousData,
    };
  } catch (error) {
    console.error("❌ Failed to fetch invoice data:", error);
    sessionStorage.setItem("invoiceData", "[]");
    sessionStorage.setItem("prevInvoiceData", "[]");
    return {
      currentData: [],
      previousData: [],
    };
  }
};

export const getStoredInvoiceData = () => {
  try {
    return JSON.parse(sessionStorage.getItem("invoiceData") || "[]");
  } catch {
    return [];
  }
};

export const getStoredPrevInvoiceData = () => {
  try {
    return JSON.parse(sessionStorage.getItem("prevInvoiceData") || "[]");
  } catch {
    return [];
  }
};
