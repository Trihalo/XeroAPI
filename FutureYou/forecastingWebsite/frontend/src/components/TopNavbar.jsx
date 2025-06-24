import { useState } from "react";
import { useNavigate } from "react-router-dom";
import calendar from "../data/calendar";
import { getCurrentMonthInfo } from "../utils/getCurrentMonthInfo";

const { weekLabel } = getCurrentMonthInfo(calendar);

function TopNavbar({ userName = "User" }) {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const role = localStorage.getItem("role");

  const handleLogout = () => {
    localStorage.clear();
    navigate("/", { replace: true });
  };

  const toggleMenu = () => setMenuOpen((prev) => !prev);

  return (
    <header className="w-full bg-base-300 px-10 py-4 flex items-center justify-between text-sm relative">
      {/* Left side */}
      <div className="flex items-baseline gap-4">
        <div className="text-2xl text-primary font-light">
          Hello, {userName}
        </div>
        <div className="text-sm text-gray-500">{weekLabel}</div>
      </div>

      {/* Hamburger Button (Mobile) */}
      <button className="md:hidden flex flex-col gap-1" onClick={toggleMenu}>
        <span className="w-6 h-0.5 bg-gray-700 rounded"></span>
        <span className="w-6 h-0.5 bg-gray-700 rounded"></span>
        <span className="w-6 h-0.5 bg-gray-700 rounded"></span>
      </button>

      {/* Desktop Nav */}
      <nav className="hidden md:flex items-center space-x-6">
        {role === "admin" && (
          <button
            className="hover:underline"
            onClick={() => navigate("/admin")}
          >
            Admin
          </button>
        )}
        <button
          className="hover:underline"
          onClick={() => navigate("/forecasts")}
        >
          Forecasts
        </button>
        {role === "admin" && (
          <button
            className="hover:underline"
            onClick={() => navigate("/legends")}
          >
            Legends
          </button>
        )}
        {role === "admin" && (
          <button
            className="hover:underline"
            onClick={() => navigate("/dashboard")}
          >
            Revenue
          </button>
        )}
        <button className="hover:underline" onClick={handleLogout}>
          Log Out
        </button>
        <img src="/fy.png" alt="FutureYou" className="h-12 ml-4" />
      </nav>

      {/* Mobile Dropdown */}
      {menuOpen && (
        <div className="absolute top-16 right-4 w-56 bg-base-100 border border-gray-300 rounded-lg shadow-lg z-50 p-4 animate-fadeIn space-y-2">
          {role === "admin" && (
            <button
              className="w-full text-left px-4 py-2 rounded hover:bg-base-200 text-base-content"
              onClick={() => {
                navigate("/admin");
                setMenuOpen(false);
              }}
            >
              Admin
            </button>
          )}
          <button
            className="w-full text-left px-4 py-2 rounded hover:bg-base-200 text-base-content"
            onClick={() => {
              navigate("/forecasts");
              setMenuOpen(false);
            }}
          >
            Forecasts
          </button>
          {role === "admin" && (
            <button
              className="w-full text-left px-4 py-2 rounded hover:bg-base-200 text-base-content"
              onClick={() => {
                navigate("/dashboard");
                setMenuOpen(false);
              }}
            >
              Revenue
            </button>
          )}
          <hr className="my-2 border-gray-200" />
          <button
            className="w-full text-left px-4 py-2 rounded hover:bg-accent text-secondary"
            onClick={() => {
              handleLogout();
              setMenuOpen(false);
            }}
          >
            Log Out
          </button>
        </div>
      )}
    </header>
  );
}

export default TopNavbar;
