/* =========================================================
   AEGISTWIN API
   ========================================================= */

export const API_BASE = "http://127.0.0.1:8000";

/* =========================================================
   SHARED
   ========================================================= */

export type RiskLevel =
  | "LOW"
  | "MEDIUM"
  | "HIGH"
  | "CRITICAL";

export type DecisionAction =
  | "ALLOW"
  | "BLOCK"
  | "REDACT"
  | "REQUIRE_APPROVAL";

export type ApiRole =
  | "viewer"
  | "security"
  | "admin";

/* =========================================================
   API KEY STORAGE
   ========================================================= */

const API_KEY_STORAGE = {
  viewer: "aegistwin.viewerApiKey",
  security: "aegistwin.securityApiKey",
  admin: "aegistwin.adminApiKey",
} satisfies Record<ApiRole, string>;

export function setApiKey(
  role: ApiRole,
  key: string,
): void {
  if (typeof window === "undefined") return;

  const trimmed = key.trim();

  if (!trimmed) {
    sessionStorage.removeItem(
      API_KEY_STORAGE[role],
    );
    return;
  }

  sessionStorage.setItem(
    API_KEY_STORAGE[role],
    trimmed,
  );
}

export function getApiKey(
  role: ApiRole,
): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  return (
    sessionStorage.getItem(
      API_KEY_STORAGE[role],
    ) ?? null
  );
}

export function clearApiKey(
  role?: ApiRole,
): void {
  if (typeof window === "undefined") return;

  if (role) {
    sessionStorage.removeItem(
      API_KEY_STORAGE[role],
    );
    return;
  }

  Object.values(API_KEY_STORAGE).forEach(
    (key) => sessionStorage.removeItem(key),
  );
}

/* =========================================================
   HEADERS
   ========================================================= */

function authHeaders(
  role?: ApiRole,
  keyOverride?: string,
): HeadersInit {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };

  if (!role) return headers;

  const key =
    keyOverride?.trim() ||
    getApiKey(role);

  if (key) {
    headers["X-API-Key"] = key;
  }

  return headers;
}

function jsonHeaders(
  role?: ApiRole,
  keyOverride?: string,
): HeadersInit {
  return {
    ...authHeaders(role, keyOverride),
    "Content-Type": "application/json",
  };
}

/* =========================================================
   DIGITAL TWIN TYPES
   ========================================================= */

export interface ToolProfile {
  tool_name: string;
  version: string;
  declared_effects: string[];
  observed_effects: string[];
  capabilities: string[];
  risk_level: RiskLevel;
  behavioral_mismatch: boolean;
  fingerprint: string;
}

export interface CapabilityFlags {
  sensitive_data_access: boolean;
  external_communication: boolean;
  financial_modification: boolean;
  credential_access_or_creation: boolean;
  destructive_action: boolean;
  code_execution: boolean;
  filesystem_access: boolean;
  database_access: boolean;
}

export interface CapabilityTool {
  tool_name: string;
  version: string;
  risk_level: RiskLevel;
  behavioral_mismatch: boolean;
  fingerprint: string;
  declared_effects: string[];
  observed_effects: string[];
  capabilities: string[];
  capability_flags: CapabilityFlags;
}

export interface CapabilitySummary {
  total_tools: number;
  critical_tools: number;
  high_risk_tools: number;
  behavioral_mismatches: number;
  external_communication_tools: number;
  sensitive_data_tools: number;
}

export interface CapabilityMap {
  summary: CapabilitySummary;
  tools: CapabilityTool[];
}

export interface TwinGraphNode {
  id: string;
  type: string;
  name?: string;
  version?: string;
  tool_name?: string;
  call_id?: string;
  session_id?: string;
  arguments?: Record<string, unknown>;
  instruction_origin?: string;
  original_user_intent?: string;
  timestamp?: string;
  origin?: string;
  intent?: string;
  artifact_id?: string;
  labels?: string[];
  parent_artifact_ids?: string[];
  transformation?: string;
  declared_effects?: string[];
  observed_effects?: string[];
  capabilities?: string[];
  risk_level?: RiskLevel;
  behavioral_mismatch?: boolean;
  fingerprint?: string;
}

export interface TwinGraphEdge {
  source: string;
  target: string;
  relation: string;
}

export interface TwinGraphData {
  nodes: TwinGraphNode[];
  edges: TwinGraphEdge[];
}

