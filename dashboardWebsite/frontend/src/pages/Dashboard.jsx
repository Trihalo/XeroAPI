import React, { useState, useEffect } from "react";
import Sidebar from "../components/Sidebar";
import RequestButton from "../components/RequestButton";
import { triggerTestEmail, testApiCall } from "../api";
import credentials from "../login/credentials.json"; // Import stored credentials

export default function Dashboard() {
  const [statusMessage, setStatusMessage] = useState("");
  const [selectedScript, setSelectedScript] = useState(null);
  const [selectedClient, setSelectedClient] = useState(null);
  const [selectedDescription, setSelectedDescription] = useState("");
  const [isAuthScreen, setIsAuthScreen] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [globalAlert, setGlobalAlert] = useState(null); // Floating alert on root
  const [alertVisible, setAlertVisible] = useState(false); // Controls fade-out animation

  // 🔹 Clients and their scripts (dynamic data)
  const clients = [
    {
      clientName: "Test",
      scripts: [
        {
          name: "Test Email Script",
          description: "Sends a test email to verify SMTP settings.",
          action: triggerTestEmail,
        },
        {
          name: "Test API Script",
          description: "Tests the API connection with a sample request.",
          action: testApiCall,
        },
      ],
    },
    {
      clientName: "FutureYou",
      scripts: [
        {
          name: "ATB & Overdue Request",
          description: "Generates an overdue accounts report.",
          action: testApiCall,
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
    setLoginError("");
    setUsername("");
    setPassword("");
    document.getElementById("scriptModal").showModal();
  };

  // 🔹 Switch to login screen
  const handleExecute = () => {
    setIsAuthScreen(true);
    setLoginError("");
  };

  // 🔹 Handle API Execution
  const handleConfirm = async () => {
    setIsLoading(true);
    setLoginError("");

    const user = credentials.users.find(
      (user) => user.username === username && user.password === password
    );

    if (!user) {
      setIsLoading(false);
      setLoginError("❌ Invalid username or password");
      return;
    }

    setStatusMessage(`✅ Executing ${selectedScript}...`);

    const script = clients
      .flatMap((client) => client.scripts)
      .find((script) => script.name === selectedScript);

    if (script && script.action) {
      try {
        const response = await script.action();
        showGlobalAlert({
          success: response.success,
          message: response.message,
        });
      } catch (error) {
        showGlobalAlert({
          success: false,
          message: "❌ API call failed. Please try again.",
        });
      }
    }

    setIsLoading(false);
    document.getElementById("scriptModal").close(); // ✅ Close modal after API completes
  };

  // 🔹 Function to Show Global Alert with Auto-Fade
  const showGlobalAlert = (alert) => {
    setGlobalAlert(alert);
    setAlertVisible(true);

    setTimeout(() => {
      setAlertVisible(false); // Start fade-out
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
          <div className="card-body">
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

              <div className="form-control">
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

              {loginError && <p className="text-red-500 mt-2">{loginError}</p>}

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
            <div className="flex flex-col items-center justify-center">
              <span className="loading loading-spinner loading-lg text-primary"></span>
              <p className="text-center mt-4">
                Executing script, please wait...
              </p>
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
