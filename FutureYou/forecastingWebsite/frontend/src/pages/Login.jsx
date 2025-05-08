import { useState } from "react";
import { login } from "../api";
import { useNavigate } from "react-router-dom";
import { fetchAndStoreInvoiceData } from "../utils/getInvoiceInfo.js";

function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async () => {
    setMessage("");
    const result = await login(username, password);
    if (result.success) {
      setMessage("✅ Login successful!");
      localStorage.setItem("token", result.token);
      localStorage.setItem("role", result.role);
      console.log("User role:", result.role);
      console.log("User name:", result.name);
      localStorage.setItem("name", result.name);
      navigate("/forecasts");

      await fetchAndStoreInvoiceData();
    } else {
      setMessage(result.message);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-primary text-base-content">
      <div className="bg-base-100 text-base-content rounded-2xl shadow-md px-10 py-8 w-[30%] text-center">
        <img src="/fy.png" alt="FutureYou" className="mx-auto mb-2" />
        <h2 className="text-xl font-small mb-6">
          Recruiter Forecast Dashboard
        </h2>

        <div className="text-left mb-4">
          <label className="block text-sm font-semibold mb-1">Username</label>
          <input
            type="text"
            placeholder="Enter your username"
            className="input input-bordered w-full"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div className="text-left mb-4">
          <label className="block text-sm font-semibold mb-1">Password</label>
          <div className="relative">
            <input
              type={showPassword ? "text" : "password"}
              placeholder="Enter your password"
              className="input input-bordered w-full pr-12"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              type="button"
              className="absolute top-1/2 right-3 transform -translate-y-1/2 text-sm text-primary"
              onClick={() => setShowPassword((prev) => !prev)}
            >
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>
        </div>
        <button
          onClick={handleLogin}
          className="btn btn-primary w-full py-2 mt-4"
        >
          Log In
        </button>

        {message && <div className="text-sm mt-4 text-error">{message}</div>}
      </div>

      <div className="absolute bottom-4 right-4 text-xs text-base-100">
        For any issues, please contact{" "}
        <a href="mailto:Leo@trihalo.com.au" className="underline">
          Leo@trihalo.com.au
        </a>
      </div>
    </div>
  );
}

export default Login;
