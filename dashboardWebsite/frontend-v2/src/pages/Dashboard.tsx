import { useState, useEffect } from "react";
import {
  FileText,
  Database,
  RefreshCw,
  CreditCard,
  FileCheck,
  Mail,
  Zap,
  ChevronRight,
  Clock,
  AlertCircle,
  CheckCircle2,
  XCircle,
  MinusCircle,
  Circle,
  Loader2,
  ExternalLink,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import Sidebar from "@/components/Sidebar";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  triggerWorkflow,
  uploadFile,
  authenticateUser,
  fetchRunStatus,
  type AuthUser,
  type WorkflowStep,
  type RunStatus,
} from "@/api";

type DialogStep = "info" | "auth" | "tracking";

interface Script {
  name: string;
  description: string;
  workflowKey: string;
  workflowFile: string;
  estimatedTime: number;
  requiresFileUpload: boolean;
  icon: React.ElementType;
}

interface ClientConfig {
  clientName: string;
  color: string;
  scripts: Script[];
}

const CLIENTS: ClientConfig[] = [
  {
    clientName: "FutureYou",
    color: "bg-violet-100 text-violet-700",
    scripts: [
      {
        name: "ATB & Overdue Files",
        description:
          "Generates an Aged Trial Balance report that includes both FutureYou Recruitment and Contracting Invoices.",
        workflowKey: "futureyou-reports",
        workflowFile: "futureYouReports.yml",
        estimatedTime: 240,
        requiresFileUpload: false,
        icon: FileText,
      },
      {
        name: "Update Revenue Database",
        description:
          "Updates the Invoice Revenue BigQuery Database by syncing invoices changed within the last 24 hours.",
        workflowKey: "futureyou-revenue-database",
        workflowFile: "futureYouInvoiceRevenue.yml",
        estimatedTime: 30,
        requiresFileUpload: false,
        icon: Database,
      },
      {
        name: "Update ATB Database",
        description:
          "Updates the ATB BigQuery Database, automatically refreshing the Master ATB file with the latest data.",
        workflowKey: "futureyou-atb-database",
        workflowFile: "futureYouATB.yml",
        estimatedTime: 120,
        requiresFileUpload: false,
        icon: RefreshCw,
      },
    ],
  },
  {
    clientName: "H2coco",
    color: "bg-cyan-100 text-cyan-700",
    scripts: [
      {
        name: "Supplier Payment Allocator",
        description:
          "Allocates supplier DPs to any approved bills in Xero. DP list is current as of the first day of the month.",
        workflowKey: "h2coco-supplier-payment",
        workflowFile: "h2cocoSupplierPayment.yml",
        estimatedTime: 30,
        requiresFileUpload: false,
        icon: CreditCard,
      },
      {
        name: "Draft Invoice Approver",
        description:
          "Approves draft invoices and stock journals in Xero for H2coco. Excludes Costco Australia invoices.",
        workflowKey: "h2coco-invoice-approver",
        workflowFile: "h2cocoDraftInvoices.yml",
        estimatedTime: 30,
        requiresFileUpload: false,
        icon: FileCheck,
      },
    ],
  },
  {
    clientName: "FlightRisk",
    color: "bg-pink-100 text-pink-700",
    scripts: [
      {
        name: "Draft Invoice Approver",
        description:
          "Approves draft invoices and stock journals in Xero for FlightRisk, with Unleashed sales order validation.",
        workflowKey: "flight-risk-invoice-approver",
        workflowFile: "flightRiskDraftInvoices.yml",
        estimatedTime: 60,
        requiresFileUpload: false,
        icon: FileCheck,
      },
      {
        name: "Customer Prepayment Allocator",
        description:
          "Allocates customer prepayments to approved AR invoices in Xero and sends a summary report to your email.",
        workflowKey: "flight-risk-prepayment-allocator",
        workflowFile: "flightRiskPrepaymentAllocator.yml",
        estimatedTime: 60,
        requiresFileUpload: false,
        icon: CreditCard,
      },
      {
        name: "ATB Updater",
        description:
          "Updates the Aged Trial Balance BigQuery database with the latest outstanding AR invoices from Xero.",
        workflowKey: "flight-risk-atb",
        workflowFile: "flightRiskAtb.yml",
        estimatedTime: 120,
        requiresFileUpload: false,
        icon: Database,
      },
    ],
  },
  {
    clientName: "Test",
    color: "bg-slate-100 text-slate-600",
    scripts: [
      {
        name: "Test Email Script",
        description:
          "Sends a test email to verify SMTP settings and connectivity.",
        workflowKey: "test-email",
        workflowFile: "sendEmail.yml",
        estimatedTime: 3,
        requiresFileUpload: false,
        icon: Mail,
      },
      {
        name: "Test API Script",
        description:
          "Tests the API connection with a sample request to verify the backend is reachable.",
        workflowKey: "test-api",
        workflowFile: "",
        estimatedTime: 2,
        requiresFileUpload: false,
        icon: Zap,
      },
    ],
  },
];

