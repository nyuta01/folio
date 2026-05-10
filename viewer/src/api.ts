export type LogicalType =
  | "string"
  | "integer"
  | "number"
  | "boolean"
  | "date"
  | "timestamp"
  | "array"
  | "object";

export interface ContractProperty {
  name: string;
  logicalType: LogicalType;
  description?: string;
  primaryKey?: boolean;
  required?: boolean;
  ["x-derived"]?: boolean;
  ["x-inputs"]?: string[];
  ["x-editable-by"]?: string[];
}

export interface ContractSchema {
  name: string;
  physicalType: string;
  properties: ContractProperty[];
}

export interface Contract {
  apiVersion: string;
  kind: string;
  id: string;
  name: string;
  version: string;
  schema: ContractSchema[];
}

export interface RecordsEnvelope {
  records: Record<string, unknown>[];
  format: "json" | "toon";
  limit: number;
  next_cursor: string | null;
}

export interface ProvenanceEntry {
  record_id: string;
  field: string;
  source: "ai" | "import" | "human" | "sql" | "http" | "python" | "cross_sheet";
  actor: string;
  timestamp: string;
  input_hash?: string;
  cost_usd?: number | null;
  model?: string;
}

let cachedCsrf: string | null = null;

async function csrfToken(): Promise<string> {
  if (cachedCsrf) return cachedCsrf;
  const response = await fetch("/api/csrf", { credentials: "include" });
  const body = await response.json();
  cachedCsrf = body.csrf_token as string;
  return cachedCsrf;
}

export async function getContract(): Promise<Contract> {
  const response = await fetch("/api/contract", { credentials: "include" });
  if (!response.ok) throw new Error(`getContract: ${response.status}`);
  return response.json();
}

export async function listRecords(params: {
  fields?: string[];
  limit?: number;
  cursor?: string;
  filter?: string;
}): Promise<RecordsEnvelope> {
  const search = new URLSearchParams();
  if (params.fields?.length) search.set("fields", params.fields.join(","));
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.cursor) search.set("cursor", params.cursor);
  if (params.filter) search.set("filter", params.filter);
  const response = await fetch(`/api/records?${search.toString()}`, {
    credentials: "include",
  });
  if (!response.ok) throw new Error(`listRecords: ${response.status}`);
  return response.json();
}

export async function upsertRecord(record: Record<string, unknown>): Promise<void> {
  const token = await csrfToken();
  const response = await fetch("/api/records", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": token,
    },
    body: JSON.stringify({ records: [record] }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message || `upsertRecord: ${response.status}`);
  }
}

export async function getProvenance(
  recordId: string,
  field: string,
): Promise<ProvenanceEntry | null> {
  const search = new URLSearchParams({ record_id: recordId, field });
  const response = await fetch(`/api/provenance?${search.toString()}`, {
    credentials: "include",
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`getProvenance: ${response.status}`);
  return response.json();
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
  if (!response.ok) throw new Error(`getProvenanceHistory: ${response.status}`);
  return response.json();
}

export interface TargetStatus {
  ai_count?: number;
  import_count?: number;
  human_count?: number;
  none_count?: number;
  last_run?: string | null;
  derivation_kind?: string;
}

export async function getStatus(): Promise<Record<string, TargetStatus>> {
  const response = await fetch("/api/status", { credentials: "include" });
  if (!response.ok) throw new Error(`getStatus: ${response.status}`);
  return response.json();
}

export interface MaterializeEnvelope {
  materialized: number;
  skipped: number;
  failures: unknown[];
  total_cost: number | null;
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
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message || `materializeAll: ${response.status}`);
  }
  return response.json();
}
