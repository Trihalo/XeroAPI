import { useNavigate } from "react-router-dom";
import calendar from "../data/calendar"; // 👈 import the calendar

function TopNavbar({ userName = "User" }) {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.clear();
    navigate("/", { replace: true });
  };

  // 🔍 Determine current week label based on today's date
  const today = new Date();

  const matchedEntry = calendar.find((entry) => {
    const [startStr, endStr] = entry.range.split(" - ");
    const [sd, sm, sy] = startStr.split("/").map(Number);
    const [ed, em, ey] = endStr.split("/").map(Number);

    const start = new Date(sy < 100 ? sy + 2000 : sy, sm - 1, sd);
    const end = new Date(ey < 100 ? ey + 2000 : ey, em - 1, ed);

    return today >= start && today <= end;
  });

  const formattedDate = `${new Date().getDate()}/${
    new Date().getMonth() + 1
  }/${new Date().getFullYear().toString().slice(-2)}`;

  const weekLabel = matchedEntry
    ? `${matchedEntry.month} Week ${matchedEntry.week}, ${formattedDate}`
    : "";

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
