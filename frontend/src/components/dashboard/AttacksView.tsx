import {
  ArrowRight,
  Check,
  Database,
  FileText,
  Globe2,
  LoaderCircle,
  ShieldCheck,
  Swords,
  Terminal,
  TriangleAlert,
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

interface AttacksViewProps {
  stage: AttackStage;

  stageIndex: number;

  isRunning: boolean;

  error: string;

  onRunAttack: () => void;

  result:
    | AttackResponse
    | null;
}

/* =========================================================
   FALLBACK DEMO PATH

   Used only before the real backend response arrives.
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

function getToolLabel(
  toolName: string,
) {
  if (
    toolName.includes(
      "external",
    )
  ) {
    return "EXTERNAL";
  }

  if (
    toolName.includes(
      "database",
    )
  ) {
    return "DATA";
  }

  if (
    toolName.includes(
      "summarizer",
    )
  ) {
    return "TRANSFORM";
  }

  return "TOOL";
}

function getToolIcon(
  toolName: string,
  blocked: boolean,
) {
  if (
    blocked &&
    toolName.includes(
      "external",
    )
  ) {
    return (
      <ShieldCheck
        size={18}
      />
    );
  }

  if (
    toolName.includes(
      "external",
    )
  ) {
    return (
      <Globe2 size={18} />
    );
  }

  if (
    toolName.includes(
      "database",
    )
  ) {
    return (
      <Database size={18} />
    );
  }

  if (
    toolName.includes(
      "invoice",
    )
  ) {
    return (
      <FileText size={18} />
    );
  }

  return (
    <Terminal size={18} />
  );
}

/* =========================================================
   COMPONENT
   ========================================================= */

export default function AttacksView({
  stage,
  stageIndex,
  isRunning,
  error,
  onRunAttack,
  result,
}: AttacksViewProps) {
  const completed =
    stage === "complete";

  /* =======================================================
     REAL BACKEND DATA
     ======================================================= */

  const attackDetails =
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

  const realPath =
    getAttackToolPath(
      result,
    );

  const attackPath =
    realPath.length > 0
      ? realPath
      : fallbackPath;

  const targetTool =
    attackPath[
      attackPath.length - 1
    ] ?? "unknown";

  const provenance =
    result?.twin_analysis
      ?.provenance?.chain;

  const intentMismatch =
    result?.twin_analysis
      ?.intent_action?.find(
        (item) =>
          item.aligned === false,
      );

  const lineageLabels =
    attackDetails
      ?.source_labels ??
    result?.twin_analysis
      ?.lineage
      ?.sensitive_labels ??
    [];

  const benchmarkCases =
    result?.benchmark_report
      ?.cases ?? [];

  const beforeAttack =
    benchmarkCases.find(
      (item) =>
        item.phase ===
          "before" &&
        item.scenario ===
          "malicious",
    );

  const afterAttack =
    benchmarkCases.find(
      (item) =>
        item.phase ===
          "after" &&
        item.scenario ===
          "malicious",
    );

  const afterLegitimate =
    benchmarkCases.find(
      (item) =>
        item.phase ===
          "after" &&
        item.scenario ===
          "legitimate",
    );

  const attackBlocked =
    replay
      .maliciousBlockedAfter;

  const legitimateAllowed =
    replay
      .legitimateAllowedAfter;

  const severity =
    attackDetails
      ?.risk_level ??
    "PENDING";

  const attackId =
    attackDetails
      ?.attack_id ??
    "ATK-001";

  const destination =
    attackDetails
      ?.destination ??
    "EXTERNAL";

  const origin =
    attackDetails
      ?.instruction_origin ??
    provenance
      ?.effective_origin ??
    result
      ?.instruction_origin ??
    "PENDING";

  const originalIntent =
    attackDetails
      ?.original_intent ??
    intentMismatch
      ?.original_intent ??
    result
      ?.original_user_intent ??
    "Awaiting analysis";

  const finalEffect =
    attackDetails
      ?.final_effect ??
    intentMismatch
      ?.final_effect ??
    "External data transfer";

  const evidenceCount =
    attackDetails
      ?.evidence_receipt_ids
      ?.length ?? 0;

  /* =======================================================
     RENDER
     ======================================================= */

  return (
    <section className="attacks-page">
      {/* ===================================================
          HEADER
          =================================================== */}

      <div className="attacks-page__header">
        <div>
          <span className="console-kicker">
            ADVERSARIAL VALIDATION
          </span>

          <h2>
            Attack Lab
          </h2>

          <p>
            Execute controlled attacks against the
            security twin, trace sensitive data movement,
            and verify whether generated guardrails stop
            the exploit.
          </p>
        </div>

        <button
          type="button"
          className={`attack-lab-button ${
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
              size={16}
              className="attack-spinner"
            />
          ) : completed ? (
            <Check
              size={16}
            />
          ) : (
            <Swords
              size={16}
            />
          )}

          {isRunning
            ? "RUNNING ATTACK"
            : completed
              ? "RUN AGAIN"
              : "LAUNCH ATTACK"}
        </button>
      </div>

      {/* ===================================================
          SUMMARY CARDS
          =================================================== */}

      <div className="attack-summary-grid">
        {/* SCENARIO */}

        <article>
          <span>
            SCENARIO
          </span>

          <strong>
            {result
              ? attackId
              : "ATK-001"}
          </strong>

          <small>
            Prompt-injection exfiltration
          </small>
        </article>

        {/* SEVERITY */}

        <article>
          <span>
            SEVERITY
          </span>

          <strong className="attack-severity">
            {result
              ? severity
              : "PENDING"}
          </strong>

          <small>
            Sensitive-data exposure
          </small>
        </article>

        {/* TARGET */}

        <article>
          <span>
            TARGET
          </span>

          <strong>
            {result
              ? targetTool
              : "external_http"}
          </strong>

          <small>
            {result
              ? destination
              : "External destination"}
          </small>
        </article>

        {/* RESULT */}

        <article>
          <span>
            RESULT
          </span>

          <strong
            className={
              completed &&
              attackBlocked
                ? "attack-result-safe"
                : "attack-result-pending"
            }
          >
            {!completed
              ? "PENDING"
              : attackBlocked
                ? "BLOCKED"
                : "REVIEW"}
          </strong>

          <small>
            {!completed
              ? "Awaiting replay"
              : attackBlocked
                ? "Guardrail verified"
                : "Manual review required"}
          </small>
        </article>
      </div>

      {/* ===================================================
          MAIN LAYOUT
          =================================================== */}

      <div className="attacks-layout">
        {/* =================================================
            LEFT — ATTACK EXECUTION
            ================================================= */}

        <div className="attack-execution-panel">
          {/* ===============================================
              PANEL HEADER
              =============================================== */}

          <div className="panel-heading">
            <div>
              <span>
                ACTIVE SCENARIO
              </span>

              <h2>
                Sensitive data exfiltration
              </h2>
            </div>

            <div className="attack-critical-badge">
              {result
                ? severity
                : "CRITICAL"}
            </div>
          </div>

          {/* ===============================================
              ATTACK SOURCE
              =============================================== */}

          <div className="attack-source-card">
            <div className="attack-source-icon">
              <TriangleAlert
                size={20}
              />
            </div>

            <div>
              <span>
                ATTACK ORIGIN
              </span>

              <strong>
                {result
                  ? origin
                  : "UNTRUSTED INPUT"}
              </strong>

              <p>
                {result
                  ? `Original intent: "${originalIntent}". Observed execution attempted ${finalEffect.toLowerCase()} toward ${destination}.`
                  : "An untrusted invoice input attempts to expand a legitimate summarization request into a sensitive external transfer."}
              </p>
            </div>
          </div>

          {/* =================================================
              REAL ATTACK ROUTE
              ================================================= */}

          <div className="attack-chain">
            {attackPath.map(
              (
                toolName,
                index,
              ) => {
                const isFirst =
                  index === 0;

                const isLast =
                  index ===
                  attackPath.length -
                    1;

                const blocked =
                  isLast &&
                  stageIndex >= 3 &&
                  Boolean(
                    guardrail?.enabled,
                  );

                const dangerous =
                  stageIndex >= 1 &&
                  !blocked;

                let subtitle =
                  "observed tool";

                if (isFirst) {
                  subtitle =
                    result
                      ? origin
                      : "WEB_UNTRUSTED";
                }

                if (
                  toolName.includes(
                    "database",
                  )
                ) {
                  subtitle =
                    lineageLabels[0] ??
                    "Sensitive data";
                }

                if (
                  toolName.includes(
                    "summarizer",
                  )
                ) {
                  subtitle =
                    lineageLabels.find(
                      (label) =>
                        label.includes(
                          "DerivedFrom",
                        ),
                    ) ??
                    "Derived data";
                }

                if (isLast) {
                  subtitle =
                    blocked
                      ? "BLOCKED"
                      : destination;
                }

                return (
                  <>
                    <div
                      key={`node-${toolName}-${index}`}
                      className={`attack-chain-node ${
                        blocked
                          ? "blocked"
                          : dangerous
                            ? "danger"
                            : stageIndex >=
                                0 &&
                              isFirst
                              ? "active"
                              : ""
                      }`}
                    >
                      <div>
                        {getToolIcon(
                          toolName,
                          blocked,
                        )}
                      </div>

                      <span>
                        {getToolLabel(
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
                      <div
                        key={`arrow-${toolName}-${index}`}
                        className={`attack-chain-arrow ${
                          stageIndex >= 1
                            ? "danger"
                            : ""
                        }`}
                      >
                        <ArrowRight
                          size={18}
                        />
                      </div>
                    )}
                  </>
                );
              },
            )}
          </div>

          {/* =================================================
              PIPELINE
              ================================================= */}

          <div className="attack-stage-timeline">
            {[
              "Discover",
              "Analyze",
              "Compile",
              "Replay",
              "Verify",
            ].map(
              (
                label,
                index,
              ) => (
                <div
                  key={label}
                  className={`attack-stage-item ${
                    index <
                    stageIndex
                      ? "done"
                      : index ===
                          stageIndex
                        ? "current"
                        : ""
                  }`}
                >
                  <div className="attack-stage-marker">
                    {index <
                    stageIndex ? (
                      <Check
                        size={11}
                      />
                    ) : (
                      String(
                        index + 1,
                      ).padStart(
                        2,
                        "0",
                      )
                    )}
                  </div>

                  <span>
                    {label}
                  </span>
                </div>
              ),
            )}
          </div>

          {/* =================================================
              REPLAY RESULT
              ================================================= */}

          {completed &&
            result && (
              <div className="attack-final-result">
                <div className="attack-final-result__icon">
                  <ShieldCheck
                    size={24}
                  />
                </div>

                <div>
                  <span>
                    REPLAY RESULT
                  </span>

                  <strong>
                    {attackBlocked
                      ? "Attack blocked successfully"
                      : "Attack requires review"}
                  </strong>

                  <p>
                    {attackBlocked &&
                    legitimateAllowed
                      ? `The ${destination} transfer was blocked while the legitimate workflow remained available.`
                      : attackBlocked
                        ? "The malicious transfer was blocked, but legitimate workflow preservation requires review."
                        : "The replay did not produce a verified blocking outcome."}
                  </p>
                </div>
              </div>
            )}

          {/* =================================================
              ERROR
              ================================================= */}

          {stage === "error" && (
            <div className="attack-lab-error">
              <TriangleAlert
                size={16}
              />

              <span>
                {error ||
                  "Attack workflow failed."}
              </span>
            </div>
          )}
        </div>

        {/* =================================================
            RIGHT — REAL EVIDENCE
            ================================================= */}

        <aside className="attack-evidence-panel">
          <div className="attack-evidence-heading">
            <span>
              ATTACK EVIDENCE
            </span>

            <TriangleAlert
              size={17}
            />
          </div>

          {/* ===============================================
              PROVENANCE
              =============================================== */}

          <div className="attack-evidence-section">
            <span className="attack-evidence-label">
              PROVENANCE
            </span>

            <div className="attack-evidence-row">
              <span>
                Input origin
              </span>

              <strong>
                {result
                  ? origin
                  : "PENDING"}
              </strong>
            </div>

            <div className="attack-evidence-row">
              <span>
                Trust state
              </span>

              <strong>
                {result
                  ? provenance
                      ?.contains_untrusted_content
                    ? "UNTRUSTED"
                    : "TRUSTED"
                  : "PENDING"}
              </strong>
            </div>

            <div className="attack-evidence-row">
              <span>
                Evidence receipts
              </span>

              <strong>
                {result
                  ? evidenceCount
                  : "—"}
              </strong>
            </div>

            <div className="attack-evidence-row">
              <span>
                Reproducible
              </span>

              <strong>
                {result
                  ? attackDetails
                      ?.reproducible
                    ? "YES"
                    : "NO"
                  : "PENDING"}
              </strong>
            </div>
          </div>

          {/* ===============================================
              INTENT
              =============================================== */}

          <div className="attack-evidence-section">
            <span className="attack-evidence-label">
              INTENT
            </span>

            <div className="attack-evidence-row">
              <span>
                User intent
              </span>

              <strong>
                {originalIntent}
              </strong>
            </div>

            <div className="attack-intent-card">
              <TriangleAlert
                size={15}
              />

              <div>
                <strong>
                  {result
                    ? intentMismatch
                      ? "Intent mismatch"
                      : "Intent aligned"
                    : "Awaiting analysis"}
                </strong>

                <span>
                  {result
                    ? intentMismatch
                        ?.reason ??
                      "No semantic mismatch was detected."
                    : "The semantic intent check will run during attack analysis."}
                </span>
              </div>
            </div>
          </div>

          {/* ===============================================
              DATA LINEAGE
              =============================================== */}

          <div className="attack-evidence-section">
            <span className="attack-evidence-label">
              DATA LINEAGE
            </span>

            {lineageLabels.length >
            0 ? (
              <div className="attack-lineage">
                {lineageLabels.map(
                  (
                    label,
                    index,
                  ) => (
                    <>
                      <span
                        key={`lineage-${label}-${index}`}
                      >
                        {label}
                      </span>

                      <ArrowRight
                        key={`lineage-arrow-${index}`}
                        size={12}
                      />
                    </>
                  ),
                )}

                <span className="attack-lineage-danger">
                  {destination}
                </span>
              </div>
            ) : (
              <div className="attack-awaiting">
                Awaiting lineage analysis
              </div>
            )}
          </div>

          {/* ===============================================
              GENERATED CONTROL
              =============================================== */}

          <div className="attack-evidence-section">
            <span className="attack-evidence-label">
              GENERATED CONTROL
            </span>

            {stageIndex >= 2 &&
            guardrail ? (
              <div className="attack-policy">
                <code>
                  {guardrail.source_labels.join(
                    " /\n",
                  )}

                  {"\n\n"}

                  →{" "}
                  {
                    guardrail.destination
                  }

                  {"\n"}

                  ={" "}
                  {
                    guardrail.action
                  }
                </code>
              </div>
            ) : (
              <div className="attack-awaiting">
                {stageIndex >= 2
                  ? "Waiting for backend policy"
                  : "Guardrail not compiled yet"}
              </div>
            )}
          </div>

          {/* ===============================================
              BEFORE / AFTER EVIDENCE
              =============================================== */}

          <div className="attack-evidence-section">
            <span className="attack-evidence-label">
              ATTACK STATE
            </span>

            <div className="attack-evidence-row">
              <span>
                Before protection
              </span>

              <strong>
                {result
                  ? beforeAttack
                      ?.attack_success
                    ? "SUCCESS"
                    : "FAILED"
                  : "—"}
              </strong>
            </div>

            <div className="attack-evidence-row">
              <span>
                After protection
              </span>

              <strong>
                {result
                  ? afterAttack
                      ?.blocked
                    ? "BLOCKED"
                    : "NOT BLOCKED"
                  : "—"}
              </strong>
            </div>
          </div>

          {/* ===============================================
              VERIFICATION
              =============================================== */}

          <div className="attack-evidence-section">
            <span className="attack-evidence-label">
              VERIFICATION
            </span>

            <div className="attack-verification">
              {/* ATTACK */}

              <div>
                <span>
                  Attack
                </span>

                <strong
                  className={
                    completed &&
                    attackBlocked
                      ? "safe"
                      : ""
                  }
                >
                  {completed
                    ? attackBlocked
                      ? "BLOCKED"
                      : "REVIEW"
                    : "—"}
                </strong>
              </div>

              {/* LEGITIMATE WORK */}

              <div>
                <span>
                  Legitimate work
                </span>

                <strong
                  className={
                    completed &&
                    legitimateAllowed
                      ? "safe"
                      : ""
                  }
                >
                  {completed
                    ? afterLegitimate
                        ?.allowed
                      ? "ALLOWED"
                      : "REVIEW"
                    : "—"}
                </strong>
              </div>

              {/* FALSE POSITIVES */}

              <div>
                <span>
                  False positives
                </span>

                <strong>
                  {completed
                    ? `${replay.falsePositiveAfter}%`
                    : "—"}
                </strong>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}