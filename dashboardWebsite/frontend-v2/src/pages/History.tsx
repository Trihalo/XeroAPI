import { useState, useEffect } from "react";
import { ChevronLeft, ChevronRight, FileText } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fetchSummaries, type SummaryEntry } from "@/api";

const PAGE_SIZE = 15;

const WORKFLOW_DISPLAY_NAMES: Record<string, string> = {
  "sendEmail.yml": "Send Email Test",
  "futureYouReports.yml": "FutureYou Reports",
  "h2cocoSupplierPayment.yml": "H2coco Supplier Payment",
  "h2cocoDraftInvoices.yml": "H2coco Invoice Approver",
  "futureYouInvoiceRevenue.yml": "FutureYou Revenue DB",
  "futureYouATB.yml": "FutureYou ATB DB",
  "flightRiskDraftInvoices.yml": "FlightRisk Invoice Approver",
  "flightRiskPrepaymentAllocator.yml": "FlightRisk Prepayment Allocator",
  "flightRiskAtb.yml": "FlightRisk ATB Updater",
  test: "Test Workflow",
};

const formatDate = (val: unknown): string => {
  if (!val) return "—";
  if (typeof val === "string") {
    return new Date(val).toLocaleString("en-AU", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  }
  if (typeof val === "object" && val !== null) {
    const ts = val as { _seconds?: number; seconds?: number };
    const s = ts._seconds ?? ts.seconds;
    if (s) return new Date(s * 1000).toLocaleString("en-AU", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  }
  return String(val);
};

// ── Markdown renderer ────────────────────────────────────────────────────────
function MarkdownRenderer({ md }: { md: string }) {
  const lines = md.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.startsWith("## ")) {
      elements.push(
        <h2 key={i} className="text-lg font-bold mt-2 mb-3" style={{ color: "#151f4a" }}>
          {line.slice(3)}
        </h2>,
      );
      i++;
    } else if (line.startsWith("### ")) {
      elements.push(
        <h3 key={i} className="text-sm font-semibold mt-4 mb-2 text-foreground">
          {line.slice(4)}
        </h3>,
      );
      i++;
    } else if (line.startsWith("| ")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].startsWith("| ")) {
        tableLines.push(lines[i]);
        i++;
      }
      if (tableLines.length >= 2) {
        const parseRow = (row: string) =>
          row.split("|").map((c) => c.trim()).filter((c) => c !== "" && c !== "---");
        const headers = parseRow(tableLines[0]);
        const dataRows = tableLines.slice(2).map(parseRow);
        elements.push(
          <div key={`table-${i}`} className="overflow-x-auto mb-3">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  {headers.map((h, j) => (
                    <th key={j} className="text-left px-3 py-2 font-semibold text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dataRows.map((row, j) => (
                  <tr key={j} className="border-b border-border/50 hover:bg-muted/20">
                    {row.map((cell, k) => (
                      <td key={k} className="px-3 py-2 text-foreground">{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>,
        );
      }
    } else if (line.startsWith("_") && line.endsWith("_") && line.length > 2) {
      elements.push(
        <p key={i} className="text-xs italic text-muted-foreground mb-2">{line.slice(1, -1)}</p>,
      );
      i++;
    } else if (line.trim() === "") {
      i++;
    } else {
      elements.push(
        <p key={i} className="text-xs text-foreground mb-1">{line}</p>,
      );
      i++;
    }
  }

  return <div className="font-sans">{elements}</div>;
}

// ── Component ────────────────────────────────────────────────────────────────
export default function History() {
  const [summaries, setSummaries] = useState<SummaryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [page, setPage] = useState(1);
  const [selectedSummary, setSelectedSummary] = useState<SummaryEntry | null>(null);

  useEffect(() => {
    fetchSummaries()
      .then((sums) => {
        setSummaries(sums);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, []);

  const totalPages = Math.max(1, Math.ceil(summaries.length / PAGE_SIZE));
  const pageStart = (page - 1) * PAGE_SIZE;
  const pageEnd = pageStart + PAGE_SIZE;
  const currentRows = summaries.slice(pageStart, pageEnd);

  return (
    <div className="flex h-screen bg-background">
      <Sidebar />

      <main className="flex-1 overflow-auto">
        <div className="border-b border-border bg-card px-8 py-6">
          <h1 className="text-2xl font-bold" style={{ color: "#151f4a" }}>History</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Recent workflow executions and their outcomes.
          </p>
        </div>

        <div className="p-8 max-w-6xl">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Workflow Runs</CardTitle>
                {!loading && !error && summaries.length > 0 && (
                  <span className="text-sm text-muted-foreground">
                    {summaries.length} total entries
                  </span>
                )}
              </div>
            </CardHeader>

            <CardContent className="p-0">
              {loading ? (
                <div className="flex items-center justify-center py-16">
                  <div className="relative h-8 w-8">
                    <div className="absolute inset-0 rounded-full border-2 border-primary/20" />
                    <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-primary animate-spin" />
                  </div>
                </div>
              ) : error ? (
                <div className="flex items-center justify-center py-16 text-sm text-muted-foreground">
                  Failed to load history. Check your connection.
                </div>
              ) : summaries.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 gap-2">
                  <p className="text-sm font-medium text-foreground">No history yet</p>
                  <p className="text-xs text-muted-foreground">Workflow executions will appear here.</p>
                </div>
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Workflow</TableHead>
                        <TableHead>Run</TableHead>
                        <TableHead>Date</TableHead>
                        <TableHead>Triggered By</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {currentRows.map((s, index) => {
                        const isScheduled = s.event_name === "schedule" || !s.event_name;
                        const triggeredBy = isScheduled
                          ? `Daily Schedule (${formatDate(s.stored_at)})`
                          : (s.triggered_by || "—");
                        const succeeded = s.job_status?.toLowerCase() === "success";
                        const hasFailed = s.job_status?.toLowerCase() === "failure";

                        return (
                        <TableRow key={pageStart + index}>
                          <TableCell className="font-medium">
                            {WORKFLOW_DISPLAY_NAMES[s.workflow_file] ?? s.workflow_file}
                          </TableCell>
                          <TableCell className="text-muted-foreground tabular-nums">
                            {s.run_number ? `#${s.run_number}` : "—"}
                          </TableCell>
                          <TableCell className="text-muted-foreground tabular-nums">
                            {formatDate(s.stored_at)}
                          </TableCell>
                          <TableCell className="text-muted-foreground text-sm">
                            {triggeredBy}
                          </TableCell>
                          <TableCell>
                            {s.job_status ? (
                              <Badge variant={succeeded ? "success" : hasFailed ? "destructive" : "secondary"}>
                                {succeeded ? "Success" : hasFailed ? "Failed" : s.job_status}
                              </Badge>
                            ) : null}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="outline"
                              size="sm"
                              className="gap-1.5 text-xs"
                              onClick={() => setSelectedSummary(s)}
                            >
                              <FileText className="h-3.5 w-3.5" />
                              Preview
                            </Button>
                          </TableCell>
                        </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>

                  {/* Pagination */}
                  <div className="flex items-center justify-between px-4 py-3 border-t border-border">
                    <p className="text-sm text-muted-foreground">
                      Showing {pageStart + 1}–{Math.min(pageEnd, summaries.length)} of {summaries.length}
                    </p>
                    <div className="flex items-center gap-1">
                      <Button variant="outline" size="icon" onClick={() => setPage((p) => p - 1)} disabled={page === 1}>
                        <ChevronLeft className="h-4 w-4" />
                      </Button>

                      {Array.from({ length: totalPages }, (_, i) => i + 1)
                        .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
                        .reduce<(number | "ellipsis")[]>((acc, p, idx, arr) => {
                          if (idx > 0 && p - (arr[idx - 1] as number) > 1) acc.push("ellipsis");
                          acc.push(p);
                          return acc;
                        }, [])
                        .map((item, idx) =>
                          item === "ellipsis" ? (
                            <span key={`ellipsis-${idx}`} className="px-2 text-muted-foreground text-sm">…</span>
                          ) : (
                            <Button
                              key={item}
                              variant={page === item ? "default" : "outline"}
                              size="icon"
                              onClick={() => setPage(item as number)}
                              className="h-9 w-9 text-sm"
                            >
                              {item}
                            </Button>
                          ),
                        )}

                      <Button variant="outline" size="icon" onClick={() => setPage((p) => p + 1)} disabled={page === totalPages}>
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </main>

      {/* ── Summary preview modal ── */}
      <Dialog open={!!selectedSummary} onOpenChange={(open) => { if (!open) setSelectedSummary(null); }}>
        <DialogContent className="max-w-6xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {selectedSummary
                ? `${WORKFLOW_DISPLAY_NAMES[selectedSummary.workflow_file] ?? selectedSummary.workflow_file}${selectedSummary.run_number ? ` — Run #${selectedSummary.run_number}` : ""}`
                : "Summary"}
            </DialogTitle>
          </DialogHeader>
          {selectedSummary && (
            <div className="mt-2">
              <MarkdownRenderer md={selectedSummary.summary.replace(/^##[^\n]*\n?/, "")} />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