export interface ProvenanceChain {
  call_count: number;
  origins: string[];
  effective_origin: string;
  contains_untrusted_content: boolean;
  can_authorize_sensitive_action: boolean;
  risk_level: RiskLevel;
}

export interface ProvenanceCall {
  call_id: string;
  session_id: string;
  tool_name: string;
  original_user_intent: string;
  instruction_origin: string;
  trusted: boolean;
  can_authorize_sensitive_action: boolean;
  requested_effect: string;
  risk_level: RiskLevel;
}

export interface ProvenanceAnalysis {
  chain: ProvenanceChain;
  calls: ProvenanceCall[];
}

export interface IntentAction {
  original_intent: string;
  final_effect: string;
  destination: string | null;
  aligned: boolean;
  risk_level: RiskLevel;
  reason: string;
}

export interface LineageArtifact {
  artifact_id: string;
  value: unknown;
  labels: string[];
  parent_artifact_ids: string[];
  transformation: string;
}

export interface LineageAnalysis {
  sensitive_labels: string[];
  sensitive_artifact_ids: string[];
  traces: Record<string, string[]>;
  artifacts: LineageArtifact[];
}

export interface AttackPath {
  attack_id: string;
  original_intent: string;
  instruction_origin: string;
  path: string[];
  final_effect: string;
  source_labels: string[];
  destination: string;
  risk_level: RiskLevel;
  reproducible: boolean;
  evidence_receipt_ids: string[];
}

export interface LeastPrivilegeRecommendation {
  tool_name: string;
  current_capabilities: string[];
  required_capabilities: string[];
  removable_capabilities: string[];
  missing_capabilities: string[];
  legitimate_effects: string[];
  least_privilege_satisfied: boolean;
  reduction_percent: number;
}

export interface LeastPrivilegeAnalysis {
  summary: {
    total_tools: number;
    tools_with_excess_privilege: number;
    total_removable_capabilities: number;
  };

  recommendations:
    LeastPrivilegeRecommendation[];
}

export interface DriftAnalysis {
  available: boolean;
  reason: string | null;
  report: unknown;
}

export interface TwinAnalysis {
  tool_profiles: ToolProfile[];
  capability_map: CapabilityMap;
  graph: TwinGraphData;
  provenance: ProvenanceAnalysis;
  intent_action: IntentAction[];
  lineage: LineageAnalysis;
  attack_paths: AttackPath[];
  least_privilege: LeastPrivilegeAnalysis;
  drift: DriftAnalysis;
}

/* =========================================================
   GUARDRAIL / BENCHMARK
   ========================================================= */

export interface GeneratedGuardrail {
  guardrail_id: string;
  source_labels: string[];
  destination: string;
  action: DecisionAction;
  generated_from_attack: string;
  reason: string;
  enabled: boolean;
}

export interface BenchmarkMetrics {
  asr: number;
  utility: number;
  false_positive_rate: number;
  friction: number;
  latency_per_decision_ms: number;
  successful_attacks: number;
  attack_cases: number;
  allowed_legitimate_tasks: number;
  blocked_legitimate_tasks: number;
  legitimate_cases: number;
  approval_cases: number;
  total_cases: number;
  total_decisions: number;
}

export interface BenchmarkCase {
  phase: "before" | "after";
  scenario: "malicious" | "legitimate";
  workflow_success: boolean;
  allowed: boolean;
  blocked: boolean;
  attack_success: boolean;
  requires_human_approval: boolean;
  decision_count: number;
  elapsed_ms: number;
  latency_per_decision_ms: number;
}

export interface BenchmarkReport {
  before_metrics: BenchmarkMetrics;
  after_metrics: BenchmarkMetrics;

  absolute_improvement: {
    asr_reduction: number;
    utility_gain: number;
    false_positive_reduction: number;
    friction_reduction: number;
    added_latency_per_decision_ms: number;
  };

  cases: BenchmarkCase[];
  regression_suite_passed: boolean;
  guardrail: GeneratedGuardrail;
}

export interface AttackResponse {
  benchmark_report: BenchmarkReport;

  asr_before: number;
  asr_after: number;

  utility_before: number;
  utility_after: number;

  false_positive_rate: {
    before: number;
    after: number;
  };

  friction: {
    before: number;
    after: number;
  };

