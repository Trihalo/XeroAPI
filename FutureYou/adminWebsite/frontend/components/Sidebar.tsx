"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CalendarDays, FileText } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/annual-leave", label: "Annual Leave", icon: CalendarDays },
  { href: "/talent-map",   label: "Talent Map",   icon: FileText },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 shrink-0 flex flex-col bg-navy text-white min-h-screen">
      {/* Logo */}
      <div className="px-5 pt-7 pb-6 border-b border-white/10">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/fy.png"
          alt="FutureYou"
          className="w-36 object-contain brightness-0 invert"
        />
        <p className="text-[11px] font-semibold tracking-widest uppercase text-white/40 mt-3">Admin</p>
      </div>

      <nav className="flex-1 px-3 py-5 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
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
              <Icon className={cn("w-4 h-4 shrink-0", active ? "text-salmon" : "")} />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
