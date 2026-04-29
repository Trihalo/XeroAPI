import { useState, useEffect, useRef } from "react";
import * as XLSX from "xlsx";
import {
  Upload,
  FileSpreadsheet,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Info,
} from "lucide-react";
import { toast } from "sonner";
import Sidebar from "@/components/Sidebar";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { fetchFileInfo, uploadFile, type FileInfo } from "@/api";

// ── Template column definitions ───────────────────────────────────────────────
interface TemplateColumn {
  name: string;
  example: string;
  description: string;
}

// ── Managed file definitions ─────────────────────────────────────────────────
interface ManagedFile {
  label: string;
  description: string;
  repoPath: string;
  filename: string;
  client: string;
  clientColor: string;
  templateColumns: TemplateColumn[];
  templateNote?: string;
}

const MANAGED_FILES: ManagedFile[] = [
  {
    label: "Purchase Orders",
    description:
      "At the end of every month, H2coco's Supplier Prepayment account is updated. Upload an updated file with the PO list. This list drives the Supplier Payment Allocator tool.",
    repoPath: "H2coco/PO.xlsx",
    filename: "PO.xlsx",
    client: "H2coco",
    clientColor: "bg-cyan-100 text-cyan-700",
    templateColumns: [
      {
        name: "PO",
        example: "1",
        description: "Purchase Order number (Match Unleashed)",
      },
      {
        name: "Date",
        example: "16/07/2025",
        description: "Date when the Deposit was made",
      },
      {
        name: "CurrencyRate",
        example: "0.6698",
        description: "FX rate (USD→AUD)",
      },
      {
        name: "Amount",
        example: "11025.00",
        description: "DP amount made in USD",
      },
    ],
    templateNote:
      "One row per Purchase Order. Rows with no PO number are ignored.",
  },
  {
    label: "Trade Finance Payments",
    description:
      "H2coco may use Trade Finance to fund supplier payments. Use this tool to automatically allocate Trade Finance payments to Xero Bills.",
    repoPath: "H2coco/TradeFinance.xlsx",
    filename: "TradeFinance.xlsx",
    client: "H2coco",
    clientColor: "bg-cyan-100 text-cyan-700",
    templateColumns: [
      {
        name: "PO",
        example: "4582",
        description: "Purchase Order number (Match Unleashed)",
      },
      {
        name: "Date",
        example: "09/12/2025",
        description: "Trade Finance payment date",
      },
      {
        name: "CurrencyRate",
        example: "0.6607",
        description: "FX rate (USD→AUD)",
      },
      {
        name: "Amount",
        example: "14586.00",
        description: "Payment amount in USD",
      },
    ],
    templateNote:
      "One row per Trade Finance payment. Must match a Xero bill by PO number.",
  },
  {
    label: "Sun Road Deposits",
    description:
      "A list of Sun Road deposit payments. This list is necessary for the Sun Road Invoice Approver to allocate deposit payments accurately.",
    repoPath: "H2coco/SR.xlsx",
    filename: "SR.xlsx",
    client: "H2coco",
    clientColor: "bg-cyan-100 text-cyan-700",
    templateColumns: [
      {
        name: "Date",
        example: "29/12/2025",
        description: "Deposit Date",
      },
      {
        name: "H2coco PO",
        example: "1234",
        description: "H2coco Purchase Order Number",
      },
      {
        name: "Sun Road PO",
        example: "987654",
        description: "Sun Road Purchase Order Number",
      },
      {
        name: "DP Amount (USD)",
        example: "1000.00",
        description: "Deposit Amount in USD",
      },
      {
        name: "DP Amount (AUD)",
        example: "1500.00",
        description: "Deposit Amount in AUD",
      },
    ],
    templateNote: "One row per Sun Road deposit.",
  },
  {
    label: "Customer Prepayments",
    description:
      "Flight Risk customers pay upfront for their orders. The Customer Prepayment account stores these payments. Use this tool to automatically allocate to AR invoices.",
    repoPath: "FlightRisk/CustomerPrepayment.xlsx",
    filename: "CustomerPrepayment.xlsx",
    client: "FlightRisk",
    clientColor: "bg-emerald-100 text-emerald-700",
    templateColumns: [
      {
        name: "Sales Order Number",
        example: "FRC#3194",
        description: "Flight Risk sales order reference",
      },
      {
        name: "Payment Date",
        example: "29/12/2025",
        description: "Date customer paid",
      },
      {
        name: "Prepayment $",
        example: "11635.98",
        description: "Prepayment amount in AUD",
      },
    ],
    templateNote:
      "One row per prepayment. Sales Order Number must match the Xero invoice reference.",
  },
];

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatRelativeDate(iso: string | null): string {
  if (!iso) return "Never uploaded";
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 30) return `${days} days ago`;
  const months = Math.floor(days / 30);
  return months === 1 ? "1 month ago" : `${months} months ago`;
}

function formatFullDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-AU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function staleness(
  iso: string | null,
): "fresh" | "aging" | "stale" | "unknown" {
  if (!iso) return "unknown";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 14) return "fresh";
  if (days <= 45) return "aging";
  return "stale";
}

