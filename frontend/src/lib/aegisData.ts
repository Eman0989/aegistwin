import type {
  AttackPath,
  AttackResponse,
  GeneratedGuardrail,
  RuntimeStatus,
} from "./api";

/* =========================================================
   HELPERS
   ========================================================= */

function safeNumber(
  value: unknown,
  fallback = 0,
): number {
  return typeof value === "number" &&
    Number.isFinite(value)
    ? value
    : fallback;
}

export function toPercent(
  value: number,
): number {
  return Math.round(
    safeNumber(value) * 100,
  );
}

function unique(
  values: string[],
): string[] {
  return Array.from(
    new Set(values),
  );
}

/* =========================================================
   GUARDRAIL
   ========================================================= */

export function getGeneratedGuardrail(
  result: AttackResponse | null,
): GeneratedGuardrail | null {
  if (!result) {
    return null;
  }

  if (
    result.generated_guardrail
  ) {
    return result.generated_guardrail;
  }

  if (
    result.benchmark_report
      ?.guardrail
  ) {
    return result.benchmark_report
      .guardrail;
  }

  return null;
}

export function getGuardrailText(
  result: AttackResponse | null,
): string {
  const guardrail =
    getGeneratedGuardrail(result);

  if (!guardrail) {
    return "No guardrail generated.";
  }

  const labels =
    guardrail.source_labels.join(
      " / ",
    );

  return `${labels} → ${guardrail.destination} = ${guardrail.action}`;
}

export function getGuardrailCode(
  result: AttackResponse | null,
): string {
  const guardrail =
    getGeneratedGuardrail(result);

  if (!guardrail) {
    return `policy "pending" {
  action = NONE
}`;
  }

  const source =
    guardrail.source_labels[0] ??
    "UNKNOWN";

  const derived =
    guardrail.source_labels[1];

  const derivedLine = derived
    ? `\n  derived     = ${derived}`
    : "";

  return `policy "${guardrail.guardrail_id}" {
  source      = ${source}${derivedLine}
  destination = ${guardrail.destination}
  action      = ${guardrail.action}
}`;
}

/* =========================================================
   ATTACK PATH
   ========================================================= */

export function getPrimaryAttackPath(
  result: AttackResponse | null,
): AttackPath | null {
  if (!result) {
    return null;
  }

  if (
    result.attack_path_details
  ) {
    return result.attack_path_details;
  }

  return (
    result.twin_analysis
      ?.attack_paths?.[0] ??
    null
  );
}

export function getAttackToolPath(
  result: AttackResponse | null,
): string[] {
  if (!result) {
    return [];
  }

  /*
   * Best representation:
   * backend top-level attack_path
   * already contains simple tool names.
   */
  if (
    Array.isArray(
      result.attack_path,
    ) &&
    result.attack_path.length > 0
  ) {
    return result.attack_path;
  }

  /*
   * Provenance calls preserve the
   * observed execution order.
   */
  const provenanceTools =
    result.twin_analysis
      ?.provenance?.calls?.map(
        (call) => call.tool_name,
      ) ?? [];

  if (
    provenanceTools.length > 0
  ) {
    return unique(
      provenanceTools,
    );
  }

  /*
   * Final fallback:
   * extract tool nodes from graph.
   */
  return unique(
    (
      result.twin_analysis
        ?.graph?.nodes ?? []
    )
      .filter(
        (node) =>
          node.type === "TOOL",
      )
      .map(
        (node) =>
          node.name ??
          node.tool_name ??
          "",
      )
      .filter(Boolean),
  );
}

/* =========================================================
   TWIN SUMMARY
   ========================================================= */

export function getTwinSummary(
  result: AttackResponse | null,
) {
  const capability =
    result?.twin_analysis
      ?.capability_map?.summary;

  const attackPaths =
    result?.twin_analysis
      ?.attack_paths ?? [];

  const guardrail =
    getGeneratedGuardrail(result);

  const lineage =
    result?.twin_analysis
      ?.lineage;

  return {
    totalTools:
      capability?.total_tools ??
      0,

    criticalTools:
      capability?.critical_tools ??
      0,

    highRiskTools:
      capability?.high_risk_tools ??
      0,

    behavioralMismatches:
      capability
        ?.behavioral_mismatches ??
      0,

    externalTools:
      capability
        ?.external_communication_tools ??
      0,

    sensitiveDataTools:
      capability
        ?.sensitive_data_tools ??
      0,

    attackPaths:
      attackPaths.length,

    activeGuardrails:
      guardrail?.enabled
        ? 1
        : 0,

    sensitiveLabels:
      lineage
        ?.sensitive_labels ?? [],

    sensitiveArtifacts:
      lineage
        ?.sensitive_artifact_ids
        ?.length ?? 0,
  };
}