  measured_latency: {
    before_ms_per_decision: number;
    after_ms_per_decision: number;
    added_ms_per_decision: number;
  };

  regression_passed: boolean;

  twin_analysis: TwinAnalysis;

  generated_guardrail?: GeneratedGuardrail;

  attack_path?: string[];

  attack_path_details?: AttackPath;

  summary?: {
    attack_before?: string;
    attack_after?: string;
    legitimate_task?: string;
    [key: string]: string | undefined;
  };

  original_user_intent?: string;
  instruction_origin?: string;
  sensitive_lineage?: string[];

  before?: unknown;
  after?: unknown;
  legitimate_workflow?: unknown;

  [key: string]: unknown;
}

/* =========================================================
   HEALTH
   ========================================================= */

export interface HealthResponse {
  status?: string;
  service?: string;
  version?: string;

  [key: string]: unknown;
}

/* =========================================================
   REAL POLICY CONTRACT
   ========================================================= */

export interface PolicyControlConfig {
  tool_allow_list: boolean;
  semantic_detection: boolean;
  composition_analysis: boolean;
  deterministic_policy: boolean;
  data_lineage: boolean;
  human_approval: boolean;
  budget_enforcement: boolean;
  historical_attack_detection: boolean;
}

export interface PolicyBudgetConfig {
  max_tool_calls_per_session: number;
  max_external_http_calls_per_session: number;
  max_estimated_cost_per_session: number;
  max_agent_turns_per_session: number;
  max_input_tokens_per_session: number;
  max_output_tokens_per_session: number;
  max_execution_duration_ms_per_session: number;
  max_model_runtime_ms_per_session: number;
}

export interface PolicyResponse {
  status: string;
  source: string;

  policy: {
    version: string;

    controls: PolicyControlConfig;

    tools: {
      allowed: string[];
    };

    models: {
      allowed: string[];
      semantic_threshold: number;
    };

    data: {
      sensitive_labels: string[];
      external_destinations: string[];
    };

    budgets: PolicyBudgetConfig;

    actions: {
      sensitive_external_data:
        | DecisionAction
        | string;

      unknown_tool:
        | DecisionAction
        | string;

      unknown_model:
        | DecisionAction
        | string;

      historical_exploit:
        | DecisionAction
        | string;
    };

    historical_attack_signatures:
      string[];

    organization_ceilings: {
      permanently_blocked_data_labels:
        string[];

      permanently_blocked_destinations:
        string[];

      maximum_tool_calls_per_session:
        number;

      maximum_external_http_calls_per_session:
        number;

      maximum_estimated_cost_per_session:
        number;

      maximum_agent_turns_per_session:
        number;

      maximum_input_tokens_per_session:
        number;

      maximum_output_tokens_per_session:
        number;

      maximum_execution_duration_ms_per_session:
        number;

      maximum_model_runtime_ms_per_session:
        number;
    };
  };

  enforcement: {
    organization_ceilings: string;
    validation: string;
    load_time: string;
  };

  reload_mode: string;
  hot_reload: boolean;
  reload_count: number;

  last_reloaded_at:
    | string
    | null;

  /*
   * Compatibility aliases for older components.
   */
  version?: string;
  policy_version?: string;

  [key: string]: unknown;
}

export interface PolicyReloadResponse {
  success?: boolean;
  version?: string;
  policy_version?: string;
  message?: string;

  [key: string]: unknown;
}

/* =========================================================
   REAL CAPABILITIES CONTRACT
   ========================================================= */

export interface CapabilityControlState {
  enabled: boolean;
  type: string;

  threshold?: number;

  max_tool_calls_per_session?: number;

  max_external_http_calls_per_session?: number;

  max_estimated_cost_per_session?: number;

  max_agent_turns_per_session?: number;

  max_input_tokens_per_session?: number;

  max_output_tokens_per_session?: number;

  max_execution_duration_ms_per_session?: number;

  max_model_runtime_ms_per_session?: number;

  [key: string]: unknown;
}

export interface CapabilitiesResponse {
  architecture: string;

  gateway_mode: string;

  composition_enforcement: boolean;

  policy_source: string;

  policy_version: string;

  persistence: {
    enabled: boolean;
    backend: string;
  };

  controls: Record<
    string,
    CapabilityControlState
  >;

  decision_actions:
    DecisionAction[];

