import { FC_AUTH } from "./forecasting-cache";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8081";

function authHeaders(): Record<string, string> {
  const token = FC_AUTH.getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function generateAnnualLeave(): Promise<string> {
  const res = await fetch(`${API_BASE}/annual-leave/generate`, {
    method: "POST",
    headers: authHeaders(),
  });
  const data = await res.json();
  if (!res.ok || data.error) {
    throw new Error(data.error ?? "Failed to generate report");
  }
  return data.html as string;
}

export async function generateTalentMap(
  file: File,
  client: string,
  jobTitle: string,
): Promise<Blob> {
  const form = new FormData();
  form.append("file", file);
  form.append("client", client);
  form.append("jobTitle", jobTitle);

  const res = await fetch(`${API_BASE}/talent-map/generate`, {
    method: "POST",
    body: form,
    headers: authHeaders(),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(
      (data as { error?: string }).error ?? "Failed to generate document",
    );
  }

  return res.blob();
}
