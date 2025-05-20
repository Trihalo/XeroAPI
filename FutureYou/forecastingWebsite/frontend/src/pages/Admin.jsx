// ✅ Admin.jsx (Updated Layout using Firebase + Refetchable State)
import { useState, useEffect } from "react";
import TopNavbar from "../components/TopNavbar.jsx";
import {
  submitMonthlyTarget,
  fetchMonthlyTargets,
  addRecruiter,
  deleteRecruiter,
  updateHeadcount,
} from "../api";
import { useRecruiterData } from "../hooks/useRecruiterData";

const ConfirmDialog = ({ show, onConfirm, onCancel, message }) => {
  if (!show) return null;
  return (
    <div className="fixed inset-0 bg-[rgba(0,0,0,0.3)] z-50 flex items-center justify-center">
      <div className="bg-white p-6 rounded-lg shadow-lg space-y-4 w-[320px]">
        <p className="text-md text-gray-800">{message}</p>
        <div className="flex justify-end space-x-4">
          <button className="btn btn-outline btn-sm" onClick={onCancel}>
            Cancel
          </button>
          <button className="btn btn-error btn-sm" onClick={onConfirm}>
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
};

function Admin() {
  const [activeTab, setActiveTab] = useState("recruiterManagement");
  const [fy, setFy] = useState("FY25");
  const [month, setMonth] = useState("Jan");
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [alertMessage, setAlertMessage] = useState("");
  const [showAlert, setShowAlert] = useState(false);
  const [summaryByMonth, setSummaryByMonth] = useState({});
  const [newRecruiterName, setNewRecruiterName] = useState("");
  const [newRecruiterArea, setNewRecruiterArea] = useState("");
  const [areaEdits, setAreaEdits] = useState({});
  const [showConfirm, setShowConfirm] = useState(false);
  const [confirmMessage, setConfirmMessage] = useState("");
  const [onConfirmAction, setOnConfirmAction] = useState(() => () => {});
  const [refreshKey, setRefreshKey] = useState(0);

  const { recruiters, areas } = useRecruiterData(refreshKey);

  console.log(areas);

  const askConfirm = (message, action) => {
    setConfirmMessage(message);
    setOnConfirmAction(() => action);
    setShowConfirm(true);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    const result = await submitMonthlyTarget({ fy, month, amount });

    if (result.success) {
      setAlertMessage("✅ Monthly target submitted!");
      await fetchAndSetTargetSummary(fy);
    } else {
      setAlertMessage(`❌ ${result.message}`);
    }

    setShowAlert(true);
    setSubmitting(false);
    setTimeout(() => setShowAlert(false), 4000);
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
  }, [fy]);

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
      <TopNavbar userName={localStorage.getItem("name")} />

      <div className="flex-1 p-8">
        <div className="max-w mx-auto bg-white rounded-xl shadow p-12 relative mb-15">
          <p className="text-lg font-semibold mb-4">Admin Dashboard</p>
          <div className="flex flex-wrap justify-start gap-4 mb-8">
            {["recruiterManagement", "monthlyTotal"].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded-lg shadow transition min-w-[250px] ${
                  activeTab === tab
                    ? "bg-secondary text-white font-semibold"
                    : "bg-gray-200 text-gray-800 font-medium hover:bg-gray-300"
                }`}
              >
                {tab === "recruiterManagement"
                  ? "Recruiter Management"
                  : "Input Monthly Target"}
              </button>
            ))}
          </div>

          {activeTab === "recruiterManagement" && (
            <div className="space-y-8">
              <h3 className="text-lg font-semibold text-primary">
                👤 Recruiter & Area Management
              </h3>

              <div>
                <h4 className="font-medium mb-2">Recruiters</h4>
                <div className="flex gap-2 mb-10">
                  <input
                    className="input input-bordered"
                    placeholder="Recruiter Name"
                    value={newRecruiterName}
                    onChange={(e) => setNewRecruiterName(e.target.value)}
                  />
                  <select
                    className="select select-bordered"
                    value={newRecruiterArea}
                    onChange={(e) => setNewRecruiterArea(e.target.value)}
                  >
                    <option value="" disabled>
                      Select an area
                    </option>
                    {areas.map((area) => (
                      <option key={area.id} value={area.name}>
                        {area.name}
                      </option>
                    ))}
                  </select>
                  <button
                    className="btn btn-secondary"
                    onClick={() =>
                      askConfirm(
                        `Add ${newRecruiterName} to ${newRecruiterArea}?`,
                        async () => {
                          await addRecruiter(
                            newRecruiterName,
                            newRecruiterArea
                          );
                          setNewRecruiterName("");
                          setNewRecruiterArea("");
                          setAlertMessage("✅ Recruiter added");
                          setShowAlert(true);
                          setRefreshKey((k) => k + 1);
                        }
                      )
                    }
                  >
                    Add
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                  {recruiters.map((r) => (
                    <div
                      key={r.id}
                      className="bg-gray-100 p-3 rounded flex items-center justify-between text-sm shadow-sm"
                    >
                      <span className="text-gray-800 font-medium leading-snug">
                        {r.name}{" "}
                        <span className="text-gray-500 text-xs">
                          ({r.area})
                        </span>
                      </span>
                      <button
                        onClick={() =>
                          askConfirm(`Delete ${r.name}?`, async () => {
                            await deleteRecruiter(r.id);
                            setAlertMessage("✅ Recruiter deleted");
                            setShowAlert(true);
                            setRefreshKey((k) => k + 1);
                          })
                        }
                        className="text-gray-500 hover:text-secondary"
                      >
                        🗑
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="font-medium mt-8 mb-2">Area Headcounts</h4>
                <ul className="space-y-2">
                  {areas.map((a) => (
                    <li key={a.id} className="flex items-center gap-4">
                      <span className="w-48">{a.name}</span>
                      <input
                        type="number"
                        className="input input-bordered w-24"
                        value={areaEdits[a.id] ?? a.headcount}
                        onChange={(e) =>
                          setAreaEdits((prev) => ({
                            ...prev,
                            [a.id]: e.target.value,
                          }))
                        }
                      />
                      <button
                        className="btn btn-sm"
                        onClick={() =>
                          askConfirm(
                            `Save headcount for "${a.name}"?`,
                            async () => {
                              await updateHeadcount(
                                a.id,
                                parseFloat(areaEdits[a.id])
                              );
                              setAlertMessage("✅ Headcount updated!");
                              setShowAlert(true);
                              setRefreshKey((k) => k + 1);
                            }
                          )
                        }
                      >
                        💾 Save
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
              <ConfirmDialog
                show={showConfirm}
                onCancel={() => setShowConfirm(false)}
                onConfirm={() => {
                  setShowConfirm(false);
                  onConfirmAction();
                }}
                message={confirmMessage}
              />
            </div>
          )}

          {activeTab === "monthlyTotal" && (
            <div className="text-gray-800 text-sm mt-15 mb-15">
              <h2 className="text-lg font-semibold text-primary mb-5">
                📋 Input Monthly Target
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-6 max-w-xl w-full">
                <div>
                  <label className="block mb-1">Financial Year</label>
                  <select
                    className="select select-bordered w-full"
                    value={fy}
                    onChange={(e) => setFy(e.target.value)}
                  >
                    <option>FY25</option>
                    <option>FY26</option>
                  </select>
                </div>
                <div>
                  <label className="block mb-1">Month</label>
                  <select
                    className="select select-bordered w-full"
                    value={month}
                    onChange={(e) => setMonth(e.target.value)}
                  >
                    {months.map((m) => (
                      <option key={m}>{m}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block mb-1">Monthly Target ($)</label>
                  <input
                    type="number"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className="input input-bordered w-full"
                  />
                </div>
              </div>
              <button
                className="btn btn-secondary mt-4"
                onClick={handleSubmit}
                disabled={submitting}
              >
                Submit Target
              </button>
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
              <div className="mt-8">
                <h2 className="text-lg font-semibold text-primary mb-4">
                  📊 View Submitted Targets
                </h2>
                <div className="overflow-hidden rounded-xl border border-gray-300 max-w-sm">
                  <table className="w-full text-sm text-gray-800">
                    <thead>
                      <tr>
                        <th className="bg-gray-200 px-4 py-3 text-left text-sm font-semibold w-1/2">
                          Month
                        </th>
                        <th className="bg-gray-200 px-4 py-3 text-left text-sm font-semibold w-1/2">
                          Target
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {months.map((m, idx) => (
                        <tr
                          key={m}
                          className={idx % 2 === 0 ? "bg-white" : "bg-gray-50"}
                        >
                          <td className="px-4 py-3 text-left font-medium">
                            {m}
                          </td>
                          <td className="px-4 py-3 text-left">
                            {summaryByMonth[m]
                              ? `$${(summaryByMonth[m] / 1000).toFixed(0)}K`
                              : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
      <div className="text-gray-400 p-5 text-right">
        For any issues, please contact Leo@trihalo.com.au
      </div>
    </div>
  );
}

export default Admin;
