import type {
  Contract,
  MaterializeEnvelope,
  ProvenanceEntry,
  QueryResult,
  RecordsEnvelope,
  TargetStatus,
} from "./types";

let cachedCsrf: string | null = null;

async function csrfToken(): Promise<string> {
  if (cachedCsrf) return cachedCsrf;
  const response = await fetch("/api/csrf", { credentials: "include" });
  const body = await response.json();
  cachedCsrf = body.csrf_token as string;
  return cachedCsrf;
}

async function unwrapError(response: Response): Promise<never> {
  const body = await response.json().catch(() => null);
  const message =
    body?.error?.message ||
    `${response.status} ${response.statusText}`;
  throw new Error(message);
}

export async function getContract(): Promise<Contract> {
  const response = await fetch("/api/contract", { credentials: "include" });
  if (!response.ok) await unwrapError(response);
  return response.json();
}

export async function listRecords(params: {
  fields?: string[];
  limit?: number;
  cursor?: string;
  filter?: string;
} = {}): Promise<RecordsEnvelope> {
  const search = new URLSearchParams();
  if (params.fields?.length) search.set("fields", params.fields.join(","));
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.cursor) search.set("cursor", params.cursor);
  if (params.filter) search.set("filter", params.filter);
  const response = await fetch(`/api/records?${search.toString()}`, {
    credentials: "include",
  });
  if (!response.ok) await unwrapError(response);
  return response.json();
}

export async function upsertRecord(
  record: Record<string, unknown>,
  actor?: string,
): Promise<{ inserted: number; updated: number; total: number }> {
  const token = await csrfToken();
  const response = await fetch("/api/records", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": token,
    },
    body: JSON.stringify({ records: [record], actor }),
  });
  if (!response.ok) await unwrapError(response);
  return response.json();
}

export async function deleteRecords(
  ids: string[],
  actor?: string,
): Promise<{ deleted: number; remaining: number }> {
  const token = await csrfToken();
  const search = new URLSearchParams({ ids: ids.join(",") });
  const headers: Record<string, string> = { "X-CSRF-Token": token };
  if (actor) headers["X-Folio-Actor"] = actor;
  const response = await fetch(`/api/records?${search.toString()}`, {
    method: "DELETE",
    credentials: "include",
    headers,
  });
  if (!response.ok) await unwrapError(response);
  return response.json();
}

export async function runQuery(
  sql: string,
  params: unknown[] = [],
): Promise<QueryResult> {
  const response = await fetch("/api/query", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql, params }),
  });
  if (!response.ok) await unwrapError(response);
  return response.json();
}

export async function getProvenance(
  recordId: string,
  field: string,
): Promise<ProvenanceEntry | null> {
  const search = new URLSearchParams({ record_id: recordId, field });
  const response = await fetch(`/api/provenance?${search.toString()}`, {
    credentials: "include",
  });
  if (!response.ok) {
    if (response.status === 404) return null;
    await unwrapError(response);
  }
  const body = await response.json();
  return body == null ? null : body;
}

export async function getProvenanceHistory(
  recordId: string,
  field: string,
): Promise<ProvenanceEntry[]> {
  const search = new URLSearchParams({
    record_id: recordId,
    field,
    history: "true",
  });
  const response = await fetch(`/api/provenance?${search.toString()}`, {
    credentials: "include",
  });
  if (!response.ok) await unwrapError(response);
  return response.json();
}

export async function getStatus(): Promise<Record<string, TargetStatus>> {
  const response = await fetch("/api/status", { credentials: "include" });
  if (!response.ok) await unwrapError(response);
  return response.json();
}

export async function materializeAll(actor: string): Promise<MaterializeEnvelope> {
  const token = await csrfToken();
  const response = await fetch("/api/materialize", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": token,
    },
    body: JSON.stringify({ actor }),
  });
  if (!response.ok) await unwrapError(response);
  return response.json();
}
