"use client";

import { useState } from "react";
import { toast } from "sonner";
import { RefreshCw, Info, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { generateAnnualLeave } from "@/lib/api";

export default function AnnualLeavePage() {
  const [loading, setLoading] = useState(false);
  const [html, setHtml] = useState<string | null>(null);
  const [infoOpen, setInfoOpen] = useState(false);

  async function handleGenerate() {
    setLoading(true);
    setHtml(null);
    try {
      const result = await generateAnnualLeave();
      setHtml(result);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-4 sm:p-6 md:p-8 flex flex-col gap-6 h-full">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-navy">Annual Leave Report</h1>
          <p className="text-dark-grey text-sm mt-0.5">
            Fetches live data from Xero Payroll — may take 20–40 seconds.
          </p>
        </div>
        <Button
          onClick={handleGenerate}
          disabled={loading}
          className="bg-navy hover:bg-navy/90 text-white shadow-sm self-start sm:self-auto"
        >
          {loading ? (
            <>
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              Generating…
            </>
          ) : (
            "Generate Report"
          )}
        </Button>
      </div>

      {/* Instructions panel (only shown after report is generated) */}
      {html && !loading && (
        <div>
          <button
            onClick={() => setInfoOpen((o) => !o)}
            className="flex items-center gap-1.5 text-sm text-dark-grey hover:text-navy transition-colors mb-2"
            aria-label="Toggle instructions"
          >
            <Info className="w-4 h-4" />
            How to read this report
            {infoOpen ? (
              <ChevronUp className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      )}

      {html && !loading && infoOpen && (
        <div className="rounded-xl border border-[#e0e0e0] bg-white shadow-sm overflow-hidden">
          <div className="bg-navy px-6 py-4 flex items-center gap-2">
            <Info className="w-4 h-4 text-salmon" />
            <span className="text-white font-semibold text-sm">
              How to use this report
            </span>
          </div>
          <div className="px-6 py-5 grid grid-cols-1 md:grid-cols-3 gap-6 text-sm text-dark-grey">
            <div className="flex flex-col gap-2">
              <h3 className="font-semibold text-navy text-sm">
                Report sections
              </h3>
              <p className="leading-relaxed">
                The report contains three parts:
              </p>
              <ul className="flex flex-col gap-1.5 mt-1">
                <li className="flex gap-2">
                  <span className="text-salmon font-bold mt-0.5">1.</span>
                  <span>
                    <strong>AL Balances</strong> — current leave balance for
                    every employee, their upcoming scheduled hours, and their
                    projected balance after that leave is taken.
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-salmon font-bold mt-0.5">2.</span>
                  <span>
                    <strong>Scheduled Leave</strong> — a list of all upcoming
                    approved leave periods, including dates and description.
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-salmon font-bold mt-0.5">3.</span>
                  <span>
                    <strong>Leave Calendar</strong> — a month-by-month visual
                    showing who is off on each day, colour-coded per employee.
                  </span>
                </li>
              </ul>
            </div>

            <div className="flex flex-col gap-2">
              <h3 className="font-semibold text-navy text-sm">Column guide</h3>
              <div className="flex flex-col gap-2 mt-1">
                <div className="rounded-lg bg-gray-50 border border-[#e8e8e8] px-3 py-2">
                  <p className="font-medium text-navy text-xs mb-0.5">
                    AL Bal (hrs)
                  </p>
                  <p className="text-xs leading-relaxed">
                    The employee&apos;s current accrued annual leave balance in
                    hours, as reported by Xero Payroll right now.
                  </p>
                </div>
                <div className="rounded-lg bg-gray-50 border border-[#e8e8e8] px-3 py-2">
                  <p className="font-medium text-navy text-xs mb-0.5">
                    Scheduled (hrs)
                  </p>
                  <p className="text-xs leading-relaxed">
                    Total hours of approved &amp; scheduled future leave already
                    booked in Xero.
                  </p>
                </div>
                <div className="rounded-lg bg-gray-50 border border-[#e8e8e8] px-3 py-2">
                  <p className="font-medium text-navy text-xs mb-0.5">
                    AL Bal inc. Scheduled
                  </p>
                  <p className="text-xs leading-relaxed">
                    Projected balance after all scheduled leave is deducted.{" "}
                    <em>AL Bal − Scheduled Hours.</em>
                  </p>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <h3 className="font-semibold text-navy text-sm">
                Highlight feature
              </h3>
              <p className="leading-relaxed">
                When an employee&apos;s <strong>AL Bal inc. Scheduled</strong>{" "}
                drops below zero, that cell is highlighted in{" "}
                <span className="font-semibold" style={{ color: "#F25A57" }}>
                  salmon/red
                </span>
                .
              </p>
              <div className="rounded-lg border border-[#fdd] bg-[#fff5f5] px-3 py-2 mt-1 text-xs leading-relaxed">
                This means the employee has{" "}
                <strong>more leave booked than they have accrued</strong>. They
                will go into negative leave if the bookings proceed.
              </div>
            </div>
          </div>
        </div>
      )}

      {loading && (
        <div className="flex-1 flex flex-col items-center justify-center gap-6 rounded-xl border border-[#e0e0e0] bg-white/50">
          <div className="relative w-20 h-20">
            <span className="absolute inset-0 rounded-full border-4 border-salmon/20" />
            <span className="absolute inset-0 rounded-full border-4 border-t-salmon border-r-transparent border-b-transparent border-l-transparent animate-spin" />
            <span className="absolute inset-2 rounded-full border-4 border-t-transparent border-r-navy/30 border-b-navy/30 border-l-transparent animate-spin [animation-direction:reverse] [animation-duration:1.4s]" />
          </div>
          <div className="text-center">
            <p className="text-navy font-semibold text-sm">
              Fetching leave data from Xero…
            </p>
            <p className="text-dark-grey text-xs mt-1">
              This may take 20–40 seconds
            </p>
          </div>
        </div>
      )}

      {html && !loading && (
        <iframe
          srcDoc={html}
          className="flex-1 w-full rounded-xl border border-[#e0e0e0] bg-white shadow-sm"
          style={{ minHeight: "75vh" }}
          title="Annual Leave Report"
          sandbox="allow-same-origin"
        />
      )}

      {!html && !loading && (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-[#e0e0e0] text-dark-grey bg-white/50 py-16">
          <p className="text-sm font-medium">No report generated yet.</p>
          <p className="text-xs text-center max-w-xs">
            Click <strong>&ldquo;Generate Report&rdquo;</strong> to pull live
            data from Xero
          </p>
        </div>
      )}
    </div>
  );
}
