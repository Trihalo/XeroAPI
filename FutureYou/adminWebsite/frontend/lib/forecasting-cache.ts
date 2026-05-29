// TTL-based localStorage cache for forecasting data

const CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour

interface CacheEntry<T> {
  data: T;
  fetchedAt: number;
}

export function getCached<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const entry: CacheEntry<T> = JSON.parse(raw);
    if (Date.now() - entry.fetchedAt > CACHE_TTL_MS) {
      localStorage.removeItem(key);
      return null;
    }
    return entry.data;
  } catch {
    return null;
  }
}

export function setCache<T>(key: string, data: T): void {
  if (typeof window === "undefined") return;
  try {
    const entry: CacheEntry<T> = { data, fetchedAt: Date.now() };
    localStorage.setItem(key, JSON.stringify(entry));
  } catch {
    // Storage quota exceeded — fail silently
  }
}

export function clearCache(key: string): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(key);
}

// Auth storage helpers
export const FC_AUTH = {
  getToken: (): string | null =>
    typeof window !== "undefined" ? localStorage.getItem("fc_token") : null,
  getRole: (): string | null =>
    typeof window !== "undefined" ? localStorage.getItem("fc_role") : null,
  getName: (): string | null =>
    typeof window !== "undefined" ? localStorage.getItem("fc_name") : null,
  getLastModified: (): string | null =>
    typeof window !== "undefined" ? localStorage.getItem("fc_last_modified") : null,
  getUsername: (): string | null =>
    typeof window !== "undefined" ? localStorage.getItem("fc_username") : null,
  getMustChangePassword: (): boolean =>
    typeof window !== "undefined"
      ? localStorage.getItem("fc_must_change_password") === "true"
      : false,
  setAuth: (
    token: string,
    role: string,
    name: string,
    lastModified: string,
    mustChangePassword = false,
    username = "",
  ): void => {
    if (typeof window === "undefined") return;
    localStorage.setItem("fc_token", token);
    localStorage.setItem("fc_role", role);
    localStorage.setItem("fc_name", name);
    localStorage.setItem("fc_last_modified", lastModified);
    localStorage.setItem("fc_username", username);
    localStorage.setItem(
      "fc_must_change_password",
      mustChangePassword ? "true" : "false",
    );
  },
  clearMustChangePassword: (): void => {
    if (typeof window === "undefined") return;
    localStorage.setItem("fc_must_change_password", "false");
  },
  clear: (): void => {
    if (typeof window === "undefined") return;
    [
      "fc_token",
      "fc_role",
      "fc_name",
      "fc_last_modified",
      "fc_must_change_password",
      "fc_username",
    ].forEach((k) => localStorage.removeItem(k));
  },
};

// Invoice cache keys
export const INVOICE_CACHE_KEY = "fc_invoice_current";
export const PREV_INVOICE_CACHE_KEY = "fc_invoice_prev";

// Legends cache key
export const LEGENDS_CACHE_KEY = "fc_legends";