/** Parse the first row of an xlsx file and return the header strings. */
async function readXlsxHeaders(file: File): Promise<string[]> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target!.result as ArrayBuffer);
        const wb = XLSX.read(data, { type: "array" });
        const ws = wb.Sheets[wb.SheetNames[0]];
        const rows = XLSX.utils.sheet_to_json<string[]>(ws, {
          header: 1,
          defval: null,
        });
        const headers = (rows[0] ?? []).filter((h) => h !== null) as string[];
        resolve(headers);
      } catch {
        reject(new Error("Could not read file."));
      }
    };
    reader.onerror = () => reject(new Error("File read error."));
    reader.readAsArrayBuffer(file);
  });
}

// ── Template dialog ───────────────────────────────────────────────────────────
function TemplateDialog({
  managed,
  open,
  onClose,
}: {
  managed: ManagedFile;
  open: boolean;
  onClose: () => void;
}) {
  const PLACEHOLDER_ROWS = 3;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-3xl p-8">
        <DialogHeader>
          <div className="flex items-center gap-2 mb-1">
            <FileSpreadsheet className="h-5 w-5" style={{ color: "#151f4a" }} />
            <DialogTitle className="text-lg">
              {managed.label} — Template
            </DialogTitle>
          </div>
          <DialogDescription className="text-sm">
            Your uploaded file must match this column structure exactly (first
            row = headers).
          </DialogDescription>
        </DialogHeader>

        {/* Spreadsheet preview */}
        <div className="overflow-x-auto rounded-lg border border-border mt-2">
          <table className="w-full text-sm border-collapse">
            <thead>
              {/* Column letter header */}
              <tr>
                <th className="w-10 border-r border-b border-border bg-muted px-3 py-2 text-center text-muted-foreground font-normal" />
                {managed.templateColumns.map((_col, i) => (
                  <th
                    key={i}
                    className="border-r border-b border-border bg-muted px-5 py-2 text-center font-mono text-muted-foreground font-normal tracking-wide"
                  >
                    {String.fromCharCode(65 + i)}
                  </th>
                ))}
              </tr>
              {/* Column name header (row 1) */}
              <tr>
                <td className="border-r border-b border-border bg-muted px-3 py-2 text-center text-muted-foreground font-mono text-xs">
                  1
                </td>
                {managed.templateColumns.map((col, i) => (
                  <td
                    key={i}
                    className="border-r border-b border-border px-5 py-3 font-semibold text-foreground whitespace-nowrap"
                    style={{ backgroundColor: "#151f4a12" }}
                  >
                    {col.name}
                  </td>
                ))}
              </tr>
            </thead>
            <tbody>
              {/* Example data row */}
              <tr>
                <td className="border-r border-b border-border bg-muted px-3 py-2 text-center text-muted-foreground font-mono text-xs">
                  2
                </td>
                {managed.templateColumns.map((col, i) => (
                  <td
                    key={i}
                    className="border-r border-b border-border px-5 py-3 text-foreground/80 whitespace-nowrap"
                  >
                    {col.example}
                  </td>
                ))}
              </tr>
              {/* Placeholder rows */}
              {Array.from({ length: PLACEHOLDER_ROWS }).map((_, ri) => (
                <tr key={ri}>
                  <td className="border-r border-b border-border bg-muted px-3 py-2 text-center text-muted-foreground font-mono text-xs">
                    {ri + 3}
                  </td>
                  {managed.templateColumns.map((_, ci) => (
                    <td
                      key={ci}
                      className="border-r border-b border-border px-5 py-3"
                    >
                      <div className="h-3.5 rounded bg-muted-foreground/10 w-20" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Column descriptions */}
        <div className="space-y-3 mt-4">
          {managed.templateColumns.map((col, i) => (
            <div key={i} className="flex items-baseline gap-3 text-sm">
              <span
                className="shrink-0 font-mono font-semibold px-2 py-1 rounded text-xs"
                style={{ backgroundColor: "#151f4a12", color: "#151f4a" }}
              >
                {col.name}
              </span>
              <span className="text-muted-foreground">{col.description}</span>
            </div>
          ))}
        </div>

        {managed.templateNote && (
          <p className="text-sm text-muted-foreground border-t border-border pt-4 mt-2">
            {managed.templateNote}
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ── File card ─────────────────────────────────────────────────────────────────
function FileCard({ managed }: { managed: ManagedFile }) {
  const [info, setInfo] = useState<FileInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [templateOpen, setTemplateOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const loadInfo = () => {
    setLoading(true);
    fetchFileInfo(managed.repoPath)
      .then(setInfo)
      .catch(() =>
        setInfo({
          path: managed.repoPath,
          last_updated_at: null,
          last_updated_by: null,
        }),
      )
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadInfo();
  }, [managed.repoPath]);

  const handleUpload = async (file: File) => {
    if (
      !file.name.toLowerCase().endsWith(".xlsx") &&
      !file.name.toLowerCase().endsWith(".xls")
    ) {
      toast.error("Only .xlsx or .xls files are accepted.");
      return;
    }

    // ── Validate headers match template ──────────────────────────────────────
    let headers: string[];
    try {
      headers = await readXlsxHeaders(file);
    } catch {
      toast.error(
        "Could not read the file. Make sure it is a valid .xlsx file.",
      );
      return;
    }

    const required = managed.templateColumns.map((c) => c.name);
    const missing = required.filter((col) => !headers.includes(col));
    const extra = headers.filter((h) => !required.includes(h));

    if (missing.length > 0) {
      toast.error(
        `Missing columns: ${missing.map((c) => `"${c}"`).join(", ")}. Check the template.`,
        { duration: 6000 },
      );
      return;
    }

    if (extra.length > 0) {
      // Warn but allow — extra columns won't break the scripts
      toast.warning(
        `Unexpected columns will be ignored: ${extra.map((c) => `"${c}"`).join(", ")}`,
        { duration: 5000 },
      );
    }

    // ── Upload ───────────────────────────────────────────────────────────────
    setUploading(true);
    const result = await uploadFile(file, managed.repoPath);
    setUploading(false);

    if (result.success) {
      toast.success(`${managed.label} updated successfully.`);
      loadInfo();
    } else {
      toast.error(result.message || "Upload failed.");
    }
  };

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void handleUpload(file);
    e.target.value = "";
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) void handleUpload(file);
  };

  const age = info ? staleness(info.last_updated_at) : "unknown";

  return (
    <>
      <TemplateDialog
        managed={managed}
        open={templateOpen}
        onClose={() => setTemplateOpen(false)}
      />

      <Card
        className="transition-all"
        style={
          dragOver
            ? { outline: "2px solid #38bdf8", outlineOffset: "2px" }
            : undefined
        }
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <div
              className="p-2 rounded-lg"
              style={{ backgroundColor: "#151f4a15", color: "#151f4a" }}
            >
              <FileSpreadsheet className="h-4 w-4" />
            </div>
            <div>
              <CardTitle
                className="text-sm font-semibold"
                style={{ color: "#151f4a" }}
              >
                {managed.label}
              </CardTitle>
              <code className="text-xs text-muted-foreground font-mono">
                {managed.repoPath}
              </code>
            </div>
          </div>
          <div className="flex items-center gap-2 mt-2">
            <Badge className={managed.clientColor} variant="outline">
              {managed.client}
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground gap-1"
              onClick={() => setTemplateOpen(true)}
            >
              <Info className="h-3 w-3" />
              View template
            </Button>
          </div>
          <CardDescription className="text-xs leading-relaxed mt-1">
            {managed.description}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-3">
          {/* Last updated info */}
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted text-xs">
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground shrink-0" />
            ) : age === "fresh" ? (
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
            ) : age === "stale" || age === "unknown" ? (
              <AlertCircle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            )}
            {loading ? (
              <span className="text-muted-foreground">Loading…</span>
            ) : (
              <div className="flex-1 min-w-0">
                <span className="font-medium text-foreground">
                  {formatRelativeDate(info?.last_updated_at ?? null)}
                </span>
                {info?.last_updated_by && (
                  <span className="text-muted-foreground">
                    {" "}
                    · {info.last_updated_by}
                  </span>
                )}
                {info?.last_updated_at && (
                  <div className="text-muted-foreground mt-0.5 truncate">
                    {formatFullDate(info.last_updated_at)}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Drop zone / upload button */}
          <div
            className={`border-2 border-dashed rounded-lg px-4 py-5 text-center cursor-pointer transition-colors ${dragOver
                ? "border-current bg-accent"
                : "border-border hover:border-muted-foreground/40 hover:bg-muted/40"
              }`}
            style={dragOver ? { borderColor: "#38bdf8" } : undefined}
            onClick={() => inputRef.current?.click()}
          >
            {uploading ? (
              <div className="flex flex-col items-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                <p className="text-xs text-muted-foreground">
                  Uploading to GitHub…
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-1.5">
                <Upload className="h-5 w-5 text-muted-foreground" />
                <p className="text-xs font-medium text-foreground">
                  Drop file here or{" "}
                  <span style={{ color: "#151f4a" }}>browse</span>
                </p>
                <p className="text-xs text-muted-foreground">
                  .xlsx files only · replaces {managed.filename}
                </p>
              </div>
            )}
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx,.xls"
              className="hidden"
              onChange={onInputChange}
            />
          </div>
        </CardContent>
      </Card>
    </>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────
export default function Files() {
  return (
    <div className="flex h-screen bg-background">
      <Sidebar />

      <main className="flex-1 overflow-auto">
        <div className="border-b border-border bg-card px-8 py-6">
          <h1 className="text-2xl font-bold" style={{ color: "#151f4a" }}>
            Files
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Upload updated data files used by automation scripts. Changes go
            directly to the GitHub repository.
          </p>
        </div>

        <div className="p-8 max-w-4xl">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {MANAGED_FILES.map((mf) => (
              <FileCard key={mf.repoPath} managed={mf} />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
