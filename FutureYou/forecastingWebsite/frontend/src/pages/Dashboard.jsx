import { useState } from "react";
import { useNavigate } from "react-router-dom";
import TopNavbar from "../components/TopNavbar.jsx";

function Dashboard() {
  const [activeTab, setActiveTab] = useState("consultant");
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-200 text-base-content flex flex-col">
      {/* Top Navbar */}
      <TopNavbar userName={localStorage.getItem("name")} />
      {/* Main content area */}
      <div className="flex-1 p-8">
        <div className="max-w mx-auto bg-white rounded-xl shadow p-6 relative">
          hi, content yet to be added
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