  [key: string]: unknown;
}

/* =========================================================
   GATEWAY REQUEST
   ========================================================= */

export interface GatewayToolCall {
  call_id: string;

  session_id: string;

  tool_name: string;

  arguments?: Record<
    string,
    unknown
  >;

  instruction_origin: string;

  original_user_intent: string;

  model_name?:
    | string
    | null;

  timestamp?: string;
}

export interface GatewayDataArtifact {
  artifact_id: string;

  value: unknown;

  labels?: string[];

  parent_artifact_ids?: string[];

  transformation?:
    | string
    | null;
}

export interface GatewayEvaluateRequest {
  call: GatewayToolCall;

  input_artifacts?:
    GatewayDataArtifact[];

  approval_id?:
    | string
    | null;

  estimated_cost?: number;
}

/* =========================================================
   REAL GATEWAY RESPONSE
   ========================================================= */

export interface GatewayDecision {
  decision_id: string;
  call_id: string;
  action: DecisionAction;
  reason: string;

  matched_guardrail_id:
    | string
    | null;

  risk_level:
    | RiskLevel
    | string;
}

export interface GatewayReceipt {
  receipt_id?: string;
  call_id?: string;
  session_id?: string;
  tool_name?: string;
  timestamp?: string;

  [key: string]: unknown;
}

export interface GatewaySession {
  session_id: string;

  receipt_count?: number;
  decision_count?: number;

  tool_sequence?: string[];
  instruction_origins?: string[];
  data_labels?: string[];

  receipt_ids?: string[];
  decision_ids?: string[];

  metadata?: Record<
    string,
    unknown
  >;

  [key: string]: unknown;
}

export interface GatewayEvaluateResponse {
  decision: GatewayDecision;

  executed: boolean;

  receipt:
    | GatewayReceipt
    | null;

  session: GatewaySession;

  composition_analysis:
    | unknown
    | null;

  policy_version: string;

  control_path: string[];

  [key: string]: unknown;
}

/* =========================================================
   EXTENDED BENCHMARK
   ========================================================= */

export interface ExtendedBenchmarkResponse {
  scenario_count?: number;
  attack_cases?: number;
  legitimate_cases?: number;
  security_categories?: number;
  results?: unknown[];
  metrics?: unknown;

  [key: string]: unknown;
}

/* =========================================================
   BUDGET TYPES
   ========================================================= */

export interface BudgetDimension {
  used?: number;
  limit?: number;
  remaining?: number;
  unit?: string;

  [key: string]: unknown;
}

export interface ExtendedSessionBudget {
  tool_calls?:
    | number
    | BudgetDimension;

  external_http_calls?:
    | number
    | BudgetDimension;

  estimated_cost?:
    | number
    | BudgetDimension;

  agent_turns?:
    | number
    | BudgetDimension;

  input_tokens?:
    | number
    | BudgetDimension;

  output_tokens?:
    | number
    | BudgetDimension;

  model_runtime?:
    | number
    | BudgetDimension;

  model_runtime_ms?:
    | number
    | BudgetDimension;

  execution_duration?:
    | number
    | BudgetDimension;

  execution_duration_ms?:
    | number
    | BudgetDimension;

  [key: string]: unknown;
}

export interface BudgetGovernance {
  limits?: Record<
    string,
    unknown
  >;

  sessions?: Record<
    string,
    ExtendedSessionBudget
  >;

  session_usage?: Record<
    string,
    ExtendedSessionBudget
  >;

  [key: string]: unknown;
}

/* =========================================================
   RUNTIME STATUS
   ========================================================= */

export interface SessionBudget {
  tool_calls: number;

  external_http_calls: number;

  estimated_cost: number;

  agent_turns?: number;

  input_tokens?: number;

  output_tokens?: number;

  model_runtime_ms?: number;

  execution_duration_ms?: number;

  [key: string]: unknown;
}

export interface RuntimeStatus {
  receipts: number;

  decisions: number;

  pending_approvals: number;

  session_budgets: Record<
    string,
    SessionBudget
  >;

  [key: string]: unknown;
}

/* =========================================================
   REAL SESSION DETAIL CONTRACT
   ========================================================= */

export interface SessionCompositionAnalysis {
  dangerous: boolean;

  score: number;

  category: string;

  reason: string;

  risk_level:
    | RiskLevel
    | string;

