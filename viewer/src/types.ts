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
  description?: string;
  schema: ContractSchema[];
}

export interface RecordsEnvelope {
  records: Record<string, unknown>[];
  format: "json" | "toon";
  limit: number;
  next_cursor: string | null;
}

export type ProvenanceSource =
  | "ai"
  | "import"
  | "python"
  | "sql"
  | "http"
  | "cross_sheet"
  | "human_override";

export interface ProvenanceEntry {
  record_id: string;
  field: string;
  source: ProvenanceSource;
  actor: string;
  at: string;
  input_hash?: string;
  cost_usd?: number | null;
  model?: string;
}

export interface TargetStatus {
  total_records?: number;
  with_provenance?: number;
  ai_count?: number;
  import_count?: number;
  human_count?: number;
  none_count?: number;
  human_override_count?: number;
  last_at?: string | null;
  last_actor?: string | null;
  derivation_kind?: string;
}

export interface MaterializeEnvelope {
  materialized: number;
  skipped: number;
  failures: Array<{
    record_id: string;
    field: string;
    error: string;
    error_type: string;
  }>;
  total_cost: number | null;
}

export interface QueryResult {
  rows: Record<string, unknown>[];
  count: number;
}

export interface FolioEvent {
  kind: string;
  ts: string;
  [key: string]: unknown;
}

export type ActivityKind =
  | "materialize.start"
  | "materialize.end"
  | "materialize.error"
  | "human_edit"
  | "query"
  | "delete"
  | "note";

export interface ActivityEntry {
  id: string;
  kind: ActivityKind;
  actor?: string;
  at: string;
  record_id?: string;
  field?: string;
  value?: unknown;
  prior?: unknown;
  sql?: string;
  text?: string;
  meta?: Record<string, unknown>;
}
