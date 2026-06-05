"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { toast } from "sonner";
import { RefreshCw, Menu } from "lucide-react";
import { Toaster } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Sidebar from "@/components/Sidebar";
import { fcLogin } from "@/lib/forecasting-api";
import { FC_AUTH } from "@/lib/forecasting-cache";

// Which path prefixes each role can access
const ROLE_ROUTES: Record<string, string[]> = {
  finance:   ["/", "/annual-leave", "/talent-map", "/forecasting", "/forecasting/revenue", "/forecasting/admin", "/legends"],
  admin:     ["/", "/annual-leave", "/talent-map", "/forecasting", "/legends"],
  partner:   ["/", "/talent-map", "/forecasting", "/legends"],
  recruiter: ["/", "/talent-map", "/legends"],
};

// Where to send a user whose role can't access the page they landed on
const ROLE_DEFAULT: Record<string, string> = {
  finance:   "/",
  admin:     "/",
  partner:   "/talent-map",
  recruiter: "/talent-map",
};

function canAccess(role: string, pathname: string): boolean {
  if (pathname === "/forecasting/password") return true;
  const allowed = ROLE_ROUTES[role] ?? [];
  return allowed.some((r) => {
    if (r === "/") return pathname === "/";
    return pathname === r || pathname.startsWith(r + "/");
  });
}

function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.exp ? Date.now() / 1000 > payload.exp : false;
  } catch {
    return true;
  }
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  const [authState, setAuthState] = useState<
    "loading" | "unauthenticated" | "authenticated"
  >("loading");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    const token = FC_AUTH.getToken();
    if (!token || isTokenExpired(token)) {
      FC_AUTH.clear();
      setAuthState("unauthenticated");
      return;
    }

    const role = FC_AUTH.getRole() ?? "";
    const mustChange = FC_AUTH.getMustChangePassword();

    if (mustChange && pathname !== "/forecasting/password") {
      router.replace("/forecasting/password");
      setAuthState("authenticated");
      return;
    }

    if (!canAccess(role, pathname)) {
      router.replace(ROLE_DEFAULT[role] ?? "/");
      setAuthState("authenticated");
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
          result.must_change_password ?? false,
          username,
        );
        toast.success(`Welcome, ${result.name}`);
        if (result.must_change_password) {
          router.replace("/forecasting/password");
        }
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

  if (authState === "loading") {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-gray-50">
        <div className="w-6 h-6 rounded-full border-4 border-t-salmon border-navy/20 animate-spin" />
      </div>
    );
  }

  if (authState === "unauthenticated") {
    return (
      <div className="flex h-screen w-full">
        {/* Left panel */}
        <div className="hidden md:flex w-1/2 bg-navy flex-col items-center justify-center gap-8 px-12">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/fy.png"
            alt="FutureYou"
            className="w-64 object-contain brightness-0 invert"
          />
          <p className="text-white/50 text-sm text-center max-w-xs leading-relaxed">
            Internal tools portal for the FutureYou team.
          </p>
        </div>

        {/* Right panel */}
        <div className="flex flex-1 flex-col items-center justify-center bg-gray-50 px-8">
          {/* Mobile logo */}
          <div className="md:hidden mb-8">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/fy.png" alt="FutureYou" className="w-44 object-contain" />
          </div>

          <div className="w-full max-w-sm">
            <h1 className="text-2xl font-bold text-navy mb-1">Welcome back</h1>
            <p className="text-dark-grey text-sm mb-8">Sign in to your account to continue.</p>

            <form onSubmit={handleLogin} className="flex flex-col gap-5">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="shell-username" className="text-navy text-sm font-semibold">
                  Username
                </Label>
                <Input
                  id="shell-username"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => { setUsername(e.target.value); setLoginError(""); }}
                  placeholder="Enter your username"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="shell-password" className="text-navy text-sm font-semibold">
                  Password
                </Label>
                <Input
                  id="shell-password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setLoginError(""); }}
                  placeholder="Enter your password"
                />
              </div>

              {loginError && (
                <p className="text-sm text-salmon">{loginError}</p>
              )}

              <Button
                type="submit"
                disabled={!username || !password || loggingIn}
                className="bg-navy hover:bg-navy/90 text-white w-full mt-1"
              >
                {loggingIn ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  "Sign in"
                )}
              </Button>
            </form>

            <p className="mt-8 text-xs text-dark-grey text-center">
              Forgotten your password? Contact{" "}
              <a href="mailto:leoshi@future-you.com.au" className="text-navy font-semibold hover:underline">
                leoshi@future-you.com.au
              </a>
            </p>
          </div>
        </div>
        <Toaster position="top-right" richColors />
      </div>
    );
  }

  return (
    <>
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar — fixed overlay on mobile, inline on desktop */}
      <div
        className={`fixed inset-y-0 left-0 z-50 transition-transform duration-200 md:static md:z-auto md:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <Sidebar onClose={() => setSidebarOpen(false)} />
      </div>

      {/* Content column */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile header */}
        <header className="md:hidden flex items-center gap-3 px-4 py-3 bg-white border-b border-gray-200 shrink-0">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1 rounded-md text-navy hover:bg-gray-100"
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5" />
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/fy.png" alt="FutureYou" className="h-6 object-contain" />
        </header>

        <main className="flex-1 bg-gray-50 overflow-auto">{children}</main>
      </div>

      <Toaster position="top-right" richColors />
    </>
  );
}