/* =========================================================
   PROVENANCE
   ========================================================= */

export function getProvenanceSummary(
  result: AttackResponse | null,
) {
  const chain =
    result?.twin_analysis
      ?.provenance?.chain;

  return {
    callCount:
      chain?.call_count ?? 0,

    origin:
      chain?.effective_origin ??
      "UNKNOWN",

    untrusted:
      chain
        ?.contains_untrusted_content ??
      false,

    canAuthorizeSensitiveAction:
      chain
        ?.can_authorize_sensitive_action ??
      false,

    risk:
      chain?.risk_level ??
      "LOW",
  };
}

/* =========================================================
   INTENT
   ========================================================= */

export function getIntentSummary(
  result: AttackResponse | null,
) {
  const actions =
    result?.twin_analysis
      ?.intent_action ?? [];

  const mismatch =
    actions.find(
      (item) =>
        item.aligned === false,
    );

  return {
    totalActions:
      actions.length,

    alignedActions:
      actions.filter(
        (item) => item.aligned,
      ).length,

    mismatchFound:
      Boolean(mismatch),

    mismatchEffect:
      mismatch?.final_effect ??
      null,

    mismatchDestination:
      mismatch?.destination ??
      null,

    mismatchRisk:
      mismatch?.risk_level ??
      null,

    mismatchReason:
      mismatch?.reason ??
      null,

    originalIntent:
      mismatch?.original_intent ??
      actions[0]
        ?.original_intent ??
      result
        ?.original_user_intent ??
      "Unknown",
  };
}

/* =========================================================
   LINEAGE
   ========================================================= */

export function getLineageSummary(
  result: AttackResponse | null,
) {
  const lineage =
    result?.twin_analysis
      ?.lineage;

  return {
    labels:
      lineage
        ?.sensitive_labels ?? [],

    artifactCount:
      lineage
        ?.artifacts?.length ??
      0,

    sensitiveArtifactCount:
      lineage
        ?.sensitive_artifact_ids
        ?.length ?? 0,

    transformations:
      unique(
        (
          lineage
            ?.artifacts ?? []
        )
          .map(
            (artifact) =>
              artifact.transformation,
          )
          .filter(Boolean),
      ),
  };
}

/* =========================================================
   LEAST PRIVILEGE
   ========================================================= */

export function getLeastPrivilegeSummary(
  result: AttackResponse | null,
) {
  const analysis =
    result?.twin_analysis
      ?.least_privilege;

  const summary =
    analysis?.summary;

  return {
    totalTools:
      summary?.total_tools ??
      0,

    toolsWithExcessPrivilege:
      summary
        ?.tools_with_excess_privilege ??
      0,

    removableCapabilities:
      summary
        ?.total_removable_capabilities ??
      0,

    recommendations:
      analysis
        ?.recommendations ?? [],
  };
}

/* =========================================================
   DRIFT
   ========================================================= */

export function getDriftSummary(
  result: AttackResponse | null,
) {
  const drift =
    result?.twin_analysis
      ?.drift;

  return {
    available:
      drift?.available ??
      false,

    reason:
      drift?.reason ??
      "No drift analysis available.",

    report:
      drift?.report ??
      null,
  };
}

/* =========================================================
   BENCHMARK / REPLAY
   ========================================================= */