  tool_sequence: string[];

  evidence_receipt_ids:
    string[];

  accumulated_labels:
    string[];
}

export interface RuntimeSessionSnapshot {
  session_id: string;

  receipt_count: number;

  decision_count: number;

  tool_sequence: string[];

  instruction_origins:
    string[];

  data_labels: string[];

  receipt_ids: string[];

  decision_ids: string[];

  metadata: {
    composition_analyses?:
      SessionCompositionAnalysis[];

    [key: string]: unknown;
  };
}

export interface RuntimeReceiptObservedEffect {
  effect_type: string;

  resource: string;

  destination:
    | string
    | null;

  data_labels: string[];

  metadata: Record<
    string,
    unknown
  >;
}

export interface RuntimeReceiptArtifact {
  artifact_id: string;

  value: unknown;

  labels: string[];

  parent_artifact_ids:
    string[];

  transformation: string;
}

export interface RuntimeReceipt {
  receipt_id: string;

  call: {
    call_id: string;

    session_id: string;

    tool_name: string;

    arguments: Record<
      string,
      unknown
    >;

    instruction_origin: string;

    original_user_intent: string;

    model_name:
      | string
      | null;

    timestamp: string;
  };

  declared_effects: string[];

  observed_effects:
    RuntimeReceiptObservedEffect[];

  input_artifact_ids:
    string[];

  output_artifacts:
    RuntimeReceiptArtifact[];

  tool_version: string;

  tool_fingerprint: string;

  succeeded: boolean;

  error:
    | string
    | null;
}

export interface RuntimeSessionDecision {
  decision_id: string;

  call_id: string;

  action: DecisionAction;

  reason: string;

  matched_guardrail_id:
    | string
    | null;

  risk_level:
    | RiskLevel
    | string;
}

export interface RuntimeSessionResponse {
  snapshot:
    RuntimeSessionSnapshot;

  composition_analyses:
    SessionCompositionAnalysis[];

  receipts:
    RuntimeReceipt[];

  decisions:
    RuntimeSessionDecision[];

  policy_version: string;

  [key: string]: unknown;
}

/* =========================================================
   TELEMETRY
   ========================================================= */

export interface TelemetryResponse {
  evaluation_count?: number;

  ALLOW?: number;

  BLOCK?: number;

  REDACT?: number;

  REQUIRE_APPROVAL?: number;

  action_counts?: Partial<
    Record<
      DecisionAction,
      number
    >
  >;

  executed_count?: number;

  prevented_count?: number;

  execution_rate?: number;

  prevention_rate?: number;

  average_latency_ms?: number;

  avg_latency_ms?: number;

  p95_latency_ms?: number;

  active_controls?:
    | number
    | string[];

  policy_version?: string;

  audit_event_count?: number;

  audit_count?: number;

  persistence?: unknown;

  persistence_status?: unknown;

  budget_governance?:
    BudgetGovernance;

  [key: string]: unknown;
}

/* =========================================================
   PERSISTENCE
   ========================================================= */

export interface PersistenceStatus {
  enabled?: boolean;

  backend?: string;

  database?: string;

  healthy?: boolean;

  decisions?: number;

  receipts?: number;

  audit_events?: number;

  [key: string]: unknown;
}

/* =========================================================
   REAL AUDIT CONTRACT
   ========================================================= */

export interface AuditEvent {
  timestamp: string;

  session_id: string;

  call_id: string;

  tool_name: string;

  instruction_origin: string;

  control: string;

  action:
    | DecisionAction
    | string;

  reason: string;

  risk:
    | RiskLevel
    | string;

  latency_ms: number;

  executed: boolean;

  decision_id: string;

  receipt_id:
    | string
    | null;

  policy_version: string;

  /*
   * Compatibility with older UI.
   */
  risk_level?: string;

  [key: string]: unknown;
}

export interface AuditEventsResponse {
  status: string;

  policy_version: string;

  event_count: number;

  events: AuditEvent[];

  total?: number;

  count?: number;

  [key: string]: unknown;
}

export interface AuditExportResponse {
  status: string;

  format: "json";

  event_count: number;

  events: AuditEvent[];
}

/* =========================================================
   ERROR
   ========================================================= */

export class AegisApiError extends Error {
  status: number;
  endpoint: string;
  details?: unknown;

