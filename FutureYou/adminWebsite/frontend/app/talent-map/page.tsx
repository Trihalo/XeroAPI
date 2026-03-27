"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";
import { Upload, FileSpreadsheet, RefreshCw } from "lucide-react";
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

  async function handleGenerate() {
    if (!file)     { toast.error("Please select an Excel file");  return; }
    if (!client)   { toast.error("Client name is required");      return; }
    if (!jobTitle) { toast.error("Job title is required");        return; }

    setLoading(true);
    try {
      const blob = await generateTalentMap(file, client, jobTitle);

      const date      = new Date().toLocaleString("en-AU", { month: "short", year: "2-digit" }).replace(" ", "");
      const safeCorp  = client.replace(/\//g, "-").replace(/ /g, "");
      const safeTitle = jobTitle.replace(/[^a-zA-Z0-9 -]/g, "").slice(0, 30).trim().replace(/ /g, "");
      const filename  = `FYTalentMap_${safeCorp}_${safeTitle}_${date}.docx`;

      const url = URL.createObjectURL(blob);
      const a   = document.createElement("a");
      a.href     = url;
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
    <div className="p-8 max-w-xl">
      <h1 className="text-2xl font-bold text-navy mb-1">Talent Map Generator</h1>
      <p className="text-dark-grey text-sm mb-8">
        Upload a talent map Excel file to produce a formatted Word document.
      </p>

      <div className="space-y-5">
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
                <span className="text-sm font-medium text-navy">{file.name}</span>
                <span className="text-xs text-dark-grey">
                  {(file.size / 1024).toFixed(0)} KB — click to change
                </span>
              </>
            ) : (
              <>
                <Upload className="w-8 h-8 text-dark-grey" />
                <span className="text-sm text-dark-grey">Click to select a .xlsx file</span>
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
          <Label htmlFor="client" className="text-navy font-medium">Client Name</Label>
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
          <Label htmlFor="job-title" className="text-navy font-medium">Job Title</Label>
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
