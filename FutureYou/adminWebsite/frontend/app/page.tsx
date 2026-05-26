"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  CalendarDays,
  FileText,
  TrendingUp,
  Trophy,
  ArrowRight,
} from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { FC_AUTH } from "@/lib/forecasting-cache";

const ALL_TOOLS = [
  {
    href: "/annual-leave",
    icon: CalendarDays,
    title: "Annual Leave Report",
    description:
      "Fetch live leave balances and upcoming leave from Xero Payroll and view the full HTML report in the browser.",
    roles: ["finance", "admin"],
  },
  {
    href: "/talent-map",
    icon: FileText,
    title: "Talent Map Generator",
    description:
      "Upload a talent map Excel file and generate a branded, landscape Word document ready for PDF export.",
    roles: ["finance", "admin", "partner", "recruiter"],
  },
  {
    href: "/forecasting",
    icon: TrendingUp,
    title: "Forecasting",
    description:
      "Enter weekly revenue forecasts, view actuals vs targets, and manage recruiters and monthly goals.",
    roles: ["finance", "admin", "partner"],
  },
  {
    href: "/legends",
    icon: Trophy,
    title: "Legends Table",
    description:
      "Consultant revenue split by perm & temp, compared to the same period last financial year.",
    roles: ["finance", "admin", "partner", "recruiter"],
  },
];

export default function Home() {
  const [role, setRole] = useState("");

  useEffect(() => {
    setRole(FC_AUTH.getRole() ?? "");
  }, []);

  const tools = ALL_TOOLS.filter((t) => !role || t.roles.includes(role));

  return (
    <div className="p-4 sm:p-6 md:p-8 max-w-3xl">
      <h1 className="text-2xl font-bold text-navy mb-1">FutureYou Admin</h1>
      <p className="text-dark-grey text-sm mb-3">
        This website hosts internal tools for FutureYou. Select a tool below to
        get started.
      </p>
      <p className="text-dark-grey text-sm mb-8">
        For any issues, please ask Tanya or email{" "}
        <a
          href="mailto:leoshi@future-you.com.au"
          className="text-navy font-semibold hover:underline"
        >
          leoshi@future-you.com.au
        </a>
        .
      </p>

      <div className="grid sm:grid-cols-2 gap-5">
        {tools.map(({ href, icon: Icon, title, description }) => (
          <Link key={href} href={href} className="group block">
            <Card className="h-full bg-white border-[#e0e0e0] transition-all duration-150 group-hover:shadow-lg group-hover:-translate-y-0.5">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3 mb-2">
                  <div className="p-2.5 rounded-lg bg-salmon/10">
                    <Icon className="w-5 h-5 text-salmon" />
                  </div>
                  <CardTitle className="text-base text-navy">{title}</CardTitle>
                </div>
                <CardDescription className="text-dark-grey text-sm leading-relaxed">
                  {description}
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-0">
                <span className="flex items-center gap-1 text-sm font-semibold text-salmon group-hover:gap-2 transition-all duration-150">
                  Open <ArrowRight className="w-4 h-4" />
                </span>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
