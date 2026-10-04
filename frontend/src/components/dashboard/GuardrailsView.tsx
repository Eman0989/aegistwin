import {
  ArrowRight,
  Check,
  CheckCircle2,
  Code2,
  Database,
  GitBranch,
  Globe2,
  LoaderCircle,
  LockKeyhole,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  XCircle,
} from "lucide-react";

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

interface GuardrailsViewProps {
  stage: AttackStage;

  stageIndex: number;

  isRunning: boolean;

  onRunAttack: () => void;

  model: ConsoleModel;
}

/* =========================================================
   COMPONENT
   ========================================================= */

export default function GuardrailsView({
  stage,
  stageIndex,
  isRunning,
  onRunAttack,
  model,
}: GuardrailsViewProps) {
  /* =======================================================
     REAL BACKEND GUARDRAIL
     ======================================================= */

  const guardrail =
    model.guardrail.data;

  const sourceLabels =
    guardrail?.source_labels ??
    [];

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

  const destination =
    guardrail?.destination ??
    "EXTERNAL";

  const action =
    guardrail?.action ??
    "BLOCK";

  const guardrailId =
    guardrail?.guardrail_id ??
    "AWAITING";

  const guardrailReason =
    guardrail?.reason ??
    "AegisTwin will generate the minimum control after attack analysis.";

  const generatedFrom =
    guardrail
      ?.generated_from_attack ??
    "—";

  /* =======================================================
     PIPELINE STATE
     ======================================================= */

  const compiled =
    stageIndex >= 2 &&
    Boolean(guardrail);

  const replayed =
    stageIndex >= 3 &&
    Boolean(guardrail);

  const verified =
    stage === "complete" &&
    model.replay.regressionPassed;

  const policyEnabled =
    Boolean(
      guardrail?.enabled,
    );

  const attackBlocked =
    model.replay
      .maliciousBlockedAfter;

  const legitimateAllowed =
    model.replay
      .legitimateAllowedAfter;

  /* =======================================================
     POLICY CODE LABELS
     ======================================================= */

  const policyName =
    guardrailId !== "AWAITING"
      ? guardrailId
      : "pending-policy";

  /* =======================================================
     RENDER
     ======================================================= */

  return (
    <section className="guardrails-page">
      {/* ===================================================
          HERO HEADER
          =================================================== */}

      <div className="guardrails-header">
        <div className="guardrails-header__copy">
          <span className="console-kicker">
            POLICY COMPILER
          </span>

          <h2>
            Minimum Guardrail Engine
          </h2>

          <p>
            Convert discovered attack paths into targeted
            runtime controls without disabling legitimate
            agent capabilities.
          </p>
        </div>

        <button
          type="button"
          className={`guardrail-generate-btn ${
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
            <CheckCircle2
              size={17}
            />
          ) : (
            <Sparkles
              size={17}
            />
          )}

          <span>
            {isRunning
              ? "COMPILING CONTROL"
              : verified
                ? "RECOMPILE & VERIFY"
                : "GENERATE GUARDRAIL"}
          </span>
        </button>
      </div>

      {/* ===================================================
          COMPILER STATUS
          =================================================== */}

      <div className="guardrail-status-strip">
        {/* ATTACK PATH */}

        <div
          className={`guardrail-status-item ${
            stageIndex >= 0
              ? "done"
              : ""
          }`}
        >
          <div>
            <ScanSearch
              size={15}
            />
          </div>

          <span>
            ATTACK PATH
          </span>

          <strong>
            {stageIndex >= 0
              ? "DISCOVERED"
              : "WAITING"}
          </strong>
        </div>

        <ArrowRight
          className="guardrail-status-arrow"
          size={15}
        />

        {/* LINEAGE */}

        <div
          className={`guardrail-status-item ${
            stageIndex >= 1
              ? "done"
              : ""
          }`}
        >
          <div>
            <GitBranch
              size={15}
            />
          </div>

          <span>
            DATA LINEAGE
          </span>

          <strong>
            {stageIndex >= 1
              ? "TRACED"
              : "WAITING"}
          </strong>
        </div>

        <ArrowRight
          className="guardrail-status-arrow"
          size={15}
        />

        {/* POLICY */}

        <div
          className={`guardrail-status-item ${
            compiled
              ? "gold"
              : ""
          }`}
        >
          <div>
            <Code2 size={15} />
          </div>

          <span>
            POLICY
          </span>

          <strong>
            {compiled
              ? "COMPILED"
              : "WAITING"}
          </strong>
        </div>

        <ArrowRight
          className="guardrail-status-arrow"
          size={15}
        />

        {/* ENFORCEMENT */}

        <div
          className={`guardrail-status-item ${
            verified
              ? "verified"
              : ""
          }`}
        >
          <div>
            <ShieldCheck
              size={15}
            />
          </div>

          <span>
            ENFORCEMENT
          </span>

          <strong>
            {verified
              ? "VERIFIED"
              : replayed
                ? "TESTING"
                : "WAITING"}
          </strong>
        </div>
      </div>

      {/* ===================================================
          MAIN GRID
          =================================================== */}

      <div className="guardrails-main-grid">
        {/* =================================================
            LEFT — POLICY COMPILER
            ================================================= */}

        <div className="guardrail-compiler">
          {/* HEADER */}

          <div className="guardrail-panel-header">
            <div>
              <span>
                GENERATED CONTROL
              </span>

              <h3>
                Compiled security policy
              </h3>
            </div>

            <div
              className={`guardrail-compiler-state ${
                compiled
                  ? "ready"
                  : ""
              }`}
            >
              {compiled
                ? policyEnabled
                  ? "COMPILED · ACTIVE"
                  : "COMPILED"
                : "AWAITING ANALYSIS"}
            </div>
          </div>

          {/* =================================================
              POLICY CODE
              ================================================= */}

          <div className="guardrail-code-area">
            <div className="guardrail-code-toolbar">
              <div>
                <span />
                <span />
                <span />
              </div>

              <strong>
                aegistwin.policy
              </strong>

              <small>
                {compiled
                  ? guardrailId
                  : "generated"}
              </small>
            </div>

            {compiled &&
            guardrail ? (
              <div className="guardrail-code">
                {/* LINE 01 */}

                <div>
                  <span className="guardrail-line-number">
                    01
                  </span>

                  <code>
                    policy{" "}

                    <b>
                      "
                      {
                        policyName
                      }
                      "
                    </b>{" "}

                    {"{"}
                  </code>
                </div>

                {/* LINE 02 */}

                <div>
                  <span className="guardrail-line-number">
                    02
                  </span>

                  <code>
                    {"  "}
                    sources = [

                    {sourceLabels.map(
                      (
                        label,
                        index,
                      ) => (
                        <span
                          key={
                            label
                          }
                        >
                          <em>
                            "
                            {
                              label
                            }
                            "
                          </em>

                          {index <
                            sourceLabels.length -
                              1
                            ? ", "
                            : ""}
                        </span>
                      ),
                    )}

                    ]
                  </code>
                </div>

                {/* LINE 03 */}

                <div>
                  <span className="guardrail-line-number">
                    03
                  </span>

                  <code>
                    {"  "}
                    destination ={" "}

                    <strong>
                      {
                        destination
                      }
                    </strong>
                  </code>
                </div>

                {/* LINE 04 */}

                <div>
                  <span className="guardrail-line-number">
                    04
                  </span>

                  <code>
                    {"  "}
                    action ={" "}

                    <mark>
                      {action}
                    </mark>
                  </code>
                </div>

                {/* LINE 05 */}

                <div>
                  <span className="guardrail-line-number">
                    05
                  </span>

                  <code>
                    {"  "}
                    generated_from ={" "}

                    <em>
                      "
                      {
                        generatedFrom
                      }
                      "
                    </em>
                  </code>
                </div>

                {/* LINE 06 */}

                <div>
                  <span className="guardrail-line-number">
                    06
                  </span>

                  <code>
                    {"  "}
                    enabled ={" "}

                    <strong>
                      {policyEnabled
                        ? "true"
                        : "false"}
                    </strong>
                  </code>
                </div>

                {/* LINE 07 */}

                <div>
                  <span className="guardrail-line-number">
                    07
                  </span>

                  <code>
                    {"}"}
                  </code>
                </div>
              </div>
            ) : (
              <div className="guardrail-code-empty">
                <Code2
                  size={30}
                />

                <strong>
                  No policy compiled yet
                </strong>

                <span>
                  Run AegisTwin analysis to generate
                  the minimum required control.
                </span>
              </div>
            )}
          </div>

          {/* =================================================
              WHY THIS POLICY
              ================================================= */}

          <div className="guardrail-reasoning">
            <div className="guardrail-reasoning-title">
              <Sparkles
                size={15}
              />

              WHY AEGISTWIN GENERATED THIS CONTROL
            </div>

            <div className="guardrail-reasoning-grid">
              {/* PROVENANCE */}

              <div>
                <span className="guardrail-reasoning-index">
                  01
                </span>

                <section>
                  <small>
                    PROVENANCE
                  </small>

                  <strong>
                    {model.provenance
                      .untrusted
                      ? "Untrusted input detected"
                      : "Provenance evaluated"}
                  </strong>

                  <p>
                    {model.provenance
                      .origin
                      ? `Execution origin: ${model.provenance.origin}. Risk: ${model.provenance.risk}.`
                      : "Waiting for provenance analysis."}
                  </p>
                </section>
              </div>

              {/* SENSITIVE DATA */}

              <div>
                <span className="guardrail-reasoning-index">
                  02
                </span>

                <section>
                  <small>
                    SENSITIVE DATA
                  </small>

                  <strong>
                    {compiled
                      ? `${protectedLabel} identified`
                      : "Awaiting classification"}
                  </strong>

                  <p>
                    {compiled
                      ? `${protectedLabel} appears on the verified attack path.`
                      : "Sensitive data classification will be evaluated during analysis."}
                  </p>
                </section>
              </div>

              {/* LINEAGE */}

              <div>
                <span className="guardrail-reasoning-index">
                  03
                </span>

                <section>
                  <small>
                    LINEAGE
                  </small>

                  <strong>
                    {compiled
                      ? "Sensitivity survives transformation"
                      : "Awaiting lineage"}
                  </strong>

                  <p>
                    {compiled
                      ? `${derivedLabel} remains protected even after transformation.`
                      : "AegisTwin will trace sensitive labels across tool outputs."}
                  </p>
                </section>
              </div>

              {/* INTENT */}

              <div>
                <span className="guardrail-reasoning-index">
                  04
                </span>

                <section>
                  <small>
                    INTENT
                  </small>

                  <strong>
                    {model.intent
                      .mismatchFound
                      ? "External action is unexpected"
                      : "Intent awaiting evaluation"}
                  </strong>

                  <p>
                    {model.intent
                      .mismatchFound
                      ? model.intent
                          .mismatchReason
                      : model.intent
                          .originalIntent
                        ? `Original request: ${model.intent.originalIntent}`
                        : "AegisTwin compares requested intent against observed actions."}
                  </p>
                </section>
              </div>
            </div>

            {/* REAL BACKEND REASON */}

            {compiled && (
              <div className="privilege-copy">
                <strong>
                  Compiler reason:{" "}
                </strong>

                {
                  guardrailReason
                }
              </div>
            )}
          </div>
        </div>

        {/* =================================================
            RIGHT SIDE
            ================================================= */}

        <aside className="guardrail-side-panel">
          {/* ===============================================
              MINIMUM CHANGE
              =============================================== */}

          <div className="guardrail-side-section">
            <div className="guardrail-side-title">
              <LockKeyhole
                size={15}
              />

              MINIMUM CHANGE
            </div>

            <div className="minimum-control-card">
              {/* BEFORE */}

              <span>
                BEFORE
              </span>

              <div className="minimum-control-route">
                <Database
                  size={15}
                />

                <strong>
                  {compiled
                    ? protectedLabel
                    : "Sensitive data"}
                </strong>

                <ArrowRight
                  size={13}
                />

                <Globe2
                  size={15}
                />

                <strong>
                  {compiled
                    ? destination
                    : "EXTERNAL"}
                </strong>
              </div>

              <div className="minimum-control-divider" />

              {/* AFTER */}

              <span>
                AFTER
              </span>

              <div className="minimum-control-route guarded">
                <Database
                  size={15}
                />

                <strong>
                  {compiled
                    ? protectedLabel
                    : "Sensitive data"}
                </strong>

                <ArrowRight
                  size={13}
                />

                <ShieldCheck
                  size={15}
                />

                <strong>
                  {compiled
                    ? action
                    : "PENDING"}
                </strong>
              </div>
            </div>

            <p className="minimum-control-copy">
              {compiled
                ? `No tool is globally disabled. Only ${sourceLabels.join(
                    " / ",
                  )} crossing the ${destination} trust boundary is ${action.toLowerCase()}.`
                : "AegisTwin searches for the smallest control that blocks the verified attack while preserving normal work."}
            </p>
          </div>

          {/* ===============================================
              POLICY SCOPE
              =============================================== */}

          <div className="guardrail-side-section">
            <div className="guardrail-side-title">
              <GitBranch
                size={15}
              />

              POLICY SCOPE
            </div>

            <div className="guardrail-scope-row">
              <span>
                Policy ID
              </span>

              <strong>
                {compiled
                  ? guardrailId
                  : "—"}
              </strong>
            </div>

            <div className="guardrail-scope-row">
              <span>
                Protected class
              </span>

              <strong>
                {compiled
                  ? protectedLabel
                  : "—"}
              </strong>
            </div>

            <div className="guardrail-scope-row">
              <span>
                Derived data
              </span>

              <strong>
                {compiled &&
                sourceLabels.some(
                  (label) =>
                    label.startsWith(
                      "DerivedFrom",
                    ),
                )
                  ? "INCLUDED"
                  : "—"}
              </strong>
            </div>

            <div className="guardrail-scope-row">
              <span>
                Boundary
              </span>

              <strong>
                {compiled
                  ? destination
                  : "—"}
              </strong>
            </div>

            <div className="guardrail-scope-row">
              <span>
                Internal processing
              </span>

              <strong
                className={
                  verified &&
                  legitimateAllowed
                    ? "guardrail-allowed"
                    : ""
                }
              >
                {!verified
                  ? "PENDING"
                  : legitimateAllowed
                    ? "ALLOWED"
                    : "REVIEW"}
              </strong>
            </div>
          </div>

          {/* ===============================================
              ENFORCEMENT
              =============================================== */}

          <div className="guardrail-side-section">
            <div className="guardrail-side-title">
              <ShieldCheck
                size={15}
              />

              ENFORCEMENT
            </div>

            <div className="guardrail-enforcement">
              {/* COMPILED */}

              <div
                className={
                  compiled
                    ? "active"
                    : ""
                }
              >
                <span>
                  Policy compiled
                </span>

                {compiled ? (
                  <Check
                    size={13}
                  />
                ) : (
                  <span className="guardrail-wait-dot" />
                )}
              </div>

              {/* ENABLED */}

              <div
                className={
                  policyEnabled
                    ? "active"
                    : ""
                }
              >
                <span>
                  Policy enabled
                </span>

                {policyEnabled ? (
                  <Check
                    size={13}
                  />
                ) : (
                  <span className="guardrail-wait-dot" />
                )}
              </div>

              {/* RUNTIME */}

              <div
                className={
                  replayed
                    ? "active"
                    : ""
                }
              >
                <span>
                  Runtime applied
                </span>

                {replayed ? (
                  <Check
                    size={13}
                  />
                ) : (
                  <span className="guardrail-wait-dot" />
                )}
              </div>

              {/* REGRESSION */}

              <div
                className={
                  verified
                    ? "active"
                    : ""
                }
              >
                <span>
                  Regression verified
                </span>

                {verified ? (
                  <Check
                    size={13}
                  />
                ) : (
                  <span className="guardrail-wait-dot" />
                )}
              </div>
            </div>
          </div>
        </aside>
      </div>

      {/* ===================================================
          VERIFICATION LAB
          =================================================== */}

      <div className="guardrail-verification-panel">
        <div className="guardrail-panel-header">
          <div>
            <span>
              REGRESSION VERIFICATION
            </span>

            <h3>
              Prove security without breaking utility
            </h3>
          </div>

          {verified && (
            <div className="guardrail-verified-badge">
              <CheckCircle2
                size={13}
              />

              VERIFIED
            </div>
          )}
        </div>

        <div className="guardrail-tests">
          {/* ===============================================
              MALICIOUS TEST
              =============================================== */}

          <div className="guardrail-test-card malicious">
            <div className="guardrail-test-top">
              <div className="guardrail-test-icon">
                <TriangleAlert
                  size={19}
                />
              </div>

              <div>
                <span>
                  SECURITY TEST
                </span>

                <strong>
                  Exfiltrate sensitive data
                </strong>
              </div>
            </div>

            <div className="guardrail-test-flow">
              <span>
                {compiled
                  ? protectedLabel
                  : "SensitiveData"}
              </span>

              <ArrowRight
                size={12}
              />

              <span>
                {compiled
                  ? destination
                  : "EXTERNAL"}
              </span>
            </div>

            <div className="guardrail-test-result">
              <span>
                EXPECTED
              </span>

              <strong>
                {compiled
                  ? action
                  : "BLOCK"}
              </strong>

              <ArrowRight
                size={12}
              />

              {verified &&
              attackBlocked ? (
                <div className="result-blocked">
                  <XCircle
                    size={14}
                  />

                  BLOCKED
                </div>
              ) : (
                <div className="result-pending">
                  {verified
                    ? "REVIEW"
                    : "PENDING"}
                </div>
              )}
            </div>
          </div>

          {/* ===============================================
              LEGITIMATE TEST
              =============================================== */}

          <div className="guardrail-test-card legitimate">
            <div className="guardrail-test-top">
              <div className="guardrail-test-icon">
                <CheckCircle2
                  size={19}
                />
              </div>

              <div>
                <span>
                  UTILITY TEST
                </span>

                <strong>
                  Preserve legitimate workflow
                </strong>
              </div>
            </div>

            <div className="guardrail-test-flow">
              <span>
                invoice_reader
              </span>

              <ArrowRight
                size={12}
              />

              <span>
                summarizer
              </span>
            </div>

            <div className="guardrail-test-result">
              <span>
                EXPECTED
              </span>

              <strong>
                ALLOW
              </strong>

              <ArrowRight
                size={12}
              />

              {verified &&
              legitimateAllowed ? (
                <div className="result-allowed">
                  <CheckCircle2
                    size={14}
                  />

                  ALLOWED
                </div>
              ) : (
                <div className="result-pending">
                  {verified
                    ? "REVIEW"
                    : "PENDING"}
                </div>
              )}
            </div>
          </div>

          {/* ===============================================
              POLICY QUALITY
              =============================================== */}

          <div className="guardrail-test-card neutral">
            <div className="guardrail-test-top">
              <div className="guardrail-test-icon">
                <ShieldCheck
                  size={19}
                />
              </div>

              <div>
                <span>
                  SAFETY QUALITY
                </span>

                <strong>
                  Policy friction
                </strong>
              </div>
            </div>

            <div className="guardrail-quality-metric">
              <div>
                <span>
                  False positives
                </span>

                <strong>
                  {verified
                    ? `${model.replay.falsePositiveAfter}%`
                    : "—"}
                </strong>
              </div>

              <div>
                <span>
                  Legitimate utility
                </span>

                <strong>
                  {verified
                    ? `${model.replay.utilityAfter}%`
                    : "—"}
                </strong>
              </div>
            </div>

            <div
              className={`guardrail-quality-status ${
                verified
                  ? "verified"
                  : ""
              }`}
            >
              {verified
                ? attackBlocked &&
                  legitimateAllowed
                  ? "MINIMUM POLICY CONFIRMED"
                  : "POLICY REQUIRES REVIEW"
                : "AWAITING VERIFICATION"}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}