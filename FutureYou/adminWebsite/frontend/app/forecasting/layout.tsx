"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FC_AUTH } from "@/lib/forecasting-cache";

const NAV = [
  {
    href: "/forecasting",
    label: "Forecasts",
    roles: ["finance", "admin", "partner"],
  },
  {
    href: "/forecasting/revenue",
    label: "Revenue Dashboard",
    roles: ["finance"],
  },
  {
    href: "/forecasting/admin",
    label: "Admin Panel",
    roles: ["finance"],
  },
];

export default function ForecastingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const role = FC_AUTH.getRole() ?? "";

  const navLinks = NAV.filter((l) => l.roles.includes(role));

  // No sub-nav needed for the password page or if the user has no forecasting links
  if (pathname === "/forecasting/password" || navLinks.length === 0) {
    return <div className="flex flex-col h-full">{children}</div>;
  }

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-gray-200 bg-white shrink-0">
        <div className="flex items-center gap-4 px-4 sm:px-8 py-3 overflow-x-auto">
          <nav className="flex items-center gap-0.5">
            {navLinks.map(({ href, label }) => {
              const active =
                href === "/forecasting"
                  ? pathname === "/forecasting"
                  : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    active
                      ? "bg-navy text-white"
                      : "text-dark-grey hover:bg-gray-100 hover:text-navy"
                  }`}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
          {role === "finance" && FC_AUTH.getLastModified() && (
            <span className="ml-auto text-xs text-dark-grey hidden lg:block">
              Data updated: <b>{FC_AUTH.getLastModified()}</b>
            </span>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-auto">{children}</div>
    </div>
  );
}
