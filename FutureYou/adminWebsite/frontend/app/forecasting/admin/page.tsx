"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Trash2, Save, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useRecruiterData } from "@/hooks/forecasting/useRecruiterData";
import {
  fcAddRecruiter,
  fcDeleteRecruiter,
  fcUpdateHeadcount,
  fcSubmitMonthlyTarget,
  fcFetchMonthlyTargets,
  type TargetRow,
} from "@/lib/forecasting-api";
import { FC_AUTH } from "@/lib/forecasting-cache";

const MONTHS = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"] as const;

interface ConfirmState {
  open: boolean;
  message: string;
  onConfirm: () => void;
}

export default function AdminPage() {
  const [refreshKey, setRefreshKey] = useState(0);
  const { recruiters, areas, loading, error } = useRecruiterData(refreshKey);

  // Recruiter management
  const [newName, setNewName] = useState("");
  const [newArea, setNewArea] = useState("");
  const [newTracking, setNewTracking] = useState("");
  const [areaEdits, setAreaEdits] = useState<Record<string, string>>({});

  // Monthly targets
  const [fy, setFy] = useState("FY26");
  const [month, setMonth] = useState<string>("Jul");
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [summaryByMonth, setSummaryByMonth] = useState<Record<string, number>>({});

  // Confirm dialog
  const [confirm, setConfirm] = useState<ConfirmState>({ open: false, message: "", onConfirm: () => { } });

  function ask(message: string, onConfirm: () => void) {
    setConfirm({ open: true, message, onConfirm });
  }

  useEffect(() => {
    fcFetchMonthlyTargets(fy).then((rows: TargetRow[]) => {
      const byMonth: Record<string, number> = {};
      rows.forEach((r) => { byMonth[r.Month] = r.Target; });
      setSummaryByMonth(byMonth);
    });
  }, [fy]);

  async function handleAddRecruiter() {
    if (!newName || !newArea) return;
    ask(`Add ${newName} to ${newArea}?`, async () => {
      const result = await fcAddRecruiter(newName, newArea, newTracking);
      if (result.success) {
        toast.success("Recruiter added.");
        setNewName("");
        setNewArea("");
        setNewTracking("");
        setRefreshKey((k) => k + 1);
      } else {
        toast.error(result.error ?? "Failed to add recruiter.");
      }
    });
  }

  async function handleDeleteRecruiter(id: string, name: string) {
    ask(`Delete ${name}?`, async () => {
      const result = await fcDeleteRecruiter(id);
      if (result.success) {
        toast.success("Recruiter deleted.");
        setRefreshKey((k) => k + 1);
      } else {
        toast.error("Failed to delete recruiter.");
      }
    });
  }

  async function handleSaveHeadcount(id: string, name: string) {
    const val = parseFloat(areaEdits[id] ?? "");
    if (isNaN(val)) return;
    ask(`Save headcount for "${name}"?`, async () => {
      const result = await fcUpdateHeadcount(id, val);
      if (result.success) {
        toast.success("Headcount updated.");
        setRefreshKey((k) => k + 1);
      } else {
        toast.error("Failed to update headcount.");
      }
    });
  }

  async function handleSubmitTarget() {
    setSubmitting(true);
    try {
      const result = await fcSubmitMonthlyTarget({ fy, month, amount: parseFloat(amount) });
      if (result.success) {
        toast.success("Monthly target submitted.");
        const rows = await fcFetchMonthlyTargets(fy);
        const byMonth: Record<string, number> = {};
        rows.forEach((r) => { byMonth[r.Month] = r.Target; });
        setSummaryByMonth(byMonth);
      } else {
        toast.error(result.error ?? "Failed to submit target.");
      }
    } catch {
      toast.error("Server error.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="p-6 md:p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-navy">Admin Panel</h1>
        <p className="text-dark-grey text-sm mt-0.5">Manage recruiters, areas, and monthly targets</p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="w-4 h-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="recruiters">
        <TabsList>
          <TabsTrigger value="recruiters">Recruiter Management</TabsTrigger>
          <TabsTrigger value="targets">Monthly Targets</TabsTrigger>
        </TabsList>

        {/* ── RECRUITER MANAGEMENT ────────────────────────────────────── */}
        <TabsContent value="recruiters" className="space-y-8 pt-4">
          {/* Add recruiter */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-navy">Add Recruiter</h3>
            <div className="flex flex-wrap gap-3 items-end">
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs text-dark-grey">Name</Label>
                <Input
                  placeholder="Full Name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-48"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs text-dark-grey">Tracking Name</Label>
                <Input
                  placeholder="e.g. SCB013 Sharon Callaghan"
                  value={newTracking}
                  onChange={(e) => setNewTracking(e.target.value)}
                  className="w-56"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs text-dark-grey">Area</Label>
                <div>
                  <Select value={newArea} onValueChange={(v) => v && setNewArea(v)}>
                    <SelectTrigger className="w-52">
                      <SelectValue placeholder="Select area" />
                    </SelectTrigger>
                    <SelectContent>
                      {areas.map((a) => (
                        <SelectItem key={a.id} value={a.name}>{a.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Button
                onClick={handleAddRecruiter}
                disabled={!newName || !newArea}
                className="bg-navy hover:bg-navy/90 text-white"
              >
                Add
              </Button>
            </div>
          </div>

          {/* Recruiter list */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-navy">Recruiters</h3>
            {loading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {[1, 2, 3, 4, 5, 6].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {recruiters.map((r) => (
                  <div
                    key={r.id}
                    className="flex items-center justify-between bg-gray-50 border border-gray-100 rounded-lg px-3 py-2.5"
                  >
                    <div>
                      <p className="text-sm font-medium text-navy">{r.name}</p>
                      <p className="text-xs text-dark-grey">{r.area}</p>
                      {r.xeroTrackingName && (
                        <p className="text-xs text-salmon font-medium mt-0.5" title="Xero Tracking Mapping">
                          {r.xeroTrackingName}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => handleDeleteRecruiter(r.id, r.name)}
                      className="text-gray-300 hover:text-salmon transition-colors"
                      aria-label={`Delete ${r.name}`}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Area headcounts */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-navy">Area Headcounts</h3>
            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-80" />)}
              </div>
            ) : (
              <ul className="space-y-2">
                {areas.map((a) => (
                  <li key={a.id} className="flex items-center gap-4">
                    <span className="text-sm text-navy w-52">{a.name}</span>
                    <Input
                      type="number"
                      className="w-24"
                      value={areaEdits[a.id] ?? a.headcount}
                      onChange={(e) => setAreaEdits((prev) => ({ ...prev, [a.id]: e.target.value }))}
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleSaveHeadcount(a.id, a.name)}
                      className="gap-1.5"
                    >
                      <Save className="w-3.5 h-3.5" /> Save
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </TabsContent>

        {/* ── MONTHLY TARGETS ──────────────────────────────────────────── */}
        <TabsContent value="targets" className="space-y-6 pt-4">
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-navy">Set Monthly Target</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-xl">
              <div className="space-y-1.5">
                <Label className="text-xs text-dark-grey">Financial Year</Label>
                <Select value={fy} onValueChange={(v) => v && setFy(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="FY25">FY25</SelectItem>
                    <SelectItem value="FY26">FY26</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs text-dark-grey">Month</Label>
                <Select value={month} onValueChange={(v) => v && setMonth(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {MONTHS.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs text-dark-grey">Target ($)</Label>
                <Input
                  type="number"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="e.g. 500000"
                />
              </div>
            </div>
            <Button
              onClick={handleSubmitTarget}
              disabled={submitting || !amount}
              className="bg-salmon hover:bg-salmon/90 text-white"
            >
              {submitting ? "Submitting…" : "Submit Target"}
            </Button>
          </div>

          {/* Targets table */}
          <div className="space-y-2 max-w-xs">
            <h3 className="text-sm font-semibold text-navy">Submitted Targets — {fy}</h3>
            <div className="rounded-lg border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="py-2.5 px-4 text-left font-semibold text-navy">Month</th>
                    <th className="py-2.5 px-4 text-right font-semibold text-navy">Target</th>
                  </tr>
                </thead>
                <tbody>
                  {MONTHS.map((m, idx) => (
                    <tr key={m} className={`border-b border-gray-50 ${idx % 2 === 0 ? "bg-white" : "bg-gray-50/50"}`}>
                      <td className="py-2 px-4 font-medium text-gray-900">{m}</td>
                      <td className="py-2 px-4 text-right text-gray-900 tabular-nums">
                        {summaryByMonth[m]
                          ? `$${(summaryByMonth[m] / 1000).toFixed(0)}K`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* Confirm dialog */}
      <Dialog open={confirm.open} onOpenChange={(open) => !open && setConfirm((c) => ({ ...c, open: false }))}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Confirm Action</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-dark-grey">{confirm.message}</p>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setConfirm((c) => ({ ...c, open: false }))}>
              Cancel
            </Button>
            <Button
              className="bg-salmon hover:bg-salmon/90 text-white"
              onClick={() => {
                setConfirm((c) => ({ ...c, open: false }));
                confirm.onConfirm();
              }}
            >
              Confirm
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
