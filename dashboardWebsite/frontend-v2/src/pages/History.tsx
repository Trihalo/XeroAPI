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
import {
  fetchHistory,
  fetchSummaries,
  type HistoryEntry,
  type SummaryEntry,
} from "@/api";

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

const formatDate = (calledAt: unknown): string => {
  if (!calledAt) return "—";
  if (typeof calledAt === "string") {
    return new Date(calledAt).toLocaleString("en-AU", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  if (typeof calledAt === "object" && calledAt !== null) {
    const ts = calledAt as { _seconds?: number; seconds?: number };
    const seconds = ts._seconds ?? ts.seconds;
    if (seconds) {
      return new Date(seconds * 1000).toLocaleString("en-AU", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    }
  }
  return String(calledAt);
};

const parseName = (name: unknown): { name: string; email: string } => {
  if (!name) return { name: "—", email: "—" };
  if (typeof name === "string") return { name, email: "—" };
  if (typeof name === "object" && name !== null) {
    const n = name as { name?: string; email?: string };
    return { name: n.name ?? "—", email: n.email ?? "—" };
  }
  return { name: "—", email: "—" };
};

const isSuccess = (success: string | number): boolean => {
  if (typeof success === "number") return success === 200 || success === 204;
  return success.toLowerCase() === "success";
};

// ── Markdown renderer ────────────────────────────────────────────────────────
// Handles the exact format produced by write_github_summary():
//   ## Title, ### Section (N), | table |, _italic_
function MarkdownRenderer({ md }: { md: string }) {
  const lines = md.split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.startsWith("## ")) {
      elements.push(
        <h2
          key={i}
          className="text-lg font-bold mt-2 mb-3"
          style={{ color: "#151f4a" }}
        >
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
      // Collect consecutive table lines
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].startsWith("| ")) {
        tableLines.push(lines[i]);
        i++;
      }
      if (tableLines.length >= 2) {
        const parseRow = (row: string) =>
          row
            .split("|")
            .map((c) => c.trim())
            .filter((c) => c !== "" && c !== "---");
        const headers = parseRow(tableLines[0]);
        const dataRows = tableLines.slice(2).map(parseRow);
        elements.push(
          <div key={`table-${i}`} className="overflow-x-auto mb-3">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  {headers.map((h, j) => (
                    <th
                      key={j}
                      className="text-left px-3 py-2 font-semibold text-muted-foreground"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dataRows.map((row, j) => (
                  <tr
                    key={j}
                    className="border-b border-border/50 hover:bg-muted/20"
                  >
                    {row.map((cell, k) => (
                      <td key={k} className="px-3 py-2 text-foreground">
                        {cell}
                      </td>
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
        <p key={i} className="text-xs italic text-muted-foreground mb-2">
          {line.slice(1, -1)}
        </p>,
      );
      i++;
    } else if (line.trim() === "") {
      i++;
    } else {
      elements.push(
        <p key={i} className="text-xs text-foreground mb-1">
          {line}
        </p>,
      );
      i++;
    }
  }

  return <div className="font-sans">{elements}</div>;
}

// ── Component ────────────────────────────────────────────────────────────────
export default function History() {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [summaries, setSummaries] = useState<SummaryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [page, setPage] = useState(1);
  const [summaryPage, setSummaryPage] = useState(1);
  const [selectedSummary, setSelectedSummary] = useState<SummaryEntry | null>(
    null,
  );

  useEffect(() => {
    Promise.all([fetchHistory(), fetchSummaries()])
      .then(([hist, sums]) => {
        setHistory(hist);
        setSummaries(sums);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, []);

  const SUMMARY_PAGE_SIZE = 5;
  const summaryTotalPages = Math.max(1, Math.ceil(summaries.length / SUMMARY_PAGE_SIZE));
  const summaryStart = (summaryPage - 1) * SUMMARY_PAGE_SIZE;
  const currentSummaries = summaries.slice(summaryStart, summaryStart + SUMMARY_PAGE_SIZE);

  const totalPages = Math.max(1, Math.ceil(history.length / PAGE_SIZE));
  const pageStart = (page - 1) * PAGE_SIZE;
  const pageEnd = pageStart + PAGE_SIZE;
  const currentRows = history.slice(pageStart, pageEnd);

  return (
    <div className="flex h-screen bg-background">
      <Sidebar />

      <main className="flex-1 overflow-auto">
        <div className="border-b border-border bg-card px-8 py-6">
          <h1 className="text-2xl font-bold" style={{ color: "#151f4a" }}>
            History
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Recent workflow executions and their outcomes.
          </p>
        </div>

        <div className="p-8 max-w-6xl space-y-6">
          {/* ── Job Summaries ── */}
          {!loading && summaries.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>Job Summaries</CardTitle>
                  <span className="text-sm text-muted-foreground">
                    {summaries.length} recent run
                    {summaries.length !== 1 ? "s" : ""}
                  </span>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Workflow</TableHead>
                      <TableHead>Run</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {currentSummaries.map((s, i) => (
                      <TableRow key={i}>
                        <TableCell className="font-medium">
                          {WORKFLOW_DISPLAY_NAMES[s.workflow_file] ??
                            s.workflow_file}
                        </TableCell>
                        <TableCell className="text-muted-foreground tabular-nums">
                          {s.run_number ? `#${s.run_number}` : "—"}
                        </TableCell>
                        <TableCell className="text-muted-foreground tabular-nums">
                          {formatDate(s.stored_at)}
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
                    ))}
                  </TableBody>
                </Table>
                {summaryTotalPages > 1 && (
                  <div className="flex items-center justify-between px-4 py-3 border-t border-border">
                    <p className="text-sm text-muted-foreground">
                      Showing {summaryStart + 1}–{Math.min(summaryStart + SUMMARY_PAGE_SIZE, summaries.length)} of {summaries.length}
                    </p>
                    <div className="flex items-center gap-1">
                      <Button variant="outline" size="icon" onClick={() => setSummaryPage((p) => p - 1)} disabled={summaryPage === 1}>
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                      <Button variant="outline" size="icon" onClick={() => setSummaryPage((p) => p + 1)} disabled={summaryPage === summaryTotalPages}>
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* ── Trigger History ── */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Workflow Runs</CardTitle>
                {!loading && !error && history.length > 0 && (
                  <span className="text-sm text-muted-foreground">
                    {history.length} total entries
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
              ) : history.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 gap-2">
                  <p className="text-sm font-medium text-foreground">
                    No history yet
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Workflow executions will appear here.
                  </p>
                </div>
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Workflow</TableHead>
                        <TableHead>Called At</TableHead>
                        <TableHead>Name</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {currentRows.map((item, index) => {
                        const { name, email } = parseName(item.name);
                        const succeeded = isSuccess(item.success);
                        return (
                          <TableRow key={pageStart + index}>
                            <TableCell className="font-medium">
                              {WORKFLOW_DISPLAY_NAMES[item.workflow] ??
                                item.workflow}
                            </TableCell>
                            <TableCell className="text-muted-foreground tabular-nums">
                              {formatDate(item.called_at)}
                            </TableCell>
                            <TableCell>{name}</TableCell>
                            <TableCell className="text-muted-foreground">
                              {email}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant={succeeded ? "success" : "destructive"}
                              >
                                {succeeded ? "Success" : "Failed"}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>

                  {/* Pagination */}
                  <div className="flex items-center justify-between px-4 py-3 border-t border-border">
                    <p className="text-sm text-muted-foreground">
                      Showing {pageStart + 1}–
                      {Math.min(pageEnd, history.length)} of {history.length}
                    </p>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => setPage((p) => p - 1)}
                        disabled={page === 1}
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </Button>

                      {Array.from({ length: totalPages }, (_, i) => i + 1)
                        .filter(
                          (p) =>
                            p === 1 ||
                            p === totalPages ||
                            Math.abs(p - page) <= 1,
                        )
                        .reduce<(number | "ellipsis")[]>((acc, p, idx, arr) => {
                          if (idx > 0 && p - (arr[idx - 1] as number) > 1)
                            acc.push("ellipsis");
                          acc.push(p);
                          return acc;
                        }, [])
                        .map((item, idx) =>
                          item === "ellipsis" ? (
                            <span
                              key={`ellipsis-${idx}`}
                              className="px-2 text-muted-foreground text-sm"
                            >
                              …
                            </span>
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

                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => setPage((p) => p + 1)}
                        disabled={page === totalPages}
                      >
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
      <Dialog
        open={!!selectedSummary}
        onOpenChange={(open) => {
          if (!open) setSelectedSummary(null);
        }}
      >
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
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
