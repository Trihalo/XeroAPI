import React, { useState, useEffect } from "react";
import Sidebar from "../components/Sidebar";

const WORKFLOW_DISPLAY_NAMES = {
  "sendEmail.yml": "Send Email Test",
  "futureYouReports.yml": "FutureYou Reports",
  "tradeFinance.yml": "Trade Finance Workflow",
  "cosmoBillsApprover.yml": "Cosmo Bills Approver",
  test: "Test Workflow",
};

export default function History() {
  const [history, setHistory] = useState([]);

  useEffect(() => {
    const API_BASE_URL = import.meta.env.VITE_API_URL;

    fetch(`${API_BASE_URL}/history`)
      .then((res) => res.json())
      .then((data) => setHistory(data))
      .catch((err) => console.error("Failed to fetch history:", err));
  }, []);

  return (
    <div className="flex w-screen h-screen">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <div className="flex-1 p-6 bg-base-200 pt-10 overflow-auto">
        <p className="text-6xl text-primary-content">Trihalo Accountancy</p>
        <p className="text-primary pt-8">Let's make this day efficient!</p>

        {/* Card Container */}
        <div className="mt-6 mr-10 bg-base-100 text-primary-content shadow-lg rounded-box">
          <div className="card-body max-h-[500px] overflow-auto">
            <h2 className="text-2xl font-bold mb-4">Workflow History</h2>

            <div className="overflow-x-auto">
              <table className="table table-zebra table-sm w-full">
                <thead>
                  <tr>
                    <th className="w-80">Workflow</th>
                    <th>Called At</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((item, index) => {
                    const isObjectName = typeof item.name === "object";
                    return (
                      <tr key={index}>
                        <td className="w-80">
                          {WORKFLOW_DISPLAY_NAMES[item.workflow] ||
                            item.workflow}
                        </td>
                        <td>{item.called_at}</td>
                        <td>{isObjectName ? item.name.name : item.name}</td>
                        <td>{isObjectName ? item.name.email : "-"}</td>
                        <td>
                          <div
                            className={`badge ${
                              item.success === 200 ||
                              (typeof item.success === "string" &&
                                item.success.toLowerCase() === "success")
                                ? "badge-success"
                                : "badge-error"
                            }`}
                          >
                            {item.success}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
