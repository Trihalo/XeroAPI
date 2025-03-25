import { LuLayoutDashboard } from "react-icons/lu";
import { LuHistory } from "react-icons/lu";
import { Link } from "react-router-dom";

export default function Sidebar() {
  return (
    <div className="w-60 h-screen bg-base-200 shadow-lg pt-5">
      <ul className="menu p-10 text-base-content">
        <li className="mb-2">
          <Link
            to="/"
            className="flex items-center gap-2 text-lg font-semibold text-primary"
          >
            Trihalo
          </Link>
          <div className="divider mt-18" />
        </li>
        <li>
          <Link
            to="/"
            className="flex items-center gap-2 rounded-lg text-md p-2 hover:bg-primary/20 mb-5"
          >
            <LuLayoutDashboard size={20} /> Dashboard
          </Link>
        </li>
        <li>
          <Link
            to="/history"
            className="flex items-center gap-2 rounded-lg text-md p-2 hover:bg-primary/20"
          >
            <LuHistory size={20} /> History
          </Link>
        </li>
      </ul>
    </div>
  );
}
