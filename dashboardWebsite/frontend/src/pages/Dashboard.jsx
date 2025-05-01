import React, { useState, useEffect } from "react";
import Sidebar from "../components/Sidebar";
import RequestButton from "../components/RequestButton";
import {
  testApiCall,
  triggerTestEmail,
  triggerFutureYouReports,
  triggerH2cocoTradeFinance,
  triggerCosmoBillsApprover,
  triggerUpdateRevenueDatabase,
  uploadFile,
  authenticateUser,
} from "../api";

export default function Dashboard() {
  const [selectedScript, setSelectedScript] = useState(null);
  const [selectedClient, setSelectedClient] = useState(null);
  const [selectedDescription, setSelectedDescription] = useState("");
  const [isAuthScreen, setIsAuthScreen] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [globalAlert, setGlobalAlert] = useState(null); // Floating alert on root
  const [alertVisible, setAlertVisible] = useState(false); // Controls fade-out animation
  const [elapsedTime, setElapsedTime] = useState(0);
  const [estimatedTime, setEstimatedTime] = useState(0);
  const [uploadedFile, setUploadedFile] = useState(null);

  // 🔹 Clients and their scripts (dynamic data)
  const clients = [
    {
      clientName: "Test",
      scripts: [
        {
          name: "Test Email Script",
          description: "Sends a test email to verify SMTP settings.",
          action: triggerTestEmail,
          estimatedTime: 3,
          requiresFileUpload: false,
        },
        {
          name: "Test API Script",
          description: "Tests the API connection with a sample request.",
          action: testApiCall,
          estimatedTime: 2,
          requiresFileUpload: false,
        },
      ],
    },
    {
      clientName: "FutureYou",
      scripts: [
        {
          name: "ATB & Overdue Request",
          description:
            "Generates an Aged Trial Balance report that includes both FutureYou Recruitment and Contracting Invoices",
          action: triggerFutureYouReports,
          estimatedTime: 240,
          requiresFileUpload: false,
        },
        {
          name: "Update Revenue Database",
          description:
            "Updates the Invoice Revenue BigQuery Database by updating invoices that have been changed within the last 24 hours.",
          action: triggerUpdateRevenueDatabase,
          estimatedTime: 30,
          requiresFileUpload: false,
        },
      ],
    },
    {
      clientName: "H2coco",
      scripts: [
        {
          name: "Trade Finance Supplier Bill Payment Allocator",
          description:
            "Allocates payment of declared amount on certain date with specific exchange rate (if specified) to the POs. Returns a Excel file with the successfully allocated POs.\n\nExcel file needs the following headers: PO, Date, CurrencyRate, Amount",
          action: triggerH2cocoTradeFinance,
          estimatedTime: 30,
          requiresFileUpload: false,
        },
      ],
    },
    {
      clientName: "Cosmopolitan Corporation",
      scripts: [
        {
          name: "Bills Approver",
          description:
            "Approves all draft bills within the Cosmopolitan Corporation Xero account if they meet the criteria. Updates any incorrect Invoice IDs.",
          action: triggerCosmoBillsApprover,
          estimatedTime: 20,
          requiresFileUpload: false,
        },
      ],
    },
    {
      clientName: "Helpers",
      scripts: [
        {
          name: "Upload File",
          description: "Upload a document to use for other functions",
          action: null,
          estimatedTime: 5,
          requiresFileUpload: true,
        },
      ],
    },
  ];

  // 🔹 Open modal with script request info
  const openModal = (clientName, script) => {
    setSelectedClient(clientName);
    setSelectedScript(script.name);
    setSelectedDescription(script.description);
    setIsAuthScreen(false);
    setStatusMessage("");
    setUsername("");
    setPassword("");
    document.getElementById("scriptModal").showModal();
  };

  // 🔹 Switch to login screen
  const handleExecute = () => {
    setIsAuthScreen(true);
    setStatusMessage("");
  };

  // 🔹 Handle API Execution
  const handleConfirm = async () => {
    setIsLoading(true);
    setStatusMessage("");
    setElapsedTime(0);

    let authResponse = null;
    try {
      authResponse = await authenticateUser(username, password);
    } catch (error) {
      setIsLoading(false);
      setStatusMessage("❌ Error during authentication.");
    }

    const script = clients
      .flatMap((client) => client.scripts)
      .find((script) => script.name === selectedScript);

    if (script?.requiresFileUpload && !uploadedFile) {
      setIsLoading(false);
      setStatusMessage("❌ Please upload an Excel file.");
      return;
    }

    if (!authResponse.success) {
      setIsLoading(false);
      setStatusMessage("❌ Invalid username or password");
      return;
    }

    console.log("Authenticated User:", authResponse.user);

    if (script?.requiresFileUpload) {
      // Call the file upload API first
      const uploadResponse = await uploadFile(uploadedFile);

      if (!uploadResponse.success) {
        setIsLoading(false);
        setStatusMessage(uploadResponse.message);
        return;
      }

      setStatusMessage("✅ File uploaded successfully. Executing script...");
    }

    setIsAuthScreen(false);

    if (script) {
      setEstimatedTime(script.estimatedTime || 10);
      let timeElapsed = 0;
      let apiResponse = null; // Store API response for later

      // Simulate progress update every second
      const interval = setInterval(() => {
        timeElapsed++;
        setElapsedTime(timeElapsed);
        if (timeElapsed >= script.estimatedTime) {
          clearInterval(interval);

          setTimeout(() => {
            setIsLoading(false);
            document.getElementById("scriptModal").close();
            if (apiResponse) {
              showGlobalAlert({
                success: apiResponse.success,
                message: apiResponse.message,
              });
            }
          }, 1000);
        }
      }, 1000);

      if (script.action) {
        try {
          apiResponse = await script.action(authResponse.user);
        } catch (error) {
          apiResponse = {
            success: false,
            message: "❌ API call failed. Please try again.",
          };
        }
      } else {
        apiResponse = {
          success: true,
          message: "✅ File uploaded successfully.",
        };
      }
    }
  };

  // 🔹 Function to Show Global Alert with Auto-Fade
  const showGlobalAlert = (alert) => {
    setGlobalAlert(alert);
    setAlertVisible(true);

    setTimeout(() => {
      setAlertVisible(false);
      setTimeout(() => setGlobalAlert(null), 500);
    }, 5000);
  };

  return (
    <div className="flex w-screen h-screen">
      <Sidebar />

      {/* Floating Alert (Global on Root) */}
      {globalAlert && (
        <div
          className={`fixed top-5 right-5 alert ${globalAlert.success ? "alert-success" : "alert-warning"} shadow-lg transition-opacity duration-500 ${
            alertVisible ? "opacity-100" : "opacity-0"
          }`}
        >
          <span>{globalAlert.message}</span>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 p-6 bg-base-200 pt-10">
        <p className="text-6xl text-primary-content">Trihalo Accountancy</p>
        <p className="text-primary pt-8">Let's make this day efficient!</p>

        {/* Requests Section */}
        <div className="mt-6 mr-10 bg-base-100 text-primary-content shadow-lg rounded-box">
          <div className="card-body overflow-auto">
            <h2 className="card-title text-2xl">Requests</h2>

            {/* 🔹 Dynamic Client Sections */}
            {clients.map((client, index) => (
              <div key={index} className="mt-8">
                <h3 className="text-xl">{client.clientName}</h3>
                <div className="flex gap-4 mt-4">
                  {client.scripts.map((script, idx) => (
                    <RequestButton
                      key={idx}
                      label={script.name}
                      onClick={() => openModal(client.clientName, script)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 🔹 Modal Component */}
      <dialog id="scriptModal" className="modal">
        <div className="modal-box p-10 w-[70%] max-w-2xl">
          <h3 className="text-lg font-bold mb-5">{selectedScript}</h3>
          {isAuthScreen ? (
            // 🔹 Authentication Screen
            <div>
              <p className="mb-2">
                <strong>Client:</strong> {selectedClient}
              </p>
              <p className="mb-4">
                <strong>Description:</strong> {selectedDescription}
              </p>

              {selectedScript &&
                clients.some((client) =>
                  client.scripts.some(
                    (script) =>
                      script.name === selectedScript &&
                      script.requiresFileUpload
                  )
                ) && (
                  <div className="form-control">
                    <input
                      type="file"
                      accept=".xls,.xlsx"
                      className="file-input file-input-bordered"
                      onChange={(e) => setUploadedFile(e.target.files[0])}
                    />
                  </div>
                )}

              <div className="form-control mt-4">
                <input
                  type="text"
                  placeholder="Username"
                  className="input input-bordered"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>

              <div className="form-control mt-4">
                <input
                  type="password"
                  placeholder="Password"
                  className="input input-bordered"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>

              {statusMessage && (
                <p className="text-neutral mt-2">{statusMessage}</p>
              )}

              <div className="modal-action">
                <button
                  className="btn btn-soft mr-5"
                  onClick={() => setIsAuthScreen(false)}
                >
                  Back
                </button>
                <button
                  className="btn btn-accent"
                  onClick={handleConfirm}
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <span className="loading loading-spinner"></span>
                  ) : (
                    "Confirm"
                  )}
                </button>
              </div>
            </div>
          ) : isLoading ? (
            // 🔹 Loading Spinner While API Runs
            <div className="flex flex-col items-center justify-center w-full">
              <span className="loading loading-spinner loading-lg text-primary"></span>
              <p className="text-center mt-4">
                Executing script, please wait...
              </p>

              {/* 🔹 Progress Bar Section */}
              <div className="w-full max-w-xs mt-4">
                <p className="text-center text-sm text-gray-500">
                  Estimated time remaining:{" "}
                  {Math.max(0, estimatedTime - elapsedTime)}s
                </p>
                <progress
                  className="progress progress-primary w-full"
                  value={(elapsedTime / estimatedTime) * 100}
                  max="100"
                ></progress>
              </div>
            </div>
          ) : (
            // 🔹 Initial Script Request Screen
            <div>
              <p className="mb-2">
                <strong>Client:</strong> {selectedClient}
              </p>
              <p className="mb-4">
                <strong>Description:</strong> {selectedDescription}
              </p>
              <div className="modal-action">
                <button
                  className="btn btn-soft mr-5"
                  onClick={() => document.getElementById("scriptModal").close()}
                >
                  Close
                </button>
                <button className="btn btn-accent" onClick={handleExecute}>
                  Execute
                </button>
              </div>
            </div>
          )}
        </div>
      </dialog>
    </div>
  );
}
