"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { KeyRound, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fcChangePassword } from "@/lib/forecasting-api";
import { FC_AUTH } from "@/lib/forecasting-cache";

export default function PasswordPage() {
  const router = useRouter();
  const name = FC_AUTH.getName() ?? "";
  const mustChange = FC_AUTH.getMustChangePassword();

  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showOld, setShowOld] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      toast.error("New passwords do not match.");
      return;
    }
    if (newPassword === oldPassword) {
      toast.error("New password must be different from your current password.");
      return;
    }
    if (newPassword.length < 6) {
      toast.error("New password must be at least 6 characters.");
      return;
    }
    setSubmitting(true);
    try {
      const result = await fcChangePassword(oldPassword, newPassword);
      if (result.success) {
        FC_AUTH.clearMustChangePassword();
        toast.success("Password changed successfully.");
        setOldPassword("");
        setNewPassword("");
        setConfirmPassword("");
        // Redirect to home after a brief moment
        setTimeout(() => router.push("/"), 1200);
      } else {
        toast.error(result.error ?? "Failed to change password.");
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
        <h1 className="text-2xl font-bold text-navy">Change Password</h1>
        <p className="text-dark-grey text-sm mt-0.5">
          {mustChange
            ? "You must set a new password before continuing."
            : "Update your admin credentials"}
        </p>
      </div>

      {mustChange && (
        <div className="max-w-sm rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Your account is using a default password. Please set a new password to
          continue.
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4 max-w-sm">
        <div className="space-y-1.5">
          <Label className="text-xs text-dark-grey">Username</Label>
          <Input value={name} disabled className="bg-gray-50 text-dark-grey" />
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs text-dark-grey">Current Password</Label>
          <div className="relative">
            <Input
              type={showOld ? "text" : "password"}
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              placeholder="Enter current password"
              required
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShowOld((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-grey hover:text-navy"
              tabIndex={-1}
            >
              {showOld ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs text-dark-grey">New Password</Label>
          <div className="relative">
            <Input
              type={showNew ? "text" : "password"}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Enter new password"
              required
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShowNew((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-grey hover:text-navy"
              tabIndex={-1}
            >
              {showNew ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs text-dark-grey">Confirm New Password</Label>
          <div className="relative">
            <Input
              type={showConfirm ? "text" : "password"}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm new password"
              required
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShowConfirm((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-grey hover:text-navy"
              tabIndex={-1}
            >
              {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <Button
          type="submit"
          disabled={submitting || !oldPassword || !newPassword || !confirmPassword}
          className="bg-navy hover:bg-navy/90 text-white gap-2"
        >
          <KeyRound className="w-4 h-4" />
          {submitting ? "Updating…" : "Update Password"}
        </Button>
      </form>
    </div>
  );
}