// ── Step status icon ────────────────────────────────────────────────────────
function StepIcon({ step }: { step: WorkflowStep }) {
  if (step.status === "completed") {
    if (step.conclusion === "success")
      return <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />;
    if (step.conclusion === "failure")
      return <XCircle className="h-4 w-4 text-red-500 shrink-0" />;
    if (step.conclusion === "skipped")
      return <MinusCircle className="h-4 w-4 text-muted-foreground shrink-0" />;
  }
  if (step.status === "in_progress")
    return <Loader2 className="h-4 w-4 text-primary animate-spin shrink-0" />;
  return <Circle className="h-4 w-4 text-muted-foreground/40 shrink-0" />;
}

function trackingLabel(
  status: RunStatus["status"],
  conclusion: RunStatus["conclusion"],
): string {
  if (status === "not_found") return "Waiting for GitHub to queue the run…";
  if (status === "queued") return "Queued — waiting for a runner…";
  if (status === "in_progress") return "Running on GitHub Actions…";
  if (status === "completed") {
    if (conclusion === "success") return "Completed successfully.";
    if (conclusion === "failure") return "Run failed.";
    if (conclusion === "cancelled") return "Run was cancelled.";
    return "Run finished.";
  }
  return "Connecting to GitHub…";
}

const formatEstimate = (s: number) =>
  s >= 60 ? `~${Math.round(s / 60)}m` : `~${s}s`;