  constructor(
    message: string,
    status: number,
    endpoint: string,
    details?: unknown,
  ) {
    super(message);

    this.name =
      "AegisApiError";

    this.status =
      status;

    this.endpoint =
      endpoint;

    this.details =
      details;
  }
}

async function readErrorBody(
  response: Response,
): Promise<unknown> {
  const contentType =
    response.headers.get(
      "content-type",
    ) ?? "";

  try {
    if (
      contentType.includes(
        "application/json",
      )
    ) {
      return await response.json();
    }

    return await response.text();
  } catch {
    return null;
  }
}

function getErrorMessage(
  status: number,
  fallback: string,
  body: unknown,
): string {
  let backendMessage = "";

  if (
    typeof body === "string"
  ) {
    backendMessage =
      body.trim();
  } else if (
    body &&
    typeof body === "object"
  ) {
    const record =
      body as Record<
        string,
        unknown
      >;

    const detail =
      record.detail;

    const message =
      record.message;

    if (
      typeof detail === "string"
    ) {
      backendMessage =
        detail;
    } else if (
      Array.isArray(detail)
    ) {
      backendMessage =
        detail
          .map((item) => {
            if (
              item &&
              typeof item ===
                "object"
            ) {
              const rec =
                item as Record<
                  string,
                  unknown
                >;

              if (
                typeof rec.msg ===
                "string"
              ) {
                const location =
                  Array.isArray(
                    rec.loc,
                  )
                    ? rec.loc.join(
                        ".",
                      )
                    : "";

                return location
                  ? `${location}: ${rec.msg}`
                  : rec.msg;
              }
            }

            return String(item);
          })
          .join("; ");
    } else if (
      typeof message ===
      "string"
    ) {
      backendMessage =
        message;
    }
  }

  switch (status) {
    case 401:
      return (
        backendMessage ||
        "Authentication required. Configure the correct AegisTwin API key."
      );

    case 403:
      return (
        backendMessage ||
        "Permission denied. This operation requires a higher AegisTwin role."
      );

    case 404:
      return (
        backendMessage ||
        "The requested AegisTwin resource was not found."
      );

    case 422:
      return (
        backendMessage ||
        "The request body does not match the AegisTwin API contract."
      );

    default:
      return (
        backendMessage ||
        `${fallback}: HTTP ${status}`
      );
  }
}

async function ensureOk(
  response: Response,
  fallback: string,
  endpoint: string,
): Promise<void> {
  if (response.ok) return;

  const body =
    await readErrorBody(
      response,
    );

  throw new AegisApiError(
    getErrorMessage(
      response.status,
      fallback,
      body,
    ),
    response.status,
    endpoint,
    body,
  );
}

async function aegisFetch(
  endpoint: string,
  options?: RequestInit,
  fallback =
    "AegisTwin request failed",
): Promise<Response> {
  try {
    const response =
      await fetch(
        `${API_BASE}${endpoint}`,
        options,
      );

    await ensureOk(
      response,
      fallback,
      endpoint,
    );

    return response;
  } catch (error) {
    if (
      error instanceof
      AegisApiError
    ) {
      throw error;
    }

    if (
      error instanceof Error
    ) {
      throw new AegisApiError(
        `Backend unavailable: ${error.message}`,
        0,
        endpoint,
      );
    }

    throw new AegisApiError(
      "Backend unavailable",
      0,
      endpoint,
    );
  }
}

/* =========================================================
   PUBLIC ENDPOINTS
   ========================================================= */

export async function getHealth(): Promise<HealthResponse> {
  const response =
    await aegisFetch(
      "/health",
      {
        method: "GET",
        headers: authHeaders(),
      },
      "Health check failed",
    );

  return response.json();
}

export async function getPolicy(): Promise<PolicyResponse> {
  const response =
    await aegisFetch(
      "/policy",
      {
        method: "GET",
        headers: authHeaders(),
      },
      "Policy unavailable",
    );

  return response.json();
}

export async function getCapabilities(): Promise<CapabilitiesResponse> {
  const response =
    await aegisFetch(
      "/capabilities",
      {
        method: "GET",
        headers: authHeaders(),
      },
      "Capabilities unavailable",
    );

  return response.json();
}

