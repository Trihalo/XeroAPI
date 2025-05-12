import { useNavigate } from "react-router-dom";
import calendar from "../data/calendar";
import { getCurrentMonthInfo } from "../utils/getCurrentMonthInfo";

const { weekLabel } = getCurrentMonthInfo(calendar);

function TopNavbar({ userName = "User" }) {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.clear();
    navigate("/", { replace: true });
  };

  return (
    <header className="w-full bg-gray-200 px-6 py-4 flex items-center justify-between text-sm">
      <div className="flex flex-row items-baseline gap-8">
        <div className="text-2xl text-gray-700 font-light">
          Hello, {userName}
        </div>
        <div className="text-sm text-gray-500">{weekLabel}</div>
      </div>

      <nav className="flex items-center space-x-6">
        <button
          className="hover:underline"
          onClick={() => navigate("/forecasts")}
        >
          Forecasts
        </button>
        <button
          className="hover:underline"
          onClick={() => navigate("/dashboard")}
        >
          Revenue
        </button>
        <button className="hover:underline" onClick={handleLogout}>
          Log Out
        </button>
        <img src="/fy.png" alt="FutureYou" className="h-12 ml-4" />
      </nav>
    </header>
  );
}

export default TopNavbar;
