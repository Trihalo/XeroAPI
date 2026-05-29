"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  CalendarDays,
  FileText,
  TrendingUp,
  Trophy,
  LogOut,
  KeyRound,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { FC_AUTH } from "@/lib/forecasting-cache";

const ALL_NAV = [
  {
    href: "/annual-leave",
    label: "Annual Leave",
    icon: CalendarDays,
    roles: ["finance", "admin"],
  },
  {
    href: "/talent-map",
    label: "Talent Map",
    icon: FileText,
    roles: ["finance", "admin", "partner", "recruiter"],
  },
  {
    href: "/forecasting",
    label: "Forecasting",
    icon: TrendingUp,
    roles: ["finance", "admin", "partner"],
  },
  {
    href: "/legends",
    label: "Legends",
    icon: Trophy,
    roles: ["finance", "admin", "partner", "recruiter"],
  },
];

const ROLE_LABELS: Record<string, string> = {
  finance: "Finance",
  admin: "Admin",
  partner: "Partner",
  recruiter: "Recruiter",
};

export default function Sidebar({ onClose }: { onClose?: () => void }) {
  const pathname = usePathname();
  const role = FC_AUTH.getRole() ?? "";
  const name = FC_AUTH.getName() ?? "";

  const nav = ALL_NAV.filter((n) => n.roles.includes(role));

  function handleLogout() {
    FC_AUTH.clear();
    window.location.href = "/";
  }

  return (
    <aside className="w-64 md:w-56 shrink-0 flex flex-col bg-navy text-white h-screen">
      {/* Logo + mobile close button */}
      <div className="flex items-start justify-between px-5 pt-7 pb-6 border-b border-white/10">
        <Link href="/" className="block" onClick={onClose}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/fy.png"
            alt="FutureYou"
            className="w-32 object-contain brightness-0 invert"
          />
          <p className="text-[11px] font-semibold tracking-widest uppercase text-white/40 mt-3">
            Admin
          </p>
        </Link>
        <button
          onClick={onClose}
          className="md:hidden p-1 rounded-md text-white/50 hover:text-white hover:bg-white/10 mt-1"
          aria-label="Close menu"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <nav className="flex-1 px-3 py-5 space-y-0.5 overflow-y-auto">
        {nav.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/forecasting"
              ? pathname.startsWith("/forecasting") &&
                !pathname.startsWith("/legends")
              : pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              onClick={onClose}
              className={cn(
                "relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                active
                  ? "bg-white/10 text-white"
                  : "text-white/60 hover:bg-white/8 hover:text-white/90",
              )}
            >
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-salmon rounded-r-full" />
              )}
              <Icon
                className={cn(
                  "w-4 h-4 shrink-0",
                  active ? "text-salmon" : "",
                )}
              />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* User info + actions */}
      <div className="px-3 pb-5 border-t border-white/10 pt-4 space-y-1">
        <div className="px-3 py-2">
          <p className="text-white text-sm font-semibold truncate">{name}</p>
          {role && (
            <span className="text-xs bg-salmon/20 text-salmon font-semibold px-2 py-0.5 rounded-full mt-1 inline-block">
              {ROLE_LABELS[role] ?? role}
            </span>
          )}
        </div>
        <Link
          href="/forecasting/password"
          onClick={onClose}
          className={cn(
            "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
            pathname === "/forecasting/password"
              ? "bg-white/10 text-white"
              : "text-white/60 hover:bg-white/8 hover:text-white/90",
          )}
        >
          <KeyRound className="w-4 h-4" />
          Change password
        </Link>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-white/60 hover:bg-white/8 hover:text-white/90 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
