// src/components/Sidebar.jsx
import { useNavigate } from "react-router-dom";

function Sidebar({ onLogout }) {
  const navigate = useNavigate();

  return (
    <aside className="w-80 bg-gray-200 p-6 flex flex-col text-base-content">
      <div>
        <img src="/fy.png" alt="FutureYou" className="h-30" />
        <ul className="space-y-3">
          <li>
            <button
              className="btn btn-ghost justify-start w-full text-left text-lg font-extralight"
              onClick={() => navigate("/dashboard")}
            >
              📊 Revenue Breakdown
            </button>
          </li>
          <li>
            <button
              className="btn btn-ghost justify-start w-full text-left text-lg font-extralight"
              onClick={() => navigate("/upload")}
            >
              ⬆️ Upload Forecast
            </button>
          </li>
          <div className="divider" />
          <li>
            <button
              className="btn btn-ghost justify-start w-full text-left text-lg font-extralight"
              onClick={onLogout}
            >
              🚪 Logout
            </button>
          </li>
        </ul>
      </div>
    </aside>
  );
}

export default Sidebar;
