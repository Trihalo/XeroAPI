"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";
import {
  Upload,
  FileSpreadsheet,
  RefreshCw,
  Info,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { generateTalentMap } from "@/lib/api";

export default function TalentMapPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [client, setClient] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [infoOpen, setInfoOpen] = useState(false);

  async function handleGenerate() {
    if (!file) {
      toast.error("Please select an Excel file");
      return;
    }
    if (!client) {
      toast.error("Client name is required");
      return;
    }
    if (!jobTitle) {
      toast.error("Job title is required");
      return;
    }

    setLoading(true);
    try {
      const blob = await generateTalentMap(file, client, jobTitle);

      const date = new Date()
        .toLocaleString("en-AU", { month: "short", year: "2-digit" })
        .replace(" ", "");
      const safeCorp = client.replace(/\//g, "-").replace(/ /g, "");
      const safeTitle = jobTitle
        .replace(/[^a-zA-Z0-9 -]/g, "")
        .slice(0, 30)
        .trim()
        .replace(/ /g, "");
      const filename = `FYTalentMap_${safeCorp}_${safeTitle}_${date}.docx`;

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);

      toast.success("Word document downloaded");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-8 max-w-4xl">
      <h1 className="text-2xl font-bold text-navy mb-1">
        Talent Map Generator
      </h1>
      <p className="text-dark-grey text-sm mb-4">
        Upload a talent map Excel file to produce a formatted Word document.
      </p>

      {/* ── Instructions panel ── */}
      <div className="mb-6">
        <button
          onClick={() => setInfoOpen((o) => !o)}
          className="flex items-center gap-1.5 text-sm text-dark-grey hover:text-navy transition-colors mb-2"
          aria-label="Toggle instructions"
        >
          <Info className="w-4 h-4" />
          How to use
          {infoOpen ? (
            <ChevronUp className="w-3.5 h-3.5" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5" />
          )}
        </button>

        {infoOpen && (
          <div className="rounded-xl border border-[#e0e0e0] bg-white shadow-sm overflow-hidden">
            <div className="bg-navy px-5 py-3.5 flex items-center gap-2">
              <Info className="w-4 h-4 text-salmon" />
              <span className="text-white font-semibold text-sm">
                How to use the Talent Map Generator
              </span>
            </div>
            <div className="px-5 py-4 flex flex-col gap-5 text-sm text-dark-grey">
              {/* Excel format */}
              <div>
                <h3 className="font-semibold text-navy text-sm mb-2">
                  Required Excel columns
                </h3>
                <p className="mb-2 leading-relaxed">
                  Your{" "}
                  <code className="bg-gray-100 px-1 py-0.5 rounded text-xs">
                    .xlsx
                  </code>{" "}
                  file must have the following columns in order, with a header
                  row:
                </p>
                <div className="overflow-x-auto rounded-lg border border-[#e0e0e0]">
                  <table className="text-xs w-full border-collapse">
                    <thead>
                      <tr className="bg-navy text-white">
                        {[
                          "Name",
                          "Current Company",
                          "Role Title",
                          "Location",
                          "Salary",
                          "LI Profile",
                          "Notes",
                        ].map((h) => (
                          <th
                            key={h}
                            className="px-3 py-2 text-left font-medium whitespace-nowrap"
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="bg-gray-50 text-dark-grey">
                        <td className="px-3 py-2 border-t border-[#e8e8e8]">
                          Jane Smith
                        </td>
                        <td className="px-3 py-2 border-t border-[#e8e8e8]">
                          Acme Corp
                        </td>
                        <td className="px-3 py-2 border-t border-[#e8e8e8]">
                          Senior Recruiter
                        </td>
                        <td className="px-3 py-2 border-t border-[#e8e8e8]">
                          Sydney
                        </td>
                        <td className="px-3 py-2 border-t border-[#e8e8e8]">
                          $110,000
                        </td>
                        <td className="px-3 py-2 border-t border-[#e8e8e8]">
                          linkedin.com/in/…
                        </td>
                        <td className="px-3 py-2 border-t border-[#e8e8e8]">
                          Open to roles
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <p className="text-xs text-dark-grey mt-2">
                  Each row = one candidate. LinkedIn URLs are auto-formatted as
                  clickable links in the Word doc.
                </p>
              </div>

              {/* Highlight feature */}
              <div>
                <h3 className="font-semibold text-navy text-sm mb-2">
                  Highlight feature
                </h3>
                <p className="leading-relaxed mb-2">
                  If you apply a <strong>cell background colour </strong> to a
                  candidate&apos;s <strong>Name cell</strong> in Excel, that
                  colour is carried through to the Word document.
                </p>
                <div className="rounded-lg border border-[#e0e0e0] bg-gray-50 px-4 py-3 text-xs leading-relaxed">
                  <p className="font-medium text-navy mb-1">Example uses:</p>
                  <ul className="flex flex-col gap-1">
                    <li className="flex gap-2">
                      <span
                        className="inline-block w-3 h-3 rounded-sm mt-0.5 flex-shrink-0"
                        style={{ background: "#FFFF00" }}
                      />
                      Yellow — shortlisted candidate
                    </li>
                    <li className="flex gap-2">
                      <span
                        className="inline-block w-3 h-3 rounded-sm mt-0.5 flex-shrink-0"
                        style={{ background: "#90EE90" }}
                      />
                      Green — confirmed interview
                    </li>
                    <li className="flex gap-2">
                      <span
                        className="inline-block w-3 h-3 rounded-sm mt-0.5 flex-shrink-0"
                        style={{ background: "#FFB6C1" }}
                      />
                      Pink — on hold
                    </li>
                  </ul>
                  <p className="mt-2 text-dark-grey">
                    Any colour works — whatever convention your team uses in
                    Excel will be preserved in the output.
                  </p>
                </div>
              </div>

              {/* Output */}
              <div>
                <h3 className="font-semibold text-navy text-sm mb-2">Output</h3>
                <p className="leading-relaxed">
                  A{" "}
                  <code className="bg-gray-100 px-1 py-0.5 rounded text-xs">
                    .docx
                  </code>{" "}
                  file is downloaded automatically. Each page has a branded
                  header showing the <strong>Client</strong> name and{" "}
                  <strong>Job Title</strong> you enter below, alongside the
                  FutureYou logo. The file is ready to export to PDF from Word.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="space-y-5 max-w-xl">
        {/* File upload */}
        <div className="space-y-2">
          <Label htmlFor="excel-file" className="text-navy font-medium">
            Excel File (.xlsx)
          </Label>
          <div
            className="flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-[#e0e0e0] bg-white px-6 py-10 cursor-pointer hover:border-salmon/40 hover:bg-salmon/5 transition-colors"
            onClick={() => fileRef.current?.click()}
          >
            {file ? (
              <>
                <FileSpreadsheet className="w-8 h-8 text-navy" />
                <span className="text-sm font-medium text-navy">
                  {file.name}
                </span>
                <span className="text-xs text-dark-grey">
                  {(file.size / 1024).toFixed(0)} KB — click to change
                </span>
              </>
            ) : (
              <>
                <Upload className="w-8 h-8 text-dark-grey" />
                <span className="text-sm text-dark-grey">
                  Click to select a .xlsx file
                </span>
              </>
            )}
            <input
              id="excel-file"
              ref={fileRef}
              type="file"
              accept=".xlsx"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
        </div>

        {/* Client name */}
        <div className="space-y-2">
          <Label htmlFor="client" className="text-navy font-medium">
            Client Name
          </Label>
          <Input
            id="client"
            placeholder="e.g. Jaybro"
            value={client}
            onChange={(e) => setClient(e.target.value)}
            className="bg-white border-[#e0e0e0] focus-visible:ring-navy"
          />
        </div>

        {/* Job title */}
        <div className="space-y-2">
          <Label htmlFor="job-title" className="text-navy font-medium">
            Job Title
          </Label>
          <Input
            id="job-title"
            placeholder="e.g. Head of Product Supply Chain"
            value={jobTitle}
            onChange={(e) => setJobTitle(e.target.value)}
            className="bg-white border-[#e0e0e0] focus-visible:ring-navy"
          />
        </div>

        <Button
          onClick={handleGenerate}
          disabled={loading || !file}
          className="w-full bg-navy hover:bg-navy/90 text-white shadow-sm"
        >
          {loading ? (
            <>
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              Generating…
            </>
          ) : (
            "Generate Word Doc"
          )}
        </Button>
      </div>
    </div>
  );
}