export async function evaluateGateway(
  payload:
    GatewayEvaluateRequest,
): Promise<GatewayEvaluateResponse> {
  const response =
    await aegisFetch(
      "/gateway/evaluate",
      {
        method: "POST",

        headers:
          jsonHeaders(),

        body:
          JSON.stringify(
            payload,
          ),
      },
      "Gateway evaluation failed",
    );

  /*
   * A BLOCK is a successful HTTP response and must
   * never be converted into an API error.
   */

  return response.json();
}

export async function runExtendedBenchmark(
  payload: Record<
    string,
    unknown
  > = {},
): Promise<ExtendedBenchmarkResponse> {
  const response =
    await aegisFetch(
      "/benchmark/extended",
      {
        method: "POST",

        headers:
          jsonHeaders(),

        body:
          JSON.stringify(
            payload,
          ),
      },
      "Extended benchmark failed",
    );

  return response.json();
}

export async function attackMyAgent(): Promise<AttackResponse> {
  const response =
    await aegisFetch(
      "/attack-my-agent",
      {
        method: "POST",

        headers:
          jsonHeaders(),

        body: JSON.stringify({}),
      },
      "Attack workflow failed",
    );

  return response.json();
}

/* =========================================================
   VIEWER ENDPOINTS
   ========================================================= */

export async function getTelemetry(
  viewerKey?: string,
): Promise<TelemetryResponse> {
  const response =
    await aegisFetch(
      "/telemetry",
      {
        method: "GET",

        headers:
          authHeaders(
            "viewer",
            viewerKey,
          ),
      },
      "Telemetry unavailable",
    );

  return response.json();
}

export async function getRuntimeStatus(
  viewerKey?: string,
): Promise<RuntimeStatus> {
  const response =
    await aegisFetch(
      "/runtime/status",
      {
        method: "GET",

        headers:
          authHeaders(
            "viewer",
            viewerKey,
          ),
      },
      "Runtime status unavailable",
    );

  return response.json();
}

export async function getRuntimeSession(
  sessionId: string,
  viewerKey?: string,
): Promise<RuntimeSessionResponse> {
  const encoded =
    encodeURIComponent(
      sessionId,
    );

  const response =
    await aegisFetch(
      `/runtime/sessions/${encoded}`,
      {
        method: "GET",

        headers:
          authHeaders(
            "viewer",
            viewerKey,
          ),
      },
      "Runtime session unavailable",
    );

  return response.json();
}

export async function getPersistenceStatus(
  viewerKey?: string,
): Promise<PersistenceStatus> {
  const response =
    await aegisFetch(
      "/persistence/status",
      {
        method: "GET",

        headers:
          authHeaders(
            "viewer",
            viewerKey,
          ),
      },
      "Persistence status unavailable",
    );

  return response.json();
}

/* =========================================================
   SECURITY ENDPOINTS
   ========================================================= */

export async function getAuditEvents(
  securityKey?: string,
): Promise<AuditEventsResponse> {
  const response =
    await aegisFetch(
      "/audit/events",
      {
        method: "GET",

        headers:
          authHeaders(
            "security",
            securityKey,
          ),
      },
      "Audit events unavailable",
    );

  return response.json();
}

export async function exportAudit(
  format:
    | "json"
    | "csv" =
    "json",
  securityKey?: string,
): Promise<
  AuditExportResponse | Blob
> {
  const response =
    await aegisFetch(
      `/audit/export?format=${encodeURIComponent(
        format,
      )}`,
      {
        method: "GET",

        headers:
          authHeaders(
            "security",
            securityKey,
          ),
      },
      "Audit export failed",
    );

  if (format === "csv") {
    return response.blob();
  }

  return response.json();
}

/* =========================================================
   ADMIN ENDPOINTS
   ========================================================= */

export async function reloadPolicy(
  adminKey?: string,
): Promise<PolicyReloadResponse> {
  const response =
    await aegisFetch(
      "/policy/reload",
      {
        method: "POST",

        headers:
          jsonHeaders(
            "admin",
            adminKey,
          ),

        body: JSON.stringify({}),
      },
      "Policy reload failed",
    );

  return response.json();
}

export async function resetRuntime(
  adminKey?: string,
): Promise<unknown> {
  const response =
    await aegisFetch(
      "/runtime/reset",
      {
        method: "POST",

        headers:
          jsonHeaders(
            "admin",
            adminKey,
          ),

        body: JSON.stringify({}),
      },
      "Runtime reset failed",
    );

  return response.json();
}