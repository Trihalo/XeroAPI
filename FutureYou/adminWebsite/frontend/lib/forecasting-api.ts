// API client for all forecasting endpoints

import { FC_AUTH } from "./forecasting-cache";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8081";

function authHeaders(): HeadersInit {
  const token = FC_AUTH.getToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface LoginResult {
  success: boolean;
  token?: string;
  role?: string;
  name?: string;
  revenue_table_last_modified_time?: string;
  error?: string;
}

export async function fcLogin(
  username: string,
  password: string,
): Promise<LoginResult> {
  const res = await fetch(`${API_BASE}/forecasting/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return res.json();
}

export async function fcChangePassword(
  username: string,
  oldPassword: string,
  newPassword: string,
): Promise<{ success: boolean; message?: string; error?: string }> {
  const res = await fetch(`${API_BASE}/forecasting/change-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, oldPassword, newPassword }),
  });
  return res.json();
}

// ── Invoices ──────────────────────────────────────────────────────────────────

export interface InvoiceRow {
  Consultant: string;
  Area: string;
  Week: number;
  Margin: number;
  FutureYouMonth: string;
  FinancialYear: string;
  Type: string;
  InvoiceNumber: string;
  ToClient?: string;
}

export async function fcFetchInvoices(
  fy: string,
  month: string,
): Promise<InvoiceRow[]> {
  const res = await fetch(
    `${API_BASE}/forecasting/invoices?fy=${fy}&month=${month}`,
    { headers: authHeaders() },
  );
  if (!res.ok) return [];
  return res.json();
}

// ── Forecasts ─────────────────────────────────────────────────────────────────

export interface ForecastRow {
  fy: string;
  month: string;
  week: number;
  range: string;
  revenue: number;
  tempRevenue: number;
  notes: string;
  name: string;
  uploadMonth: string;
  uploadWeek: number;
  uploadYear: string;
  uploadTimestamp: string;
  uploadUser: string;
}

export interface ForecastSummaryRow {
  name: string;
  week: number;
  total_revenue: number;
  uploadWeek: number;
}

export async function fcFetchForecastSummary(
  fy: string,
  month: string,
): Promise<ForecastSummaryRow[]> {
  const res = await fetch(
    `${API_BASE}/forecasting/forecasts/view?fy=${fy}&month=${month}`,
    { headers: authHeaders() },
  );
  if (!res.ok) return [];
  return res.json();
}

export async function fcFetchForecastWeekly(
  fy: string,
  month: string,
  uploadWeek: number,
): Promise<ForecastSummaryRow[]> {
  const res = await fetch(
    `${API_BASE}/forecasting/forecasts/weekly?fy=${fy}&month=${month}&uploadWeek=${uploadWeek}`,
    { headers: authHeaders() },
  );
  if (!res.ok) return [];
  return res.json();
}

export async function fcFetchForecastForRecruiter(
  recruiterName: string,
  fy: string,
  month: string,
  weeksInMonth: { week: number; range: string }[],
): Promise<ForecastRow[]> {
  const res = await fetch(
    `${API_BASE}/forecasting/forecasts/${encodeURIComponent(recruiterName)}?fy=${fy}&month=${month}`,
    { headers: authHeaders() },
  );

  const existing: ForecastRow[] = res.ok ? await res.json() : [];

  return weeksInMonth.map((entry) => {
    const match = existing.find((e) => String(e.week) === String(entry.week));
    return {
      fy,
      month,
      week: entry.week,
      range: entry.range,
      revenue: match?.revenue ?? 0,
      tempRevenue: match?.tempRevenue ?? 0,
      notes: match?.notes ?? "",
      name: recruiterName,
      uploadMonth: match?.uploadMonth ?? month,
      uploadWeek: match?.uploadWeek ?? 0,
      uploadYear: match?.uploadYear ?? fy,
      uploadTimestamp: match?.uploadTimestamp ?? "",
      uploadUser: match?.uploadUser ?? "",
    };
  });
}

export async function fcUploadForecast(
  rows: ForecastRow[],
): Promise<{ success: boolean; message?: string; error?: string }> {
  const name = FC_AUTH.getName() ?? "Unknown User";
  const enriched = rows.map((r) => ({ ...r, uploadUser: name }));
  const res = await fetch(`${API_BASE}/forecasting/forecasts`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ forecasts: enriched }),
  });
  return res.json();
}

// ── Monthly targets ───────────────────────────────────────────────────────────

export interface TargetRow {
  Month: string;
  Target: number;
  uploadTimestamp?: string;
  uploadUser?: string;
}

export async function fcFetchMonthlyTargets(fy: string): Promise<TargetRow[]> {
  const res = await fetch(
    `${API_BASE}/forecasting/monthly-targets?fy=${fy}`,
    { headers: authHeaders() },
  );
  if (!res.ok) return [];
  return res.json();
}

export async function fcSubmitMonthlyTarget(params: {
  fy: string;
  month: string;
  amount: number;
}): Promise<{ success: boolean; message?: string; error?: string }> {
  const uploadUser = FC_AUTH.getName() ?? "Unknown User";
  const res = await fetch(`${API_BASE}/forecasting/monthly-targets`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      FinancialYear: params.fy,
      Month: params.month,
      Target: params.amount,
      uploadUser,
      uploadTimestamp: new Date().toISOString(),
    }),
  });
  return res.json();
}

// ── Legends ───────────────────────────────────────────────────────────────────

export interface LegendsResponse {
  consultantTotals: { Consultant: string; Area: string; TotalMargin: number; Quarter: string }[];
  consultantTypeTotals: {
    Consultant: string;
    Area: string;
    Type: string;
    TotalMargin: number;
    Quarter: string;
    MonthName: string;
    Month: number;
  }[];
}

export async function fcFetchLegends(fy: string): Promise<LegendsResponse> {
  const res = await fetch(
    `${API_BASE}/forecasting/legends?fy=${fy}`,
    { headers: authHeaders() },
  );
  if (!res.ok) return { consultantTotals: [], consultantTypeTotals: [] };
  return res.json();
}

// ── Firestore ─────────────────────────────────────────────────────────────────

export interface Recruiter {
  id: string;
  name: string;
  area: string;
}

export interface Area {
  id: string;
  name: string;
  headcount: number;
}

export async function fcGetRecruiters(): Promise<Recruiter[]> {
  const res = await fetch(`${API_BASE}/forecasting/recruiters`, {
    headers: authHeaders(),
  });
  if (!res.ok) return [];
  return res.json();
}

export async function fcAddRecruiter(
  name: string,
  area: string,
): Promise<{ success: boolean; id?: string; error?: string }> {
  const res = await fetch(`${API_BASE}/forecasting/recruiters`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ name, area }),
  });
  return res.json();
}

export async function fcDeleteRecruiter(
  id: string,
): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/forecasting/recruiters/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return res.json();
}

export async function fcGetAreas(): Promise<Area[]> {
  const res = await fetch(`${API_BASE}/forecasting/areas`, {
    headers: authHeaders(),
  });
  if (!res.ok) return [];
  return res.json();
}

export async function fcUpdateHeadcount(
  id: string,
  headcount: number,
): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/forecasting/areas/${id}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify({ headcount }),
  });
  return res.json();
}
