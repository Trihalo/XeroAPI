import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { changePassword } from "../api";

function ChangePassword() {
  const [username, setUsername] = useState("");
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [message, setMessage] = useState("");
  const navigate = useNavigate();

  const handleChangePassword = async () => {
    setMessage("");

    if (!oldPassword || !newPassword || !confirmNewPassword) {
      setMessage("Please fill in all fields.");
      return;
    }

    if (newPassword !== confirmNewPassword) {
      setMessage("New passwords do not match.");
      return;
    }

    try {
      const response = await changePassword(username, oldPassword, newPassword);

      if (response.success) {
        setMessage("✅ Password changed successfully.");
        setTimeout(() => navigate("/"), 2000);
      } else {
        setMessage(response.error || "❌ Failed to change password.");
      }
    } catch (err) {
      setMessage("❌ Server error. Please try again.");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-primary text-base-content">
      <div className="bg-base-100 text-base-content rounded-2xl shadow-md px-6 py-8 w-full max-w-sm mx-4 sm:mx-auto text-center">
        <img src="/fy.png" alt="FutureYou" className="mx-auto mb-2" />
        <h2 className="text-xl font-small mb-6">Forecast Revenue Dashboard</h2>

        <div className="text-right">
          <button
            onClick={() => navigate(-1)}
            className="text-sm text-gray-400 transition"
          >
            ← Go Back
          </button>
        </div>
        <div className="text-left mb-4">
          <label className="block text-sm font-semibold mb-1">Username</label>
          <input
            placeholder="Enter your username"
            className="input input-bordered w-full"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div className="text-left mb-4">
          <label className="block text-sm font-semibold mb-1">
            Old Password
          </label>
          <input
            type="password"
            placeholder="Enter your old password"
            className="input input-bordered w-full"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
          />
        </div>

        <div className="text-left mb-4">
          <label className="block text-sm font-semibold mb-1">
            New Password
          </label>
          <input
            type="password"
            placeholder="Enter your new password"
            className="input input-bordered w-full"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
        </div>

        <div className="text-left mb-4">
          <label className="block text-sm font-semibold mb-1">
            Confirm New Password
          </label>
          <input
            type="password"
            placeholder="Confirm your new password"
            className="input input-bordered w-full"
            value={confirmNewPassword}
            onChange={(e) => setConfirmNewPassword(e.target.value)}
          />
        </div>

        <button
          onClick={handleChangePassword}
          className="btn btn-primary w-full py-2 mt-2"
        >
          Change Password
        </button>

        {message && (
          <div className="text-sm mt-4 text-secondary">{message}</div>
        )}
      </div>

      <div className="absolute bottom-4 right-4 text-xs text-base-content">
        For any issues, please contact{" "}
        <a href="mailto:leoshi@future-you.com.au" className="underline">
          leoshi@future-you.com.au
        </a>
      </div>
    </div>
  );
}

export default ChangePassword;
