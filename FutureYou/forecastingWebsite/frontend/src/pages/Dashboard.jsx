import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/Sidebar.jsx";

function Dashboard() {
  const [activeTab, setActiveTab] = useState("consultant");
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    navigate("/", { replace: true });
  };

  return (
    <div className="min-h-screen flex bg-gray-200 text-base-content">
      {/* Sidebar on the left */}
      <Sidebar onLogout={handleLogout} />

      {/* Main content area */}
      <div className="flex-1 p-8">
        <div className="max-w mx-auto bg-white rounded-xl shadow p-6 relative">
          {/* Header */}
          <div className="flex justify-between items-center mb-4">
            <h1 className="text-xl font-semibold">Hello, Corin</h1>
          </div>

          <div className="mb-4">
            <h2 className="text-lg font-bold">Consultant Breakdown</h2>
            <label className="label mt-2">Month</label>
            <input
              type="text"
              className="input input-bordered w-32"
              value="April"
              readOnly
            />
          </div>

          <div className="tabs mb-4">
            <a
              className={`tab tab-bordered ${
                activeTab === "consultant" ? "tab-active" : ""
              }`}
              onClick={() => setActiveTab("consultant")}
            >
              Consultant Breakdown
            </a>
            <a
              className={`tab tab-bordered ${
                activeTab === "area" ? "tab-active" : ""
              }`}
              onClick={() => setActiveTab("area")}
            >
              Area Breakdown
            </a>
          </div>

          <div className="overflow-x-auto">
            <table className="table table-sm">
              <thead>
                <tr>
                  <th></th>
                  <th>Week 1</th>
                  <th>Week 2</th>
                  <th>Week 3</th>
                  <th>Week 4</th>
                  <th>Week 5</th>
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                <tr className="text-error font-bold">
                  <td>Corin Roberts</td>
                </tr>
                <tr>
                  <td className="font-medium">Forecasted Revenue</td>
                  <td>0</td>
                  <td>45,024</td>
                  <td>0</td>
                  <td>10,000</td>
                  <td></td>
                  <td className="font-bold">55,024</td>
                </tr>
                <tr className="text-xs text-neutral">
                  <td colSpan={7}>ACTUAL</td>
                </tr>
                <tr>
                  <td>Perm</td>
                  <td>0</td>
                  <td>42,385</td>
                  <td>0</td>
                  <td>43,773</td>
                  <td></td>
                  <td className="font-bold">88,797</td>
                </tr>
                <tr>
                  <td>Temp</td>
                  <td>3,318</td>
                  <td>4,415</td>
                  <td>4,676</td>
                  <td>3,298</td>
                  <td></td>
                  <td className="font-bold">15,706</td>
                </tr>
                <tr className="text-xs text-neutral">
                  <td colSpan={7}>TOTAL REVENUE</td>
                </tr>
                <tr>
                  <td className="font-semibold">Total</td>
                  <td>3,318</td>
                  <td>49,438</td>
                  <td>4,676</td>
                  <td>47,071</td>
                  <td></td>
                  <td className="font-bold">104,503</td>
                </tr>
                <tr className="text-xs text-neutral">
                  <td colSpan={7}>VARIANCE</td>
                </tr>
                <tr>
                  <td className="font-semibold">Variance</td>
                  <td>3,318</td>
                  <td>3,318</td>
                  <td>4,676</td>
                  <td>3,318</td>
                  <td></td>
                  <td className="font-bold text-error">3,318</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="text-xs text-gray-500 mt-6">
            For any issues, please contact{" "}
            <a href="mailto:Leo@trihalo.com.au" className="underline">
              Leo@trihalo.com.au
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
