"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { Lock, LogOut, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fcLogin } from "@/lib/forecasting-api";
import { FC_AUTH } from "@/lib/forecasting-cache";

// Pages that don't need the admin role
const ADMIN_ONLY_PATHS = ["/forecasting/revenue", "/forecasting/admin"];

export default function ForecastingLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  const [authState, setAuthState] = useState<"loading" | "unauthenticated" | "authenticated">(
    "loading",
  );

  // Form state
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState("");

  useEffect(() => {
    const token = FC_AUTH.getToken();
    if (!token) {
      setAuthState("unauthenticated");
      return;
    }
    // Check admin-only pages
    const role = FC_AUTH.getRole();
    if (ADMIN_ONLY_PATHS.some((p) => pathname.startsWith(p)) && role !== "admin") {
      router.replace("/forecasting");
      return;
    }
    setAuthState("authenticated");
  }, [pathname, router]);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoggingIn(true);
    setLoginError("");
    try {
      const result = await fcLogin(username, password);
      if (result.success && result.token && result.role && result.name) {
        FC_AUTH.setAuth(
          result.token,
          result.role,
          result.name,
          result.revenue_table_last_modified_time ?? "",
        );
        toast.success(`Welcome, ${result.name}`);
        setAuthState("authenticated");
      } else {
        setLoginError(result.error ?? "Login failed.");
      }
    } catch {
      setLoginError("Could not reach the server.");
    } finally {
      setLoggingIn(false);
    }
  }

  function handleLogout() {
    FC_AUTH.clear();
    setAuthState("unauthenticated");
    setUsername("");
    setPassword("");
    router.replace("/forecasting");
  }

  // ── Loading splash ────────────────────────────────────────────────────────
  if (authState === "loading") {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="w-6 h-6 rounded-full border-4 border-t-salmon border-navy/20 animate-spin" />
      </div>
    );
  }

  // ── Login gate ────────────────────────────────────────────────────────────
  if (authState === "unauthenticated") {
    return (
      <div className="flex flex-col h-full items-center justify-center p-6 bg-gray-50">
        <div className="w-full max-w-sm mb-6 bg-pink-50 border border-pink-200 text-pink-700 px-4 py-3 rounded-lg text-center font-medium text-sm shadow-sm">
          🚧 Undergoing testing at the moment, Please don't use.
        </div>
        <div className="bg-white rounded-2xl shadow-lg w-full max-w-sm overflow-hidden">
          {/* Header */}
          <div className="bg-navy px-6 py-5 flex items-center gap-3">
            <Lock className="w-4 h-4 text-salmon" />
            <span className="text-white font-semibold text-sm">Forecasting Login</span>
          </div>

          {/* Form */}
          <form onSubmit={handleLogin} className="px-6 py-6 flex flex-col gap-4">
            <p className="text-dark-grey text-sm">
              Sign in with your forecasting credentials to continue.
            </p>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="fc-username" className="text-navy text-sm font-semibold">
                Username
              </Label>
              <Input
                id="fc-username"
                autoComplete="username"
                value={username}
                onChange={(e) => { setUsername(e.target.value); setLoginError(""); }}
                placeholder="Enter username"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="fc-password" className="text-navy text-sm font-semibold">
                Password
              </Label>
              <Input
                id="fc-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setLoginError(""); }}
                placeholder="Enter password"
              />
            </div>

            {loginError && (
              <p className="text-sm text-salmon">{loginError}</p>
            )}

            <div className="flex gap-3 justify-between pt-1">
              <div className="flex-1" />
              <Button
                type="submit"
                disabled={!username || !password || loggingIn}
                className="bg-navy hover:bg-navy/90 text-white"
              >
                {loggingIn ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  "Sign in"
                )}
              </Button>
            </div>
          </form>
        </div>
        <div className="absolute bottom-6 text-center text-xs text-dark-grey">
          For any support issues or forgotten passwords, please contact{" "}
          <a href="mailto:leoshi@future-you.com.au" className="text-navy hover:underline font-semibold">
            leoshi@future-you.com.au
          </a>
        </div>
      </div>
    );
  }

  // ── Authenticated ─────────────────────────────────────────────────────────
  const isAdmin = FC_AUTH.getRole() === "admin";

  const navLinks = [
    { href: "/forecasting", label: "Forecasts", adminOnly: false },
    { href: "/forecasting/revenue", label: "Revenue Dashboard", adminOnly: true },
    { href: "/forecasting/admin", label: "Admin Panel", adminOnly: true },
    { href: "/forecasting/legends", label: "Legends Table", adminOnly: false },
  ].filter((l) => !l.adminOnly || isAdmin);

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="flex items-center justify-between px-8 py-3 border-b border-gray-200 bg-white shrink-0">
        <div className="flex items-center gap-5">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-semibold text-navy">{FC_AUTH.getName()}</span>
            {isAdmin && (
              <span className="text-xs bg-salmon/10 text-salmon font-semibold px-2 py-0.5 rounded-full">
                Admin
              </span>
            )}
          </div>
          <nav className="flex items-center gap-0.5 border-l border-gray-200 pl-5">
            {navLinks.map(({ href, label }) => {
              const active = href === "/forecasting"
                ? pathname === "/forecasting"
                : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${active
                    ? "bg-navy text-white"
                    : "text-dark-grey hover:bg-gray-100 hover:text-navy"
                    }`}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          {FC_AUTH.getLastModified() && (
            <span className="text-xs text-dark-grey hidden sm:block">
              Data updated: <b>{FC_AUTH.getLastModified()}</b>
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push("/forecasting/password")}
            className="text-dark-grey hover:text-navy"
          >
            Change password
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            className="text-dark-grey hover:text-navy gap-1.5"
          >
            <LogOut className="w-3.5 h-3.5" />
            Sign out
          </Button>
        </div>
      </div>

      {/* Page content */}
      <div className="flex-1 overflow-auto">{children}</div>
    </div>
  );
}
