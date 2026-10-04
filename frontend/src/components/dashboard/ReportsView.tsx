import {
  Activity,
  ArrowRight,
  Check,
  CheckCircle2,
  Code2,
  Download,
  FileCheck2,
  Fingerprint,
  Printer,
  ShieldCheck,
  TriangleAlert,
  XCircle,
} from "lucide-react";

import { useMemo } from "react";

import type {
  AttackResponse,
} from "../../lib/api";

import type {
  ConsoleModel,
} from "../../lib/aegisData";

/* =========================================================
   TYPES
   ========================================================= */

type AttackStage =
  | "idle"
  | "discover"
  | "analyze"
  | "compile"
  | "replay"
  | "verify"
  | "complete"
  | "error";

interface ReportsViewProps {
  stage: AttackStage;
  stageIndex: number;
  result: AttackResponse | null;
  error: string;
  model: ConsoleModel;
}

/* =========================================================
   REPORTS VIEW
   ========================================================= */

export default function ReportsView({
  stage,
  stageIndex,
  result,
  error,
  model,
}: ReportsViewProps) {
  /* =======================================================
     REPORT STATE
     ======================================================= */

  const verified =
    stage === "complete" &&
    Boolean(result) &&
    model.replay.regressionPassed;

  const reportId = useMemo(
    () =>
      `AT-${Date.now()
        .toString(36)
        .toUpperCase()}`,
    [],
  );

  const reportDate = useMemo(
    () =>
      new Date().toLocaleString(),
    [],
  );

  /* =======================================================
     REAL BACKEND DATA
     ======================================================= */

  const attack =
    model.attack.details;

  const guardrail =
    model.guardrail.data;

  const attackPath =
    model.attack.path;

  const attackId =
    attack?.attack_id ??
    "PENDING";

  const severity =
    model.attack.severity ??
    "PENDING";

  const destination =
    model.attack.destination ??
    "—";

  const origin =
    model.provenance.origin ??
    "—";

  const sourceLabels =
    model.lineage.labels;

  const protectedLabel =
    sourceLabels.find(
      (label) =>
        !label.startsWith(
          "DerivedFrom",
        ),
    ) ??
    sourceLabels[0] ??
    "SensitiveData";

  const derivedLabel =
    sourceLabels.find(
      (label) =>
        label.startsWith(
          "DerivedFrom",
        ),
    ) ??
    "Derived sensitive data";

  const attackBlocked =
    model.replay
      .maliciousBlockedAfter;

  const legitimateAllowed =
    model.replay
      .legitimateAllowedAfter;

  const regressionPassed =
    model.replay
      .regressionPassed;

  const policyCount =
    guardrail ? 1 : 0;

  /* =======================================================
     EXPORT JSON REPORT
     ======================================================= */

  const exportJson = () => {
    const payload = {
      report_id: reportId,

      generated_at:
        new Date().toISOString(),

      system: "AegisTwin",

      security_verdict: {
        verified,

        attack_blocked:
          attackBlocked,

        legitimate_work_preserved:
          legitimateAllowed,

        regression_passed:
          regressionPassed,
      },

      scenario: {
        id: attackId,

        severity,

        original_intent:
          model.intent
            .originalIntent,

        instruction_origin:
          origin,

        destination,

        reproducible:
          model.attack
            .reproducible,

        evidence_receipts:
          model.attack
            .evidenceCount,
      },

      attack_path:
        attackPath,

      provenance: {
        origin:
          model.provenance
            .origin,

        call_count:
          model.provenance
            .callCount,

        contains_untrusted:
          model.provenance
            .untrusted,

        can_authorize_sensitive_action:
          model.provenance
            .canAuthorizeSensitiveAction,

        risk:
          model.provenance
            .risk,
      },

      intent: {
        total_actions:
          model.intent
            .totalActions,

        aligned_actions:
          model.intent
            .alignedActions,

        mismatch_found:
          model.intent
            .mismatchFound,

        mismatch_effect:
          model.intent
            .mismatchEffect,

        mismatch_destination:
          model.intent
            .mismatchDestination,

        mismatch_reason:
          model.intent
            .mismatchReason,
      },

      lineage: {
        labels:
          model.lineage
            .labels,

        artifact_count:
          model.lineage
            .artifactCount,

        sensitive_artifact_count:
          model.lineage
            .sensitiveArtifactCount,

        transformations:
          model.lineage
            .transformations,
      },

      generated_guardrail:
        guardrail,

      replay_metrics: {
        attack_success_rate: {
          before:
            model.replay
              .asrBefore,

          after:
            model.replay
              .asrAfter,
        },

        utility: {
          before:
            model.replay
              .utilityBefore,

          after:
            model.replay
              .utilityAfter,
        },

        false_positive_rate: {
          before:
            model.replay
              .falsePositiveBefore,

          after:
            model.replay
              .falsePositiveAfter,
        },

        friction: {
          before:
            model.replay
              .frictionBefore,

          after:
            model.replay
              .frictionAfter,
        },

        regression_passed:
          model.replay
            .regressionPassed,

        malicious_blocked_after:
          model.replay
            .maliciousBlockedAfter,

        legitimate_allowed_after:
          model.replay
            .legitimateAllowedAfter,
      },

      least_privilege: {
        total_tools:
          model.leastPrivilege
            .totalTools,

        tools_with_excess_privilege:
          model.leastPrivilege
            .toolsWithExcessPrivilege,

        removable_capabilities:
          model.leastPrivilege
            .removableCapabilities,

        recommendations:
          model.leastPrivilege
            .recommendations,
      },

      drift: {
        available:
          model.drift
            .available,

        reason:
          model.drift
            .reason,
      },

      runtime: {
        receipts:
          model.runtime
            .receipts,

        decisions:
          model.runtime
            .decisions,

        pending_approvals:
          model.runtime
            .pendingApprovals,

        sessions:
          model.runtime
            .sessionCount,

        tool_calls:
          model.runtime
            .toolCalls,

        external_calls:
          model.runtime
            .externalCalls,

        estimated_cost:
          model.runtime
            .estimatedCost,
      },

      backend_result:
        result,
    };

    const blob =
      new Blob(
        [
          JSON.stringify(
            payload,
            null,
            2,
          ),
        ],
        {
          type:
            "application/json",
        },
      );

    const url =
      URL.createObjectURL(
        blob,
      );

    const anchor =
      document.createElement(
        "a",
      );

    anchor.href =
      url;

    anchor.download =
      `${reportId}-aegistwin-report.json`;

    document.body.appendChild(
      anchor,
    );

    anchor.click();

    anchor.remove();

    URL.revokeObjectURL(
      url,
    );
  };

  /* =======================================================
     INTELLIGENCE MODULES
     ======================================================= */

  const intelligenceModules = [
    {
      name:
        "Capability Map",

      status:
        result
          ? `${model.twin.totalTools} TOOLS`
          : "WAITING",

      complete:
        Boolean(result),
    },

    {
      name:
        "Provenance",

      status:
        result
          ? model.provenance
              .risk
          : "WAITING",

      complete:
        Boolean(result),
    },

    {
      name:
        "Intent Analysis",

      status:
        result
          ? model.intent
              .mismatchFound
            ? "MISMATCH FOUND"
            : "ALIGNED"
          : "WAITING",

      complete:
        Boolean(result),
    },

    {
      name:
        "Data Lineage",

      status:
        result
          ? `${model.lineage.labels.length} LABELS`
          : "WAITING",

      complete:
        Boolean(result),
    },

    {
      name:
        "Attack Paths",

      status:
        result
          ? `${model.twin.attackPaths} FOUND`
          : "WAITING",

      complete:
        Boolean(result),
    },

    {
      name:
        "Least Privilege",

      status:
        result
          ? `${model.leastPrivilege.toolsWithExcessPrivilege} EXCESS`
          : "WAITING",

      complete:
        Boolean(result),
    },

    {
      name:
        "Drift",

      status:
        !result
          ? "WAITING"
          : model.drift
              .available
            ? "ANALYZED"
            : "BASELINE REQUIRED",

      complete:
        Boolean(result),
    },
  ];

  /* =======================================================
     RENDER
     ======================================================= */

  return (
    <section className="pdf-report-page">
      {/* ===================================================
          TOOLBAR
          =================================================== */}

      <div className="pdf-report-toolbar">
        <div>
          <span className="console-kicker">
            SECURITY EVIDENCE
          </span>

          <h2>
            Generated Report
          </h2>

          <p>
            Enterprise security assessment
            produced from the live AegisTwin
            verification pipeline.
          </p>
        </div>

        <div className="pdf-report-toolbar__actions">
          <button
            type="button"
            className="pdf-toolbar-secondary"
            onClick={
              exportJson
            }
            disabled={
              !result
            }
          >
            <Download
              size={15}
            />

            EXPORT DATA
          </button>

          <button
            type="button"
            className="pdf-toolbar-primary"
            onClick={() =>
              window.print()
            }
          >
            <Printer
              size={15}
            />

            SAVE AS PDF
          </button>
        </div>
      </div>

      {/* ===================================================
          PAPER
          =================================================== */}

      <div className="security-report-paper">
        {/* WATERMARK */}

        <div className="report-paper-watermark">
          AEGISTWIN
        </div>

        {/* =================================================
            DOCUMENT HEADER
            ================================================= */}

        <header className="report-document-header">
          <div className="report-document-brand">
            <div className="report-document-mark">
              A
            </div>

            <div>
              <strong>
                AEGISTWIN
              </strong>

              <span>
                Autonomous AI Security
              </span>
            </div>
          </div>

          <div className="report-document-meta">
            <span>
              SECURITY ASSESSMENT
            </span>

            <strong>
              {reportId}
            </strong>

            <small>
              {reportDate}
            </small>
          </div>
        </header>

        <div className="report-document-rule" />

        {/* =================================================
            COVER
            ================================================= */}

        <section className="report-cover-block">
          <div className="report-cover-number">
            01 / SECURITY REPORT
          </div>

          <h1>
            Agent Security
            <br />
            Verification Report
          </h1>

          <p>
            Automated analysis of agent
            capabilities, attack paths,
            sensitive-data lineage,
            generated runtime controls and
            regression verification.
          </p>

          <div
            className={`report-document-verdict ${
              verified
                ? "verified"
                : ""
            }`}
          >
            <div className="report-document-verdict__icon">
              {verified ? (
                <ShieldCheck
                  size={27}
                />
              ) : (
                <Activity
                  size={27}
                />
              )}
            </div>

            <div>
              <span>
                FINAL SECURITY VERDICT
              </span>

              <strong>
                {!result
                  ? "ANALYSIS NOT YET EXECUTED"
                  : attackBlocked &&
                      legitimateAllowed &&
                      regressionPassed
                    ? "ATTACK BLOCKED · UTILITY PRESERVED"
                    : "SECURITY REVIEW REQUIRED"}
              </strong>
            </div>

            <div className="report-document-verdict__state">
              {verified
                ? "VERIFIED"
                : result
                  ? "REVIEW"
                  : "PENDING"}
            </div>
          </div>
        </section>

        {/* =================================================
            01 — EXECUTIVE SUMMARY
            ================================================= */}

        <section className="report-document-section">
          <div className="report-section-number">
            01
          </div>

          <div className="report-section-body">
            <div className="report-section-title">
              <span>
                EXECUTIVE SUMMARY
              </span>

              <h2>
                Security outcome
              </h2>
            </div>

            <p className="report-lead">
              {result
                ? `AegisTwin identified a ${severity.toLowerCase()} execution path originating from ${origin}. The path attempted to move sensitive or derived information across the ${destination} trust boundary. A minimum guardrail was compiled and the same malicious workflow was replayed against the protected runtime.`
                : "Run Attack My Agent to generate a complete evidence-backed security assessment."}
            </p>

            <div className="report-document-metrics">
              {/* ASR */}

              <div>
                <span>
                  ATTACK SUCCESS
                </span>

                <div>
                  <strong className="report-doc-danger">
                    {result
                      ? `${model.replay.asrBefore}%`
                      : "—"}
                  </strong>

                  <ArrowRight
                    size={15}
                  />

                  <strong className="report-doc-safe">
                    {result
                      ? `${model.replay.asrAfter}%`
                      : "—"}
                  </strong>
                </div>

                <small>
                  Before → after
                </small>
              </div>

              {/* UTILITY */}

              <div>
                <span>
                  LEGITIMATE UTILITY
                </span>

                <div>
                  <strong>
                    {result
                      ? `${model.replay.utilityBefore}%`
                      : "—"}
                  </strong>

                  <ArrowRight
                    size={15}
                  />

                  <strong className="report-doc-safe">
                    {result
                      ? `${model.replay.utilityAfter}%`
                      : "—"}
                  </strong>
                </div>

                <small>
                  Preserved
                </small>
              </div>

              {/* FALSE POSITIVES */}

              <div>
                <span>
                  FALSE POSITIVES
                </span>

                <div>
                  <strong className="report-doc-safe">
                    {result
                      ? `${model.replay.falsePositiveAfter}%`
                      : "—"}
                  </strong>
                </div>

                <small>
                  Regression test
                </small>
              </div>

              {/* POLICY */}

              <div>
                <span>
                  POLICY CHANGES
                </span>

                <div>
                  <strong>
                    {policyCount}
                  </strong>
                </div>

                <small>
                  Minimum control
                </small>
              </div>
            </div>
          </div>
        </section>

        {/* =================================================
            02 — SECURITY FINDING
            ================================================= */}

        <section className="report-document-section">
          <div className="report-section-number">
            02
          </div>

          <div className="report-section-body">
            <div className="report-section-title">
              <span>
                SECURITY FINDING
              </span>

              <h2>
                Sensitive-data exfiltration
              </h2>
            </div>

            <div className="report-finding-header">
              <div>
                <TriangleAlert
                  size={18}
                />

                <span>
                  {attackId}
                </span>
              </div>

              <strong>
                {result
                  ? severity
                  : "PENDING"}
              </strong>
            </div>

            <table className="report-document-table">
              <tbody>
                <tr>
                  <th>
                    Original intent
                  </th>

                  <td>
                    {result
                      ? model.intent
                          .originalIntent ||
                        "Unavailable"
                      : "—"}
                  </td>
                </tr>

                <tr>
                  <th>
                    Provenance
                  </th>

                  <td>
                    {result
                      ? origin
                      : "—"}
                  </td>
                </tr>

                <tr>
                  <th>
                    Sensitive class
                  </th>

                  <td>
                    {result
                      ? protectedLabel
                      : "—"}
                  </td>
                </tr>

                <tr>
                  <th>
                    Derived class
                  </th>

                  <td>
                    {result
                      ? derivedLabel
                      : "—"}
                  </td>
                </tr>

                <tr>
                  <th>
                    Destination
                  </th>

                  <td>
                    {result
                      ? destination
                      : "—"}
                  </td>
                </tr>

                <tr>
                  <th>
                    Intent evaluation
                  </th>

                  <td
                    className={
                      model.intent
                        .mismatchFound
                        ? "report-doc-danger-text"
                        : ""
                    }
                  >
                    {!result
                      ? "—"
                      : model.intent
                          .mismatchFound
                        ? "MISMATCH"
                        : "ALIGNED"}
                  </td>
                </tr>
              </tbody>
            </table>

            {/* REAL ATTACK PATH */}

            <div className="report-document-path">
              {attackPath.length >
              0 ? (
                attackPath.map(
                  (
                    tool,
                    index,
                  ) => (
                    <div
                      key={`${tool}-${index}`}
                      style={{
                        display:
                          "contents",
                      }}
                    >
                      <div
                        className={
                          index ===
                          attackPath.length -
                            1
                            ? "danger"
                            : ""
                        }
                      >
                        <span>
                          {String(
                            index + 1,
                          ).padStart(
                            2,
                            "0",
                          )}
                        </span>

                        <strong>
                          {tool}
                        </strong>

                        <small>
                          {index === 0
                            ? origin
                            : index ===
                                attackPath.length -
                                  1
                              ? destination
                              : "Observed execution"}
                        </small>
                      </div>

                      {index <
                        attackPath.length -
                          1 && (
                        <ArrowRight
                          size={17}
                        />
                      )}
                    </div>
                  ),
                )
              ) : (
                <span>
                  Attack path awaiting analysis
                </span>
              )}
            </div>
          </div>
        </section>

        {/* =================================================
            03 — GENERATED CONTROL
            ================================================= */}

        <section className="report-document-section">
          <div className="report-section-number">
            03
          </div>

          <div className="report-section-body">
            <div className="report-section-title">
              <span>
                GENERATED CONTROL
              </span>

              <h2>
                Minimum guardrail
              </h2>
            </div>

            <div className="report-control-layout">
              {/* POLICY */}

              <div className="report-policy-document">
                <div className="report-policy-document__header">
                  <Code2
                    size={15}
                  />

                  GENERATED POLICY
                </div>

                {guardrail ? (
                  <code>
                    <span>
                      policy "
                      {
                        guardrail.guardrail_id
                      }
                      " {"{"}
                    </span>

                    <span>
                      {"  "}
                      sources = [
                      {
                        guardrail.source_labels.join(
                          ", ",
                        )
                      }
                      ]
                    </span>

                    <span>
                      {"  "}
                      destination ={" "}
                      {
                        guardrail.destination
                      }
                    </span>

                    <span className="policy-block">
                      {"  "}
                      action ={" "}
                      {
                        guardrail.action
                      }
                    </span>

                    <span>
                      {"  "}
                      enabled ={" "}
                      {guardrail.enabled
                        ? "true"
                        : "false"}
                    </span>

                    <span>
                      {"}"}
                    </span>
                  </code>
                ) : (
                  <code>
                    <span>
                      Awaiting generated policy
                    </span>
                  </code>
                )}
              </div>

              {/* DETAILS */}

              <div className="report-control-explanation">
                <div>
                  <span>
                    POLICY ID
                  </span>

                  <strong>
                    {guardrail
                      ?.guardrail_id ??
                      "—"}
                  </strong>
                </div>

                <div>
                  <span>
                    GENERATED FROM
                  </span>

                  <strong>
                    {guardrail
                      ?.generated_from_attack ??
                      "—"}
                  </strong>
                </div>

                <div>
                  <span>
                    SCOPE
                  </span>

                  <strong>
                    {guardrail
                      ? `${guardrail.destination} boundary`
                      : "—"}
                  </strong>
                </div>

                <div>
                  <span>
                    ACTION
                  </span>

                  <strong>
                    {guardrail
                      ?.action ??
                      "—"}
                  </strong>
                </div>

                <div>
                  <span>
                    INTERNAL PROCESSING
                  </span>

                  <strong
                    className={
                      legitimateAllowed
                        ? "report-doc-safe"
                        : ""
                    }
                  >
                    {!result
                      ? "—"
                      : legitimateAllowed
                        ? "ALLOWED"
                        : "REVIEW"}
                  </strong>
                </div>
              </div>
            </div>

            <div className="report-callout">
              <ShieldCheck
                size={17}
              />

              <p>
                <strong>
                  Minimum-change enforcement:
                </strong>{" "}

                {guardrail
                  ? guardrail.reason
                  : "AegisTwin will generate the narrowest deterministic control capable of blocking the verified attack."}
              </p>
            </div>
          </div>
        </section>

        {/* =================================================
            04 — REPLAY
            ================================================= */}

        <section className="report-document-section">
          <div className="report-section-number">
            04
          </div>

          <div className="report-section-body">
            <div className="report-section-title">
              <span>
                REPLAY VERIFICATION
              </span>

              <h2>
                Same attack. Different outcome.
              </h2>
            </div>

            <div className="report-before-after">
              {/* BEFORE */}

              <article className="report-before-card">
                <span>
                  BEFORE AEGISTWIN
                </span>

                <h3>
                  {result
                    ? model.replay
                        .asrBefore >
                      0
                      ? "Attack succeeds"
                      : "No attack reproduced"
                    : "Awaiting analysis"}
                </h3>

                <div className="report-ba-state">
                  <XCircle
                    size={29}
                  />

                  <strong>
                    {result &&
                    model.replay
                        .asrBefore >
                      0
                      ? "DATA EXPOSED"
                      : "PENDING"}
                  </strong>
                </div>

                <p>
                  {result
                    ? `Baseline attack success rate: ${model.replay.asrBefore}%.`
                    : "Baseline execution has not yet been tested."}
                </p>
              </article>

              {/* CONTROL */}

              <div className="report-ba-divider">
                <div>
                  <ShieldCheck
                    size={19}
                  />
                </div>

                <span>
                  +{policyCount} POLICY
                </span>
              </div>

              {/* AFTER */}

              <article className="report-after-card">
                <span>
                  AFTER AEGISTWIN
                </span>

                <h3>
                  {!result
                    ? "Awaiting replay"
                    : attackBlocked
                      ? "Attack blocked"
                      : "Review required"}
                </h3>

                <div className="report-ba-state">
                  <CheckCircle2
                    size={29}
                  />

                  <strong>
                    {!result
                      ? "PENDING"
                      : attackBlocked
                        ? "BOUNDARY PROTECTED"
                        : "REVIEW"}
                  </strong>
                </div>

                <p>
                  {result &&
                  attackBlocked &&
                  legitimateAllowed
                    ? "Sensitive lineage is stopped while valid legitimate operations remain available."
                    : "Replay evidence will confirm whether the policy blocks the attack without breaking utility."}
                </p>
              </article>
            </div>
          </div>
        </section>

        {/* =================================================
            05 — REGRESSION
            ================================================= */}

        <section className="report-document-section">
          <div className="report-section-number">
            05
          </div>

          <div className="report-section-body">
            <div className="report-section-title">
              <span>
                REGRESSION EVIDENCE
              </span>

              <h2>
                Security without breaking utility
              </h2>
            </div>

            <table className="report-test-table">
              <thead>
                <tr>
                  <th>
                    Test
                  </th>

                  <th>
                    Expected
                  </th>

                  <th>
                    Result
                  </th>

                  <th>
                    Status
                  </th>
                </tr>
              </thead>

              <tbody>
                {/* MALICIOUS */}

                <tr>
                  <td>
                    {protectedLabel}
                    {" → "}
                    {destination}
                  </td>

                  <td>
                    BLOCK
                  </td>

                  <td>
                    {!result
                      ? "—"
                      : attackBlocked
                        ? "BLOCKED"
                        : "NOT BLOCKED"}
                  </td>

                  <td>
                    <span
                      className={
                        result &&
                        attackBlocked
                          ? "report-table-pass"
                          : "report-table-pending"
                      }
                    >
                      {!result
                        ? "PENDING"
                        : attackBlocked
                          ? "PASS"
                          : "REVIEW"}
                    </span>
                  </td>
                </tr>

                {/* LEGITIMATE */}

                <tr>
                  <td>
                    Legitimate internal workflow
                  </td>

                  <td>
                    ALLOW
                  </td>

                  <td>
                    {!result
                      ? "—"
                      : legitimateAllowed
                        ? "ALLOWED"
                        : "BLOCKED"}
                  </td>

                  <td>
                    <span
                      className={
                        result &&
                        legitimateAllowed
                          ? "report-table-pass"
                          : "report-table-pending"
                      }
                    >
                      {!result
                        ? "PENDING"
                        : legitimateAllowed
                          ? "PASS"
                          : "REVIEW"}
                    </span>
                  </td>
                </tr>

                {/* REGRESSION */}

                <tr>
                  <td>
                    Regression suite
                  </td>

                  <td>
                    PASS
                  </td>

                  <td>
                    {!result
                      ? "—"
                      : regressionPassed
                        ? "PASSED"
                        : "FAILED"}
                  </td>

                  <td>
                    <span
                      className={
                        result &&
                        regressionPassed
                          ? "report-table-pass"
                          : "report-table-pending"
                      }
                    >
                      {!result
                        ? "PENDING"
                        : regressionPassed
                          ? "PASS"
                          : "REVIEW"}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>

            {/* QUALITY METRICS */}

            <div className="report-document-metrics">
              <div>
                <span>
                  FALSE POSITIVES
                </span>

                <strong className="report-doc-safe">
                  {result
                    ? `${model.replay.falsePositiveAfter}%`
                    : "—"}
                </strong>
              </div>

              <div>
                <span>
                  POLICY FRICTION
                </span>

                <strong className="report-doc-safe">
                  {result
                    ? `${model.replay.frictionAfter}%`
                    : "—"}
                </strong>
              </div>

              <div>
                <span>
                  UTILITY AFTER
                </span>

                <strong className="report-doc-safe">
                  {result
                    ? `${model.replay.utilityAfter}%`
                    : "—"}
                </strong>
              </div>

              <div>
                <span>
                  REGRESSION
                </span>

                <strong
                  className={
                    regressionPassed
                      ? "report-doc-safe"
                      : ""
                  }
                >
                  {!result
                    ? "—"
                    : regressionPassed
                      ? "PASSED"
                      : "FAILED"}
                </strong>
              </div>
            </div>
          </div>
        </section>

        {/* =================================================
            06 — TWIN INTELLIGENCE
            ================================================= */}

        <section className="report-document-section">
          <div className="report-section-number">
            06
          </div>

          <div className="report-section-body">
            <div className="report-section-title">
              <span>
                TWIN INTELLIGENCE
              </span>

              <h2>
                Analysis coverage
              </h2>
            </div>

            <div className="report-module-grid">
              {intelligenceModules.map(
                (module) => (
                  <div
                    key={
                      module.name
                    }
                    className={
                      module.complete
                        ? "complete"
                        : ""
                    }
                  >
                    <div>
                      {module.complete ? (
                        <Check
                          size={13}
                        />
                      ) : (
                        <Fingerprint
                          size={13}
                        />
                      )}
                    </div>

                    <span>
                      {module.name}
                    </span>

                    <strong>
                      {
                        module.status
                      }
                    </strong>
                  </div>
                ),
              )}
            </div>

            {/* DRIFT */}

            {result &&
              !model.drift
                .available && (
                <div className="report-callout">
                  <Fingerprint
                    size={17}
                  />

                  <p>
                    <strong>
                      Drift status:
                    </strong>{" "}

                    {model.drift
                      .reason ||
                      "A previous behavioral profile snapshot is required for temporal drift analysis."}
                  </p>
                </div>
              )}
          </div>
        </section>

        {/* =================================================
            07 — LEAST PRIVILEGE
            ================================================= */}

        <section className="report-document-section">
          <div className="report-section-number">
            07
          </div>

          <div className="report-section-body">
            <div className="report-section-title">
              <span>
                LEAST PRIVILEGE
              </span>

              <h2>
                Capability reduction analysis
              </h2>
            </div>

            <div className="report-document-metrics">
              <div>
                <span>
                  TOTAL TOOLS
                </span>

                <strong>
                  {result
                    ? model.leastPrivilege
                        .totalTools
                    : "—"}
                </strong>
              </div>

              <div>
                <span>
                  EXCESS PRIVILEGE
                </span>

                <strong>
                  {result
                    ? model.leastPrivilege
                        .toolsWithExcessPrivilege
                    : "—"}
                </strong>
              </div>

              <div>
                <span>
                  REMOVABLE CAPABILITIES
                </span>

                <strong>
                  {result
                    ? model.leastPrivilege
                        .removableCapabilities
                    : "—"}
                </strong>
              </div>
            </div>
          </div>
        </section>

        {/* =================================================
            08 — RUNTIME AUDIT
            ================================================= */}

        <section className="report-document-section">
          <div className="report-section-number">
            08
          </div>

          <div className="report-section-body">
            <div className="report-section-title">
              <span>
                SECURITY AUDIT
              </span>

              <h2>
                Runtime evidence
              </h2>
            </div>

            <table className="report-document-table">
              <tbody>
                <tr>
                  <th>
                    Receipts
                  </th>

                  <td>
                    {
                      model.runtime
                        .receipts
                    }
                  </td>
                </tr>

                <tr>
                  <th>
                    Decisions
                  </th>

                  <td>
                    {
                      model.runtime
                        .decisions
                    }
                  </td>
                </tr>

                <tr>
                  <th>
                    Pending approvals
                  </th>

                  <td>
                    {
                      model.runtime
                        .pendingApprovals
                    }
                  </td>
                </tr>

                <tr>
                  <th>
                    Runtime sessions
                  </th>

                  <td>
                    {
                      model.runtime
                        .sessionCount
                    }
                  </td>
                </tr>

                <tr>
                  <th>
                    Tool calls
                  </th>

                  <td>
                    {
                      model.runtime
                        .toolCalls
                    }
                  </td>
                </tr>

                <tr>
                  <th>
                    External calls
                  </th>

                  <td>
                    {
                      model.runtime
                        .externalCalls
                    }
                  </td>
                </tr>

                <tr>
                  <th>
                    Estimated cost
                  </th>

                  <td>
                    {
                      model.runtime
                        .estimatedCost
                    }
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* =================================================
            09 — AUDIT TRAIL
            ================================================= */}

        <section className="report-document-section">
          <div className="report-section-number">
            09
          </div>

          <div className="report-section-body">
            <div className="report-section-title">
              <span>
                AUDIT TRAIL
              </span>

              <h2>
                Observe → prove
              </h2>
            </div>

            <div className="report-audit-list">
              {[
                {
                  no: "01",

                  title:
                    "Agent mapped",

                  detail:
                    result
                      ? `${model.twin.totalTools} tools discovered and modeled.`
                      : "Tool discovery is waiting to run.",

                  active:
                    stageIndex >= 0,
                },

                {
                  no: "02",

                  title:
                    "Attack path identified",

                  detail:
                    result
                      ? `${model.twin.attackPaths} verified attack path(s) identified.`
                      : "Attack path discovery pending.",

                  active:
                    stageIndex >= 1,
                },

                {
                  no: "03",

                  title:
                    "Guardrail compiled",

                  detail:
                    guardrail
                      ? `${guardrail.guardrail_id}: ${guardrail.action} at ${guardrail.destination}.`
                      : "Minimum runtime control waiting for compilation.",

                  active:
                    stageIndex >=
                      2 &&
                    Boolean(
                      guardrail,
                    ),
                },

                {
                  no: "04",

                  title:
                    "Attack replayed",

                  detail:
                    attackBlocked
                      ? "The original malicious execution was blocked after enforcement."
                      : "Replay evidence pending.",

                  active:
                    stageIndex >= 3,
                },

                {
                  no: "05",

                  title:
                    "Security verified",

                  detail:
                    verified
                      ? "Attack blocked with legitimate utility preserved and regression checks passed."
                      : "Final verification pending.",

                  active:
                    verified,
                },
              ].map(
                (item) => (
                  <div
                    className={`report-audit-item ${
                      item.active
                        ? "complete"
                        : ""
                    }`}
                    key={
                      item.no
                    }
                  >
                    <div className="report-audit-index">
                      {item.active ? (
                        <Check
                          size={12}
                        />
                      ) : (
                        item.no
                      )}
                    </div>

                    <div>
                      <span>
                        STEP{" "}
                        {
                          item.no
                        }
                      </span>

                      <strong>
                        {
                          item.title
                        }
                      </strong>

                      <p>
                        {
                          item.detail
                        }
                      </p>
                    </div>
                  </div>
                ),
              )}
            </div>
          </div>
        </section>

        {/* =================================================
            ERROR
            ================================================= */}

        {stage === "error" && (
          <div className="report-document-error">
            <TriangleAlert
              size={17}
            />

            <div>
              <strong>
                Analysis error
              </strong>

              <span>
                {error ||
                  "Unknown backend error"}
              </span>
            </div>
          </div>
        )}

        {/* =================================================
            SIGN OFF
            ================================================= */}

        <footer className="report-document-footer">
          <div>
            <FileCheck2
              size={18}
            />

            <div>
              <span>
                GENERATED BY
              </span>

              <strong>
                AegisTwin Security
                Digital Twin
              </strong>
            </div>
          </div>

          <div className="report-document-signature">
            <span>
              REPORT STATUS
            </span>

            <strong>
              {verified
                ? "VERIFIED"
                : result
                  ? "ANALYZED"
                  : "DRAFT"}
            </strong>
          </div>

          <div className="report-document-page">
            AEGISTWIN · SECURITY EVIDENCE
          </div>
        </footer>
      </div>
    </section>
  );
}