export function getReplayMetrics(
  result: AttackResponse | null,
) {
  if (!result) {
    return {
      asrBefore: 0,
      asrAfter: 0,

      utilityBefore: 0,
      utilityAfter: 0,

      falsePositiveBefore: 0,
      falsePositiveAfter: 0,

      frictionBefore: 0,
      frictionAfter: 0,

      regressionPassed: false,

      beforeLatency: 0,
      afterLatency: 0,

      maliciousBlockedAfter:
        false,

      legitimateAllowedAfter:
        false,
    };
  }

  const cases =
    result.benchmark_report
      ?.cases ?? [];

  const afterMalicious =
    cases.find(
      (testCase) =>
        testCase.phase ===
          "after" &&
        testCase.scenario ===
          "malicious",
    );

  const afterLegitimate =
    cases.find(
      (testCase) =>
        testCase.phase ===
          "after" &&
        testCase.scenario ===
          "legitimate",
    );

  return {
    asrBefore:
      toPercent(
        result.asr_before,
      ),

    asrAfter:
      toPercent(
        result.asr_after,
      ),

    utilityBefore:
      toPercent(
        result.utility_before,
      ),

    utilityAfter:
      toPercent(
        result.utility_after,
      ),

    falsePositiveBefore:
      toPercent(
        result
          .false_positive_rate
          ?.before ?? 0,
      ),

    falsePositiveAfter:
      toPercent(
        result
          .false_positive_rate
          ?.after ?? 0,
      ),

    frictionBefore:
      toPercent(
        result.friction
          ?.before ?? 0,
      ),

    frictionAfter:
      toPercent(
        result.friction
          ?.after ?? 0,
      ),

    regressionPassed:
      result.regression_passed,

    beforeLatency:
      safeNumber(
        result
          .measured_latency
          ?.before_ms_per_decision,
      ),

    afterLatency:
      safeNumber(
        result
          .measured_latency
          ?.after_ms_per_decision,
      ),

    maliciousBlockedAfter:
      afterMalicious
        ?.blocked ?? false,

    legitimateAllowedAfter:
      afterLegitimate
        ?.allowed ?? false,
  };
}

/* =========================================================
   RUNTIME STATUS
   ========================================================= */

export function getRuntimeSummary(
  runtime: RuntimeStatus | null,
) {
  if (!runtime) {
    return {
      receipts: 0,
      decisions: 0,
      pendingApprovals: 0,
      sessionCount: 0,
      toolCalls: 0,
      externalCalls: 0,
      estimatedCost: 0,
    };
  }

  const sessions =
    Object.values(
      runtime.session_budgets ?? {},
    );

  return {
    receipts:
      runtime.receipts,

    decisions:
      runtime.decisions,

    pendingApprovals:
      runtime.pending_approvals,

    sessionCount:
      sessions.length,

    toolCalls:
      sessions.reduce(
        (total, session) =>
          total +
          safeNumber(
            session.tool_calls,
          ),
        0,
      ),

    externalCalls:
      sessions.reduce(
        (total, session) =>
          total +
          safeNumber(
            session
              .external_http_calls,
          ),
        0,
      ),

    estimatedCost:
      sessions.reduce(
        (total, session) =>
          total +
          safeNumber(
            session
              .estimated_cost,
          ),
        0,
      ),
  };
}

/* =========================================================
   COMPLETE CONSOLE VIEW MODEL
   ========================================================= */

export function buildConsoleModel(
  result: AttackResponse | null,
  runtime: RuntimeStatus | null,
) {
  const guardrail =
    getGeneratedGuardrail(result);

  const attack =
    getPrimaryAttackPath(result);

  return {
    twin:
      getTwinSummary(result),

    provenance:
      getProvenanceSummary(
        result,
      ),

    intent:
      getIntentSummary(result),

    lineage:
      getLineageSummary(result),

    leastPrivilege:
      getLeastPrivilegeSummary(
        result,
      ),

    drift:
      getDriftSummary(result),

    replay:
      getReplayMetrics(result),

    runtime:
      getRuntimeSummary(runtime),

    attack: {
      details:
        attack,

      path:
        getAttackToolPath(
          result,
        ),

      severity:
        attack
          ?.risk_level ??
        "LOW",

      destination:
        attack
          ?.destination ??
        null,

      reproducible:
        attack
          ?.reproducible ??
        false,

      evidenceCount:
        attack
          ?.evidence_receipt_ids
          ?.length ?? 0,
    },

    guardrail: {
      data:
        guardrail,

      text:
        getGuardrailText(
          result,
        ),

      code:
        getGuardrailCode(
          result,
        ),

      enabled:
        guardrail
          ?.enabled ??
        false,
    },
  };
}

export type ConsoleModel =
  ReturnType<
    typeof buildConsoleModel
  >;