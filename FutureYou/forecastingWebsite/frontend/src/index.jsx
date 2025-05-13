import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter as Router, Route, Routes } from "react-router-dom";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Revenue.jsx";
import Admin from "./pages/Admin.jsx";
import Upload from "./pages/Upload.jsx";
import ForecastMain from "./pages/ForecastMain.jsx";
import PrivateRoute from "./components/PrivateRoute.jsx";
import "./index.css";

function App() {
  return (
    <Router>
      <Routes>
        {/* Public route */}
        <Route path="/" element={<Login />} />

        {/* Protected routes */}
        <Route element={<PrivateRoute />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/forecasts/:recruiterName" element={<Upload />} />
          <Route path="/forecasts" element={<ForecastMain />} />
          <Route path="/admin" element={<Admin />} />
          {/* Add more protected routes here */}
        </Route>
      </Routes>
    </Router>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
