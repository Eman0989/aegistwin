import {
  ArrowRight,
  Check,
  CheckCircle2,
  Database,
  FileText,
  Globe2,
  LoaderCircle,
  LockKeyhole,
  Play,
  RefreshCcw,
  ShieldCheck,
  Terminal,
  XCircle,
} from "lucide-react";

import type {
  AttackResponse,
} from "../../lib/api";

import {
  getAttackToolPath,
  getGeneratedGuardrail,
  getPrimaryAttackPath,
  getReplayMetrics,
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

interface ReplayViewProps {
  stage: AttackStage;

  stageIndex: number;

  isRunning: boolean;

  onRunAttack: () => void;

  result:
    | AttackResponse
    | null;
}

/* =========================================================
   FALLBACK PATH
   ========================================================= */

const fallbackPath = [
  "invoice_reader",
  "customer_database",
  "summarizer",
  "external_http",
];

/* =========================================================
   HELPERS
   ========================================================= */

function getToolIcon(
  toolName: string,
  blocked = false,
) {
  if (
    blocked &&
    toolName.includes("external")
  ) {
    return (
      <ShieldCheck size={18} />
    );
  }

  if (
    toolName.includes("external")
  ) {
    return (
      <Globe2 size={18} />
    );
  }

  if (
    toolName.includes("database")
  ) {
    return (
      <Database size={18} />
    );
  }

  if (
    toolName.includes("invoice")
  ) {
    return (
      <FileText size={18} />
    );
  }

  return (
    <Terminal size={18} />
  );
}

function getToolType(
  toolName: string,
) {
  if (
    toolName.includes("external")
  ) {
    return "EXTERNAL";
  }

  if (
    toolName.includes("database")
  ) {
    return "SENSITIVE";
  }

  if (
    toolName.includes("summarizer")
  ) {
    return "TRANSFORM";
  }

  return "INPUT";
}

/* =========================================================
   COMPONENT
   ========================================================= */

export default function ReplayView({
  stage,
  stageIndex,
  isRunning,
  onRunAttack,
  result,
}: ReplayViewProps) {
  /* =======================================================
     STATE
     ======================================================= */

  const compiled =
    stageIndex >= 2;

  const replaying =
    stage === "replay";

  const verified =
    stage === "complete";

  /* =======================================================
     REAL BACKEND DATA
     ======================================================= */

  const attack =
    getPrimaryAttackPath(
      result,
    );

  const guardrail =
    getGeneratedGuardrail(
      result,
    );

  const replay =
    getReplayMetrics(
      result,
    );

  const discoveredPath =
    getAttackToolPath(
      result,
    );

  const attackPath =
    discoveredPath.length > 0
      ? discoveredPath
      : fallbackPath;

  const benchmarkCases =
    result?.benchmark_report
      ?.cases ?? [];

  const beforeMalicious =
    benchmarkCases.find(
      (item) =>
        item.phase === "before" &&
        item.scenario === "malicious",
    );

  const afterMalicious =
    benchmarkCases.find(
      (item) =>
        item.phase === "after" &&
        item.scenario === "malicious",
    );

  const afterLegitimate =
    benchmarkCases.find(
      (item) =>
        item.phase === "after" &&
        item.scenario === "legitimate",
    );

  const beforeLegitimate =
    benchmarkCases.find(
      (item) =>
        item.phase === "before" &&
        item.scenario === "legitimate",
    );

  const attackBlocked =
    replay
      .maliciousBlockedAfter;

  const legitimateAllowed =
    replay
      .legitimateAllowedAfter;

  const attackId =
    attack?.attack_id ??
    "ATK-001";

  const destination =
    attack?.destination ??
    guardrail?.destination ??
    "EXTERNAL";

  const origin =
    attack
      ?.instruction_origin ??
    "WEB_UNTRUSTED";

  const sensitiveLabels =
    attack?.source_labels ??
    guardrail?.source_labels ??
    [];

  const primarySensitiveLabel =
    sensitiveLabels.find(
      (label) =>
        !label.startsWith(
          "DerivedFrom",
        ),
    ) ??
    sensitiveLabels[0] ??
    "CustomerPII";

  const derivedLabel =
    sensitiveLabels.find(
      (label) =>
        label.startsWith(
          "DerivedFrom",
        ),
    ) ??
    "DerivedFrom<CustomerPII>";

  const policyCount =
    guardrail ? 1 : 0;

  const attackSucceededBefore =
    Boolean(
      beforeMalicious
        ?.attack_success,
    );

  const attackBlockedAfter =
    Boolean(
      afterMalicious
        ?.blocked,
    ) ||
    attackBlocked;

  const legitimateSucceededAfter =
    Boolean(
      afterLegitimate
        ?.allowed,
    ) ||
    legitimateAllowed;

  const regressionPassed =
    Boolean(
      result
        ?.benchmark_report
        ?.regression_suite_passed,
    ) ||
    Boolean(
      result
        ?.regression_passed,
    );

  /* =======================================================
     RENDER FLOW NODE
     ======================================================= */

  const renderFlow = (
    guarded: boolean,
  ) =>
    attackPath.map(
      (
        toolName,
        index,
      ) => {
        const last =
          index ===
          attackPath.length - 1;

        const blocked =
          guarded &&
          last &&
          stageIndex >= 3;

        let subtitle =
          "observed";

        if (index === 0) {
          subtitle =
            origin;
        }

        if (
          toolName.includes(
            "database",
          )
        ) {
          subtitle =
            primarySensitiveLabel;
        }

        if (
          toolName.includes(
            "summarizer",
          )
        ) {
          subtitle =
            derivedLabel;
        }

        if (last) {
          subtitle =
            blocked
              ? "BLOCKED"
              : destination;
        }

        return (
          <>
            <div
              key={`node-${guarded}-${toolName}-${index}`}
              className={
                guarded
                  ? `replay-node ${
                      blocked
                        ? "replay-node--blocked"
                        : stageIndex >=
                            (index === 0
                              ? 0
                              : 1)
                          ? "replay-node--active"
                          : ""
                    }`
                  : last
                    ? "replay-node replay-node--breach"
                    : index > 0
                      ? "replay-node replay-node--danger"
                      : "replay-node"
              }
            >
              <div className="replay-node-icon">
                {getToolIcon(
                  toolName,
                  blocked,
                )}
              </div>

              <span>
                {getToolType(
                  toolName,
                )}
              </span>

              <strong>
                {toolName}
              </strong>

              <small>
                {subtitle}
              </small>
            </div>

            {index <
              attackPath.length -
                1 && (
              <ArrowRight
                key={`arrow-${guarded}-${index}`}
                size={18}
                className={
                  guarded
                    ? stageIndex >= 3 &&
                      index ===
                        attackPath.length -
                          2
                      ? "replay-arrow replay-arrow--blocked"
                      : stageIndex >= 1
                        ? "replay-arrow replay-arrow--active"
                        : "replay-arrow"
                    : "replay-arrow replay-arrow--danger"
                }
              />
            )}
          </>
        );
      },
    );

  /* =======================================================
     RENDER
     ======================================================= */

  return (
    <section className="replay-page">
      {/* ===================================================
          HEADER
          =================================================== */}

      <div className="replay-header">
        <div>
          <span className="console-kicker">
            EXECUTION REPLAY
          </span>

          <h2>
            Before vs After
          </h2>

          <p>
            Replay the exact same malicious execution
            before and after AegisTwin enforcement to prove
            that the attack is stopped without disabling
            legitimate agent behavior.
          </p>
        </div>

        <button
          type="button"
          className={`replay-run-button ${
            isRunning
              ? "running"
              : ""
          }`}
          onClick={
            onRunAttack
          }
          disabled={
            isRunning
          }
        >
          {isRunning ? (
            <LoaderCircle
              size={17}
              className="attack-spinner"
            />
          ) : verified ? (
            <RefreshCcw
              size={17}
            />
          ) : (
            <Play
              size={17}
            />
          )}

          <span>
            {isRunning
              ? "REPLAYING EXECUTION"
              : verified
                ? "REPLAY AGAIN"
                : "RUN REPLAY"}
          </span>
        </button>
      </div>

      {/* ===================================================
          REPLAY SUMMARY
          =================================================== */}

      <div className="replay-summary">
        {/* SCENARIO */}

        <div>
          <span>
            SCENARIO
          </span>

          <strong>
            {result
              ? attackId
              : "PENDING"}
          </strong>

          <small>
            Sensitive data exfiltration
          </small>
        </div>

        {/* INPUT */}

        <div>
          <span>
            SAME INPUT
          </span>

          <strong>
            {result
              ? origin
              : "—"}
          </strong>

          <small>
            Controlled replay
          </small>
        </div>

        {/* POLICY */}

        <div>
          <span>
            POLICY CHANGE
          </span>

          <strong>
            {result
              ? policyCount
              : "—"}
          </strong>

          <small>
            Minimum guardrail
          </small>
        </div>

        {/* RESULT */}

        <div>
          <span>
            FINAL RESULT
          </span>

          <strong
            className={
              verified &&
              attackBlockedAfter
                ? "replay-safe"
                : ""
            }
          >
            {!verified
              ? "PENDING"
              : attackBlockedAfter
                ? "ATTACK BLOCKED"
                : "REVIEW"}
          </strong>

          <small>
            {!verified
              ? "Awaiting replay"
              : legitimateSucceededAfter
                ? "Utility preserved"
                : "Utility requires review"}
          </small>
        </div>
      </div>

      {/* ===================================================
          BEFORE / AFTER
          =================================================== */}

      <div className="replay-comparison">
        {/* =================================================
            BEFORE
            ================================================= */}

        <article className="replay-lane replay-lane--before">
          <div className="replay-lane-header">
            <div>
              <span>
                BEFORE AEGISTWIN
              </span>

              <h3>
                Unguarded execution
              </h3>
            </div>

            <div className="replay-danger-badge">
              {result &&
              attackSucceededBefore
                ? "VULNERABLE"
                : "BASELINE"}
            </div>
          </div>

          {/* REAL PATH */}

          <div className="replay-flow">
            {renderFlow(
              false,
            )}
          </div>

          {/* OUTCOME */}

          <div className="replay-outcome replay-outcome--danger">
            <XCircle
              size={19}
            />

            <div>
              <span>
                OUTCOME
              </span>

              <strong>
                {result
                  ? attackSucceededBefore
                    ? "Attack succeeds"
                    : "Attack not reproduced"
                  : "Awaiting benchmark"}
              </strong>

              <p>
                {result &&
                attackSucceededBefore
                  ? `Sensitive lineage reaches the ${destination} trust boundary before protection.`
                  : "The baseline malicious execution is evaluated before guardrail enforcement."}
              </p>
            </div>
          </div>
        </article>

        {/* =================================================
            CENTER POLICY DIFFERENCE
            ================================================= */}

        <div className="replay-difference">
          <div
            className={`replay-policy-chip ${
              compiled &&
              guardrail
                ? "active"
                : ""
            }`}
          >
            <LockKeyhole
              size={16}
            />

            <span>
              AEGISTWIN
            </span>

            <strong>
              +{policyCount} GUARDRAIL
            </strong>
          </div>

          <div className="replay-difference-line" />

          <code>
            {guardrail ? (
              <>
                {guardrail.source_labels.join(
                  " / ",
                )}

                <br />

                →{" "}
                {
                  guardrail.destination
                }

                <br />

                ={" "}
                {
                  guardrail.action
                }
              </>
            ) : (
              <>
                Awaiting
                <br />
                compiled
                <br />
                policy
              </>
            )}
          </code>
        </div>

        {/* =================================================
            AFTER
            ================================================= */}

        <article className="replay-lane replay-lane--after">
          <div className="replay-lane-header">
            <div>
              <span>
                AFTER AEGISTWIN
              </span>

              <h3>
                Guarded execution
              </h3>
            </div>

            <div
              className={`replay-safe-badge ${
                verified &&
                attackBlockedAfter
                  ? "active"
                  : ""
              }`}
            >
              {verified
                ? attackBlockedAfter
                  ? "VERIFIED"
                  : "REVIEW"
                : "READY"}
            </div>
          </div>

          {/* REAL PATH */}

          <div className="replay-flow">
            {renderFlow(
              true,
            )}
          </div>

          {/* OUTCOME */}

          <div
            className={`replay-outcome ${
              verified &&
              attackBlockedAfter
                ? "replay-outcome--safe"
                : ""
            }`}
          >
            {verified &&
            attackBlockedAfter ? (
              <CheckCircle2
                size={19}
              />
            ) : replaying ? (
              <LoaderCircle
                size={19}
                className="attack-spinner"
              />
            ) : (
              <ShieldCheck
                size={19}
              />
            )}

            <div>
              <span>
                OUTCOME
              </span>

              <strong>
                {verified
                  ? attackBlockedAfter
                    ? "Attack blocked"
                    : "Replay requires review"
                  : replaying
                    ? "Replaying attack"
                    : "Awaiting verification"}
              </strong>

              <p>
                {verified &&
                attackBlockedAfter
                  ? `Sensitive lineage is stopped at the ${destination} boundary.`
                  : "Run the replay to validate the compiled control."}
              </p>
            </div>
          </div>
        </article>
      </div>

      {/* ===================================================
          REGRESSION PROOF
          =================================================== */}

      <div className="replay-utility-panel">
        <div className="replay-utility-header">
          <div>
            <span>
              REGRESSION PROOF
            </span>

            <h3>
              Did security break the agent?
            </h3>
          </div>

          {verified &&
            regressionPassed && (
              <div className="replay-proof-badge">
                <Check
                  size={13}
                />

                NO REGRESSION
              </div>
            )}
        </div>

        <div className="replay-test-grid">
          {/* ===============================================
              MALICIOUS EXECUTION
              =============================================== */}

          <div className="replay-test-card replay-test-card--attack">
            <div className="replay-test-number">
              01
            </div>

            <div className="replay-test-content">
              <span>
                MALICIOUS EXECUTION
              </span>

              <strong>
                Send{" "}
                {
                  primarySensitiveLabel
                }{" "}
                externally
              </strong>

              <div>
                Expected:{" "}
                {
                  guardrail
                    ?.action ??
                  "BLOCK"
                }
              </div>
            </div>

            <div
              className={
                verified &&
                attackBlockedAfter
                  ? "replay-test-status blocked"
                  : "replay-test-status"
              }
            >
              {verified ? (
                attackBlockedAfter ? (
                  <>
                    <XCircle
                      size={14}
                    />

                    BLOCKED
                  </>
                ) : (
                  "REVIEW"
                )
              ) : (
                "PENDING"
              )}
            </div>
          </div>

          {/* ===============================================
              LEGITIMATE EXECUTION
              =============================================== */}

          <div className="replay-test-card replay-test-card--safe">
            <div className="replay-test-number">
              02
            </div>

            <div className="replay-test-content">
              <span>
                LEGITIMATE EXECUTION
              </span>

              <strong>
                Generate internal invoice summary
              </strong>

              <div>
                Expected: ALLOW
              </div>
            </div>

            <div
              className={
                verified &&
                legitimateSucceededAfter
                  ? "replay-test-status allowed"
                  : "replay-test-status"
              }
            >
              {verified ? (
                legitimateSucceededAfter ? (
                  <>
                    <CheckCircle2
                      size={14}
                    />

                    ALLOWED
                  </>
                ) : (
                  "REVIEW"
                )
              ) : (
                "PENDING"
              )}
            </div>
          </div>

          {/* ===============================================
              REGRESSION SUITE
              =============================================== */}

          <div className="replay-test-card replay-test-card--safe">
            <div className="replay-test-number">
              03
            </div>

            <div className="replay-test-content">
              <span>
                REGRESSION SUITE
              </span>

              <strong>
                Preserve legitimate behavior
              </strong>

              <div>
                Expected: PASS
              </div>
            </div>

            <div
              className={
                verified &&
                regressionPassed
                  ? "replay-test-status allowed"
                  : "replay-test-status"
              }
            >
              {verified ? (
                regressionPassed ? (
                  <>
                    <CheckCircle2
                      size={14}
                    />

                    PASSED
                  </>
                ) : (
                  "REVIEW"
                )
              ) : (
                "PENDING"
              )}
            </div>
          </div>
        </div>

        {/* =================================================
            BENCHMARK EVIDENCE
            ================================================= */}

        {result && (
          <div className="attack-evidence-section">
            <span className="attack-evidence-label">
              BENCHMARK EVIDENCE
            </span>

            <div className="attack-evidence-row">
              <span>
                Before malicious
              </span>

              <strong>
                {beforeMalicious
                  ?.attack_success
                  ? "SUCCESS"
                  : "FAILED"}
              </strong>
            </div>

            <div className="attack-evidence-row">
              <span>
                After malicious
              </span>

              <strong>
                {afterMalicious
                  ?.blocked
                  ? "BLOCKED"
                  : "NOT BLOCKED"}
              </strong>
            </div>

            <div className="attack-evidence-row">
              <span>
                Before legitimate
              </span>

              <strong>
                {beforeLegitimate
                  ?.allowed
                  ? "ALLOWED"
                  : "BLOCKED"}
              </strong>
            </div>

            <div className="attack-evidence-row">
              <span>
                After legitimate
              </span>

              <strong>
                {afterLegitimate
                  ?.allowed
                  ? "ALLOWED"
                  : "BLOCKED"}
              </strong>
            </div>
          </div>
        )}
      </div>

      {/* ===================================================
          FINAL REAL METRICS
          =================================================== */}

      <div className="replay-final-metrics">
        {/* ASR */}

        <article>
          <span>
            ATTACK SUCCESS RATE
          </span>

          <div>
            <strong className="metric-before">
              {result
                ? `${replay.asrBefore}%`
                : "—"}
            </strong>

            <ArrowRight
              size={16}
            />

            <strong
              className={
                verified
                  ? "metric-after"
                  : ""
              }
            >
              {result
                ? `${replay.asrAfter}%`
                : "—"}
            </strong>
          </div>

          <small>
            Attack effectiveness
          </small>
        </article>

        {/* UTILITY */}

        <article>
          <span>
            LEGITIMATE UTILITY
          </span>

          <div>
            <strong>
              {result
                ? `${replay.utilityBefore}%`
                : "—"}
            </strong>

            <ArrowRight
              size={16}
            />

            <strong
              className={
                verified
                  ? "metric-after"
                  : ""
              }
            >
              {result
                ? `${replay.utilityAfter}%`
                : "—"}
            </strong>
          </div>

          <small>
            Normal work preserved
          </small>
        </article>

        {/* FALSE POSITIVES */}

        <article>
          <span>
            FALSE POSITIVES
          </span>

          <div>
            <strong
              className={
                verified
                  ? "metric-after"
                  : ""
              }
            >
              {result
                ? `${replay.falsePositiveAfter}%`
                : "—"}
            </strong>
          </div>

          <small>
            Unnecessary blocks
          </small>
        </article>

        {/* FRICTION */}

        <article>
          <span>
            POLICY FRICTION
          </span>

          <div>
            <strong
              className={
                verified
                  ? "metric-after"
                  : ""
              }
            >
              {result
                ? `${replay.frictionAfter}%`
                : "—"}
            </strong>
          </div>

          <small>
            Additional denied flows
          </small>
        </article>
      </div>
    </section>
  );
}