// ── Component ───────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogStep, setDialogStep] = useState<DialogStep>("info");
  const [selectedScript, setSelectedScript] = useState<Script | null>(null);
  const [selectedClient, setSelectedClient] = useState("");
  const [selectedClientColor, setSelectedClientColor] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Live tracking
  const [dispatchedAt, setDispatchedAt] = useState("");
  const [trackingWorkflowFile, setTrackingWorkflowFile] = useState("");
  const [runStatus, setRunStatus] = useState<RunStatus | null>(null);

  // Poll GitHub every 4 seconds while tracking
  useEffect(() => {
    if (dialogStep !== "tracking" || !trackingWorkflowFile || !dispatchedAt)
      return;

    let stopped = false;

    const poll = async () => {
      if (stopped) return;
      try {
        const status = await fetchRunStatus(trackingWorkflowFile, dispatchedAt);
        if (stopped) return;
        setRunStatus(status);
        if (status.status === "completed") {
          stopped = true;
          setTimeout(() => {
            closeDialog();
            if (status.conclusion === "success") {
              toast.success(
                `${selectedScript?.name ?? "Script"} completed successfully!`,
              );
            } else {
              toast.error(
                `${selectedScript?.name ?? "Script"} ${status.conclusion ?? "failed"}.`,
              );
            }
          }, 1500); // brief pause so user sees the final state
        }
      } catch {
        // Ignore transient errors — next tick will retry
      }
    };

    poll();
    const interval = setInterval(poll, 4000);

    // Safety net: stop polling after 15 minutes
    const timeout = setTimeout(
      () => {
        if (stopped) return;
        stopped = true;
        clearInterval(interval);
        closeDialog();
        toast.error(
          "Workflow is taking longer than expected. Check GitHub Actions.",
        );
      },
      15 * 60 * 1000,
    );

    return () => {
      stopped = true;
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [dialogStep, trackingWorkflowFile, dispatchedAt, selectedScript]);

  // ── Handlers ──────────────────────────────────────────────────────────────
  const closeDialog = () => {
    setDialogOpen(false);
    setDialogStep("info"); // ensures polling useEffect cleans up immediately
  };

  const openDialog = (client: ClientConfig, script: Script) => {
    setSelectedClient(client.clientName);
    setSelectedClientColor(client.color);
    setSelectedScript(script);
    setDialogStep("info");
    setUsername("");
    setPassword("");
    setStatusMessage("");
    setUploadedFile(null);
    setRunStatus(null);
    setIsSubmitting(false);
    setDialogOpen(true);
  };

  const handleConfirm = async () => {
    if (!selectedScript || isSubmitting) return;

    if (selectedScript.requiresFileUpload && !uploadedFile) {
      setStatusMessage("Please upload the required file before continuing.");
      return;
    }

    setStatusMessage("");
    setIsSubmitting(true);

    try {
      const authResponse = await authenticateUser(username, password);
      if (!authResponse.success || !authResponse.user) {
        setStatusMessage("Invalid username or password. Please try again.");
        return;
      }

      const user: AuthUser = authResponse.user;

      if (selectedScript.requiresFileUpload && uploadedFile) {
        const uploadResponse = await uploadFile(uploadedFile);
        if (!uploadResponse.success) {
          setStatusMessage(uploadResponse.message);
          return;
        }
      }

      // Record timestamp BEFORE dispatching — GitHub creates the run during the API call,
      // so if we record it after, the run's creation time will be before our filter cutoff.
      // Subtract 2s as a small buffer for clock skew between client and GitHub.
      const dispatchedAt = new Date(Date.now() - 2000).toISOString();

      const result = await triggerWorkflow(selectedScript.workflowKey, user);
      if (!result.success) {
        closeDialog();
        toast.error(result.message || "Failed to trigger workflow.");
        return;
      }

      // No workflow file means no GitHub Action to track (e.g. test-api)
      if (!selectedScript.workflowFile) {
        closeDialog();
        toast.success(result.message || `${selectedScript.name} completed.`);
        return;
      }

      setDispatchedAt(dispatchedAt);
      setRunStatus(null);
      setTrackingWorkflowFile(selectedScript.workflowFile);
      setDialogStep("tracking");
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen bg-background">
      <Sidebar />

      <main className="flex-1 overflow-auto">
        <div className="border-b border-border bg-card px-8 py-6">
          <h1 className="text-2xl font-bold" style={{ color: "#151f4a" }}>
            Dashboard
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Trigger automation scripts for your clients.
          </p>
        </div>

        <div className="p-8 space-y-6 max-w-5xl">
          {CLIENTS.map((client) => (
            <Card key={client.clientName}>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Badge className={client.color} variant="outline">
                    {client.clientName}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {client.scripts.map((script) => {
                    const Icon = script.icon;
                    return (
                      <button
                        key={script.name}
                        onClick={() => openDialog(client, script)}
                        className="group flex flex-col gap-3 p-4 rounded-xl border border-border bg-card hover:shadow-md transition-all text-left"
                        style={{
                          ["--tw-hover-border-color" as string]: "#38bdf8",
                        }}
                        onMouseEnter={(e) =>
                          (e.currentTarget.style.borderColor = "#38bdf8")
                        }
                        onMouseLeave={(e) =>
                          (e.currentTarget.style.borderColor = "")
                        }
                      >
                        <div className="flex items-start justify-between">
                          <div
                            className="p-2 rounded-lg"
                            style={{
                              backgroundColor: "#151f4a15",
                              color: "#151f4a",
                            }}
                          >
                            <Icon className="h-4 w-4" />
                          </div>
                          <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity mt-0.5" />
                        </div>
                        <div>
                          <p className="font-medium text-sm text-foreground leading-tight">
                            {script.name}
                          </p>
                          <p className="text-xs text-muted-foreground mt-1 line-clamp-2 leading-relaxed">
                            {script.description}
                          </p>
                        </div>
                        <div className="flex items-center gap-1 text-xs text-muted-foreground">
                          <Clock className="h-3 w-3" />
                          <span>{formatEstimate(script.estimatedTime)}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </main>

      {/* ── Dialog ── */}
      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          if (!open) closeDialog();
        }}
      >
        <DialogContent className="sm:max-w-md">
          {/* Info */}
          {dialogStep === "info" && selectedScript && (
            <>
              <DialogHeader>
                <div className="flex items-center gap-2 mb-1">
                  <Badge className={selectedClientColor} variant="outline">
                    {selectedClient}
                  </Badge>
                </div>
                <DialogTitle>{selectedScript.name}</DialogTitle>
                <DialogDescription>
                  {selectedScript.description}
                </DialogDescription>
              </DialogHeader>
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted text-sm text-muted-foreground">
                <Clock className="h-4 w-4 shrink-0" />
                <span>
                  Estimated run time:{" "}
                  {formatEstimate(selectedScript.estimatedTime)}
                </span>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={closeDialog}>
                  Cancel
                </Button>
                <Button onClick={() => setDialogStep("auth")}>Execute</Button>
              </DialogFooter>
            </>
          )}

          {/* Auth */}
          {dialogStep === "auth" && selectedScript && (
            <>
              <DialogHeader>
                <DialogTitle>Confirm Identity</DialogTitle>
                <DialogDescription>
                  Enter your credentials to run{" "}
                  <strong>{selectedScript.name}</strong>.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                {selectedScript.requiresFileUpload && (
                  <div className="space-y-1.5">
                    <Label>Upload File (.xls, .xlsx)</Label>
                    <Input
                      type="file"
                      accept=".xls,.xlsx"
                      onChange={(e) =>
                        setUploadedFile(e.target.files?.[0] ?? null)
                      }
                    />
                  </div>
                )}
                <div className="space-y-1.5">
                  <Label htmlFor="username">Username</Label>
                  <Input
                    id="username"
                    type="text"
                    placeholder="Enter your username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    autoComplete="username"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                    onKeyDown={(e) => e.key === "Enter" && void handleConfirm()}
                  />
                </div>
                {statusMessage && (
                  <div className="flex items-start gap-2 px-3 py-2 rounded-lg bg-red-50 text-red-700 text-sm">
                    <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                    <span>{statusMessage}</span>
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setDialogStep("info")}
                  disabled={isSubmitting}
                >
                  Back
                </Button>
                <Button
                  onClick={() => void handleConfirm()}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Running…
                    </>
                  ) : (
                    "Run Script"
                  )}
                </Button>
              </DialogFooter>
            </>
          )}

          {/* Live tracking */}
          {dialogStep === "tracking" && selectedScript && (
            <>
              <DialogHeader>
                <DialogTitle>{selectedScript.name}</DialogTitle>
                <DialogDescription>
                  {runStatus
                    ? trackingLabel(
                        runStatus.status,
                        runStatus.conclusion ?? null,
                      )
                    : "Dispatching workflow to GitHub…"}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-3">
                {runStatus && runStatus.steps.length > 0 ? (
                  <div className="rounded-lg border border-border divide-y divide-border overflow-hidden">
                    {runStatus.steps.map((step, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-3 px-3 py-2.5"
                      >
                        <StepIcon step={step} />
                        <span
                          className={cn(
                            "text-sm flex-1",
                            step.status === "queued"
                              ? "text-muted-foreground"
                              : "text-foreground",
                          )}
                        >
                          {step.name}
                        </span>
                        {step.status === "in_progress" && (
                          <span className="text-xs text-primary font-medium">
                            Running
                          </span>
                        )}
                        {step.status === "completed" &&
                          step.conclusion === "failure" && (
                            <span className="text-xs text-red-600 font-medium">
                              Failed
                            </span>
                          )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
                    <div className="h-4 w-4 rounded-full border-2 border-primary/30 border-t-primary animate-spin shrink-0" />
                    <span className="text-sm text-muted-foreground">
                      {!runStatus || runStatus.status === "not_found"
                        ? "Waiting for GitHub to create the run…"
                        : "Waiting for a runner to pick up the job…"}
                    </span>
                  </div>
                )}

                {runStatus?.html_url && (
                  <a
                    href={runStatus.html_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
                  >
                    <ExternalLink className="h-3 w-3" />
                    View full run on GitHub
                  </a>
                )}

                <p className="text-xs text-muted-foreground">
                  The workflow will continue running on GitHub even if you close
                  this window.
                </p>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
