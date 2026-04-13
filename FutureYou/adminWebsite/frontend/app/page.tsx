import Link from "next/link";
import { CalendarDays, FileText, TrendingUp, ArrowRight } from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";

const TOOLS = [
  {
    href: "/annual-leave",
    icon: CalendarDays,
    title: "Annual Leave Report",
    description:
      "Fetch live leave balances and upcoming leave from Xero Payroll and view the full HTML report in the browser.",
  },
  {
    href: "/talent-map",
    icon: FileText,
    title: "Talent Map Generator",
    description:
      "Upload a talent map Excel file and generate a branded, landscape Word document ready for PDF export.",
  },
  {
    href: "/forecasting",
    icon: TrendingUp,
    title: "Forecasting",
    description:
      "Enter weekly revenue forecasts, view actuals vs targets, and manage recruiters and monthly goals.",
  },
];

export default function Home() {
  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold text-navy mb-1">FutureYou Admin</h1>
      <p className="text-dark-grey text-sm mb-8">
        Internal admin tools dashboard
      </p>

      <div className="grid sm:grid-cols-2 gap-5">
        {TOOLS.map(({ href, icon: Icon, title, description }) => (
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
