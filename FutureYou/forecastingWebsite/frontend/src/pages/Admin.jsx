import { useState, useEffect } from "react";
import TopNavbar from "../components/TopNavbar.jsx";
import { recruiterMapping } from "../data/recruiterMapping.js";
import RecruiterStatus from "../components/RecruiterStatus.jsx";
import { submitMonthlyTarget, fetchMonthlyTargets } from "../api";
import { useSubmittedRecruiters } from "../hooks/useSubmittedRecruiters";

function Admin() {
  const [activeTab, setActiveTab] = useState("submitStatus");
  const [fy, setFy] = useState("FY25");
  const [month, setMonth] = useState("Jan");
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [alertMessage, setAlertMessage] = useState("");
  const [showAlert, setShowAlert] = useState(false);
  const [summaryByMonth, setSummaryByMonth] = useState({});

  const submittedRecruiters = useSubmittedRecruiters();

  const tabLabels = {
    submitStatus: "Recruiter Forecast Status",
    monthlyTotal: "Input Monthly Target",
  };

  const fetchAndSetTargetSummary = async (selectedFY) => {
    const data = await fetchMonthlyTargets(selectedFY);
    const byMonth = {};
    data.forEach((row) => {
      byMonth[row.Month] = row.Target;
    });
    setSummaryByMonth(byMonth);
  };

  useEffect(() => {
    fetchAndSetTargetSummary(fy);
  }, []);

  const handleSubmit = async () => {
    setSubmitting(true);
    const result = await submitMonthlyTarget({ fy, month, amount });

    if (result.success) {
      setAlertMessage("✅ Monthly target submitted!");
      await fetchAndSetSummary(fy);
    } else {
      setAlertMessage(`❌ ${result.message}`);
    }

    setShowAlert(true);
    setSubmitting(false);

    // Auto-close after 4 seconds (optional)
    setTimeout(() => {
      setShowAlert(false);
    }, 4000);
  };

  const months = [
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
  ];

  return (
    <div className="min-h-screen bg-gray-200 text-base-content flex flex-col">
      {/* Top Navbar */}
      <TopNavbar userName={localStorage.getItem("name")} />

      {/* Main content area */}
      <div className="flex-1 p-8">
        <div className="max-w mx-auto bg-white rounded-xl shadow p-12 relative">
          <p className="text-lg font-semibold mb-4">Admin Dashboard</p>

          {/* Tabs */}
          <div className="flex space-x-4 mb-6">
            {["submitStatus", "monthlyTotal"].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-1.5 rounded-lg shadow ${
                  activeTab === tab
                    ? "bg-red-400 text-white font-semibold"
                    : "bg-gray-300 text-gray-800 font-normal"
                }`}
              >
                {tabLabels[tab] || ""}
              </button>
            ))}
          </div>

          {/* Conditional tab content */}
          {activeTab === "submitStatus" && (
            <div className="space-y-6 mt-15">
              <h3 className="text-lg font-semibold text-primary mb-5">
                Recruiter Forecast Submission Status
              </h3>
              {Object.entries(recruiterMapping).map(([category, names]) => (
                <div key={category}>
                  <h3 className="text-md font-semibold text-primary mb-5">
                    {category}
                  </h3>
                  <div className="w-full flex">
                    <div className="w-[60%]">
                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 text-gray-800">
                        {names.map((name) => (
                          <RecruiterStatus
                            key={name}
                            name={name}
                            isSubmitted={submittedRecruiters.has(name)}
                          />
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
          {activeTab === "monthlyTotal" && (
            <div className="text-gray-800 text-sm mt-15">
              <div className="bg-white max-w-2xl space-y-6">
                <h2 className="text-lg font-semibold text-primary mb-5">
                  📋 Input Monthly Target
                </h2>

                {/* Year + Month Dropdowns */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                  {/* Financial Year Dropdown */}
                  <div>
                    <label className="block mb-1 text-sm font-medium text-gray-700">
                      Financial Year
                    </label>
                    <select
                      className="select select-bordered w-full"
                      value={fy}
                      onChange={(e) => setFy(e.target.value)}
                    >
                      <option>FY25</option>
                      <option>FY26</option>
                    </select>
                  </div>

                  {/* Month Dropdown */}
                  <div>
                    <label className="block mb-1 text-sm font-medium text-gray-700">
                      Month
                    </label>
                    <select
                      className="select select-bordered w-full"
                      value={month}
                      onChange={(e) => setMonth(e.target.value)}
                    >
                      {months.map((month) => (
                        <option key={month}>{month}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Dollar Input */}
                <div>
                  <label className="block mb-1 text-sm font-medium text-gray-700">
                    Monthly Target ($)
                  </label>
                  <input
                    type="number"
                    value={amount}
                    onChange={(e) => {
                      setAmount(e.target.value);
                    }}
                    placeholder="Enter amount"
                    className="input input-bordered w-full pl-8"
                  />
                </div>
                <button
                  className="btn btn-secondary mt-4 flex items-center gap-2"
                  onClick={handleSubmit}
                  disabled={submitting}
                >
                  {submitting && (
                    <span className="loading loading-spinner loading-sm text-white"></span>
                  )}
                  Submit Target
                </button>
              </div>
              {alertMessage && showAlert && (
                <div className="fixed bottom-10 right-10 text-center z-50">
                  <div className="alert shadow-lg w-fit rounded-full bg-emerald-300 border-0">
                    <div>
                      <span className="badge uppercase rounded-full bg-emerald-400 mr-4 p-4 border-0">
                        {alertMessage.startsWith("✅") ? "Success" : "Error"}
                      </span>
                      <span>{alertMessage}</span>
                    </div>
                    <button
                      className="btn btn-sm btn-ghost"
                      onClick={() => setShowAlert(false)}
                    >
                      ✕
                    </button>
                  </div>
                </div>
              )}
              <div className="space-y-4 mt-15">
                <h2 className="text-lg font-semibold text-primary">
                  📊 View Submitted Targets
                </h2>

                <select
                  className="select select-bordered w-fit"
                  value={fy}
                  onChange={(e) => {
                    setFy(e.target.value);
                    fetchAndSetSummary(e.target.value);
                  }}
                >
                  <option>FY25</option>
                  <option>FY26</option>
                </select>

                <div className="overflow-x-auto">
                  <table className="table table-zebra mt-4 w-full">
                    <thead>
                      <tr>
                        {months.map((m) => (
                          <th key={m}>{m}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        {months.map((m) => (
                          <td key={m}>
                            {summaryByMonth[m]
                              ? `$${(summaryByMonth[m] / 1000).toFixed(0)}K`
                              : "-"}
                          </td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Admin;
