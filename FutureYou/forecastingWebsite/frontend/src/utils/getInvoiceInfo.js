import axios from "axios";
import { getCurrentMonthInfo } from "./getCurrentMonthInfo";
import calendar from "../data/calendar";

const API_BASE_URL =
  import.meta.env.MODE === "development"
    ? "http://localhost:8080"
    : import.meta.env.VITE_API_URL;

export const fetchAndStoreInvoiceData = async () => {
  const { currentMonth, currentFY } = getCurrentMonthInfo(calendar);

  try {
    const res = await axios.get(`${API_BASE_URL}/invoices`, {
      params: {
        fy: currentFY,
        month: currentMonth,
      },
    });

    const data = res.data;
    sessionStorage.setItem("invoiceData", JSON.stringify(data));
    console.log("✅ Invoice data stored in sessionStorage");
    return data;
  } catch (error) {
    console.error("❌ Failed to fetch invoice data:", error);
    sessionStorage.setItem("invoiceData", "[]");
    return [];
  }
};

export const getStoredInvoiceData = () => {
  try {
    return JSON.parse(sessionStorage.getItem("invoiceData") || "[]");
  } catch {
    return [];
  }
};
