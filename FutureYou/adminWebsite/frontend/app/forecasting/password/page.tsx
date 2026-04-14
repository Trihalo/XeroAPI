"use client";

import { useState } from "react";
import { toast } from "sonner";
import { KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fcChangePassword } from "@/lib/forecasting-api";
import { FC_AUTH } from "@/lib/forecasting-cache";

export default function PasswordPage() {
  const name = FC_AUTH.getName() ?? "";

  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      toast.error("New passwords do not match.");
      return;
    }
    if (newPassword.length < 6) {
      toast.error("New password must be at least 6 characters.");
      return;
    }
    setSubmitting(true);
    try {
      const result = await fcChangePassword(name, oldPassword, newPassword);
      if (result.success) {
        toast.success("Password changed successfully.");
        setOldPassword("");
        setNewPassword("");
        setConfirmPassword("");
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
        <p className="text-dark-grey text-sm mt-0.5">Update your forecasting tool credentials</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 max-w-sm">
        <div className="space-y-1.5">
          <Label className="text-xs text-dark-grey">Username</Label>
          <Input value={name} disabled className="bg-gray-50 text-dark-grey" />
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs text-dark-grey">Current Password</Label>
          <Input
            type="password"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
            placeholder="Enter current password"
            required
          />
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs text-dark-grey">New Password</Label>
          <Input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Enter new password"
            required
          />
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs text-dark-grey">Confirm New Password</Label>
          <Input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Confirm new password"
            required
          />
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
