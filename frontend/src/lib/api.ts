/* =========================================================
   AEGISTWIN API CONTRACT
   ========================================================= */

const API_BASE =
  "http://127.0.0.1:8000";

/* =========================================================
   SHARED TYPES
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

/* =========================================================
   TOOL PROFILE
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

/* =========================================================
   CAPABILITY MAP
   ========================================================= */

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

/* =========================================================
   GRAPH
   ========================================================= */

export interface TwinGraphNode {
  id: string;
  type: string;

  name?: string;
  version?: string;

  tool_name?: string;

  call_id?: string;
  session_id?: string;

  arguments?: Record<
    string,
    unknown
  >;

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

/* =========================================================
   PROVENANCE
   ========================================================= */

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

/* =========================================================
   INTENT / ACTION
   ========================================================= */

export interface IntentAction {
  original_intent: string;

  final_effect: string;

  destination:
    | string
    | null;

  aligned: boolean;

  risk_level: RiskLevel;

  reason: string;
}

/* =========================================================
   LINEAGE
   ========================================================= */

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

  traces: Record<
    string,
    string[]
  >;

  artifacts: LineageArtifact[];
}

/* =========================================================
   ATTACK PATH
   ========================================================= */

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

/* =========================================================
   LEAST PRIVILEGE
   ========================================================= */

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

/* =========================================================
   DRIFT
   ========================================================= */

export interface DriftAnalysis {
  available: boolean;

  reason:
    | string
    | null;

  report: unknown;
}

/* =========================================================
   TWIN ANALYSIS
   ========================================================= */

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
   GENERATED GUARDRAIL
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

/* =========================================================
   BENCHMARK
   ========================================================= */

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
  phase:
    | "before"
    | "after";

  scenario:
    | "malicious"
    | "legitimate";

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
  before_metrics:
    BenchmarkMetrics;

  after_metrics:
    BenchmarkMetrics;

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

/* =========================================================
   ATTACK RESPONSE
   ========================================================= */

export interface AttackResponse {
  benchmark_report:
    BenchmarkReport;

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

  /*
   * These exist in the full backend workflow
   * in some response versions. Keeping them
   * optional makes the UI compatible with both.
   */

  generated_guardrail?:
    GeneratedGuardrail;

  attack_path?:
    string[];

  attack_path_details?:
    AttackPath;

  summary?: {
    attack_before?: string;

    attack_after?: string;

    legitimate_task?: string;

    [key: string]:
      string | undefined;
  };

  original_user_intent?:
    string;

  instruction_origin?:
    string;

  sensitive_lineage?:
    string[];

  before?: unknown;

  after?: unknown;

  legitimate_workflow?:
    unknown;

  [key: string]:
    unknown;
}

/* =========================================================
   RUNTIME STATUS
   ========================================================= */

export interface SessionBudget {
  tool_calls: number;

  external_http_calls: number;

  estimated_cost: number;
}

export interface RuntimeStatus {
  receipts: number;

  decisions: number;

  pending_approvals: number;

  session_budgets: Record<
    string,
    SessionBudget
  >;
}

/* =========================================================
   API ERROR HELPER
   ========================================================= */

async function ensureOk(
  response: Response,
  fallback: string,
) {
  if (response.ok) {
    return;
  }

  const text =
    await response.text();

  throw new Error(
    text ||
      `${fallback}: ${response.status}`,
  );
}

/* =========================================================
   ATTACK MY AGENT
   ========================================================= */

export async function attackMyAgent(): Promise<AttackResponse> {
  const response =
    await fetch(
      `${API_BASE}/attack-my-agent`,
      {
        method: "POST",

        headers: {
          "Content-Type":
            "application/json",
        },

        body: JSON.stringify(
          {},
        ),
      },
    );

  await ensureOk(
    response,
    "Attack workflow failed",
  );

  return (
    await response.json()
  ) as AttackResponse;
}

/* =========================================================
   RUNTIME STATUS
   ========================================================= */

export async function getRuntimeStatus(): Promise<RuntimeStatus> {
  const response =
    await fetch(
      `${API_BASE}/runtime/status`,
    );

  await ensureOk(
    response,
    "Runtime status unavailable",
  );

  return (
    await response.json()
  ) as RuntimeStatus;
}

/* =========================================================
   RESET RUNTIME
   ========================================================= */

export async function resetRuntime(): Promise<unknown> {
  const response =
    await fetch(
      `${API_BASE}/runtime/reset`,
      {
        method: "POST",
      },
    );

  await ensureOk(
    response,
    "Runtime reset failed",
  );

  return response.json();
}