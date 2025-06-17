import React, { useEffect } from "react";
import ReactDOM from "react-dom/client";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  useNavigate,
} from "react-router-dom";

import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Revenue.jsx";
import Admin from "./pages/Admin.jsx";
import Upload from "./pages/Upload.jsx";
import ForecastMain from "./pages/ForecastMain.jsx";
import Password from "./pages/Password.jsx";
import PrivateRoute from "./components/PrivateRoute.jsx";
import Legends from "./pages/Legends.jsx";

import { fetchAndStoreInvoiceData } from "./utils/getInvoiceInfo.js";

import "./index.css";

function AppRoutes() {
  const navigate = useNavigate();

  // Redirect to login if no token
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      navigate("/");
    }
  }, [navigate]);

  // Fetch invoice data ONCE per session if logged in
  useEffect(() => {
    const token = localStorage.getItem("token");
    const hasFetchedInvoiceData = sessionStorage.getItem("invoiceDataFetched");

    if (token && !hasFetchedInvoiceData) {
      fetchAndStoreInvoiceData()
        .then(() => {
          sessionStorage.setItem("invoiceDataFetched", "true");
          console.log("✅ Invoice data fetched and flag set.");
        })
        .catch((err) => {
          console.error("❌ Error fetching invoice data:", err);
        });
    }
  }, []);

  return (
    <Routes>
      {/* Public route */}
      <Route path="/" element={<Login />} />
      <Route path="/password" element={<Password />} />

      {/* Protected routes */}
      <Route element={<PrivateRoute />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/forecasts/:recruiterName" element={<Upload />} />
        <Route path="/forecasts" element={<ForecastMain />} />
        <Route path="/legends" element={<Legends />} />
        <Route path="/admin" element={<Admin />} />
      </Route>
    </Routes>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <Router>
    <AppRoutes />
  </Router>
);
