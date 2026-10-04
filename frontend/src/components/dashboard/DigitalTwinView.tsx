import {
  Activity,
  Database,
  Fingerprint,
  Globe2,
  LockKeyhole,
  Network,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import type {
  AttackResponse,
  CapabilityTool,
} from "../../lib/api";

import TwinGraph from "./TwinGraph";

/* =========================================================
   TYPES
   ========================================================= */

interface DigitalTwinViewProps {
  stageIndex: number;

  result:
    | AttackResponse
    | null;
}

/* =========================================================
   HELPERS
   ========================================================= */

function getToolOperation(
  tool: CapabilityTool,
): string {
  if (
    tool.capability_flags
      ?.external_communication
  ) {
    return "EGRESS";
  }

  const effect =
    tool.observed_effects?.[0] ??
    tool.declared_effects?.[0] ??
    "";

  if (
    effect.includes("READ")
  ) {
    return "READ";
  }

  if (
    effect.includes("TRANSFORM")
  ) {
    return "TRANSFORM";
  }

  if (
    tool.capability_flags
      ?.database_access
  ) {
    return "QUERY";
  }

  return tool.risk_level;
}

/* =========================================================
   COMPONENT
   ========================================================= */

export default function DigitalTwinView({
  stageIndex,
  result,
}: DigitalTwinViewProps) {
  /* =======================================================
     REAL BACKEND ANALYSIS
     ======================================================= */

  const twin =
    result?.twin_analysis;

  const capabilitySummary =
    twin?.capability_map
      ?.summary;

  const tools =
    twin?.capability_map
      ?.tools ?? [];

  const provenance =
    twin?.provenance?.chain;

  const lineage =
    twin?.lineage;

  const attackPath =
    twin?.attack_paths?.[0];

  const leastPrivilege =
    twin?.least_privilege;

  const drift =
    twin?.drift;

  const guardrail =
    result?.generated_guardrail ??
    result?.benchmark_report
      ?.guardrail ??
    null;

  const sensitiveLabels =
    lineage?.sensitive_labels ??
    [];

  /* =======================================================
     LEAST PRIVILEGE TARGET

     Prefer external_http because it is the relevant egress
     boundary. Otherwise use the first over-privileged tool.
     ======================================================= */

  const privilegeRecommendation =
    leastPrivilege
      ?.recommendations.find(
        (recommendation) =>
          recommendation.tool_name ===
          "external_http",
      ) ??
    leastPrivilege
      ?.recommendations.find(
        (recommendation) =>
          !recommendation
            .least_privilege_satisfied,
      ) ??
    null;

  /* =======================================================
     LINEAGE DISPLAY
     ======================================================= */

  const lineageSteps = [
    provenance
      ?.effective_origin,

    ...sensitiveLabels,

    attackPath
      ?.destination,
  ].filter(
    (
      item,
    ): item is string =>
      Boolean(item),
  );

  /* =======================================================
     RENDER
     ======================================================= */

  return (
    <section className="digital-twin-page">
      {/* ===================================================
          PAGE HEADER
          =================================================== */}

      <div className="digital-twin-page__header">
        <div>
          <span className="console-kicker">
            EXECUTABLE SECURITY MODEL
          </span>

          <h2>
            Digital Twin
          </h2>

          <p>
            A live representation of agent capabilities,
            observed effects, sensitive data lineage,
            trust boundaries and tool interactions.
          </p>
        </div>

        <div className="digital-twin-health">
          <span />

          {result
            ? "TWIN ANALYZED"
            : "AWAITING ANALYSIS"}
        </div>
      </div>

      {/* ===================================================
          TOP METRICS
          =================================================== */}

      <div className="twin-detail-metrics">
        {/* TOOLS */}

        <article>
          <Network size={18} />

          <div>
            <span>
              CAPABILITIES
            </span>

            <strong>
              {result
                ? capabilitySummary
                    ?.total_tools ??
                  0
                : "—"}
            </strong>

            <small>
              mapped tools
            </small>
          </div>
        </article>

        {/* SENSITIVE LABELS */}

        <article>
          <Database size={18} />

          <div>
            <span>
              SENSITIVE CLASSES
            </span>

            <strong>
              {result
                ? sensitiveLabels.length
                : "—"}
            </strong>

            <small>
              tracked labels
            </small>
          </div>
        </article>

        {/* PROVENANCE */}

        <article>
          <Fingerprint size={18} />

          <div>
            <span>
              PROVENANCE
            </span>

            <strong>
              {result
                ? provenance
                    ?.contains_untrusted_content
                  ? 1
                  : 0
                : "—"}
            </strong>

            <small>
              untrusted source
            </small>
          </div>
        </article>

        {/* EXTERNAL EGRESS */}

        <article>
          <LockKeyhole size={18} />

          <div>
            <span>
              EXTERNAL EGRESS
            </span>

            <strong>
              {result
                ? capabilitySummary
                    ?.external_communication_tools ??
                  0
                : "—"}
            </strong>

            <small>
              detected tools
            </small>
          </div>
        </article>
      </div>

      {/* ===================================================
          MAIN TWIN WORKSPACE
          =================================================== */}

      <div className="digital-twin-layout">
        {/* =================================================
            GRAPH
            ================================================= */}

        <div className="digital-twin-graph-panel">
          <div className="panel-heading">
            <div>
              <span>
                LIVE CAPABILITY GRAPH
              </span>

              <h2>
                Agent execution topology
              </h2>
            </div>

            <div className="panel-heading__status">
              {result
                ? "LIVE"
                : "READY"}
            </div>
          </div>

          <div className="digital-twin-large-graph">
            <TwinGraph
              stageIndex={
                stageIndex
              }
              result={result}
            />
          </div>
        </div>

        {/* =================================================
            RIGHT INTELLIGENCE
            ================================================= */}

        <aside className="twin-detail-panel">
          {/* ===============================================
              CAPABILITY MAP
              =============================================== */}

          <div className="twin-detail-section">
            <div className="twin-detail-title">
              <Sparkles size={15} />

              CAPABILITY MAP
            </div>

            <div className="twin-capability-list">
              {tools.length > 0 ? (
                tools.map(
                  (tool) => {
                    const operation =
                      getToolOperation(
                        tool,
                      );

                    return (
                      <div
                        key={
                          tool.tool_name
                        }
                      >
                        <span>
                          {
                            tool.tool_name
                          }
                        </span>

                        <strong
                          className={
                            operation ===
                            "EGRESS"
                              ? "twin-egress"
                              : ""
                          }
                        >
                          {
                            operation
                          }
                        </strong>
                      </div>
                    );
                  },
                )
              ) : (
                <div>
                  <span>
                    Awaiting twin
                    analysis
                  </span>

                  <strong>
                    READY
                  </strong>
                </div>
              )}
            </div>
          </div>

          {/* ===============================================
              PROVENANCE
              =============================================== */}

          <div className="twin-detail-section">
            <div className="twin-detail-title">
              <Fingerprint size={15} />

              PROVENANCE
            </div>

            <div className="twin-detail-row">
              <span>
                Input origin
              </span>

              <strong>
                {result
                  ? provenance
                      ?.effective_origin ??
                    "UNKNOWN"
                  : "PENDING"}
              </strong>
            </div>

            <div className="twin-detail-row">
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

            <div className="twin-detail-row">
              <span>
                Risk level
              </span>

              <strong>
                {result
                  ? provenance
                      ?.risk_level ??
                    "LOW"
                  : "PENDING"}
              </strong>
            </div>

            <div className="twin-detail-row">
              <span>
                Sensitive action authority
              </span>

              <strong>
                {result
                  ? provenance
                      ?.can_authorize_sensitive_action
                    ? "YES"
                    : "NO"
                  : "PENDING"}
              </strong>
            </div>

            <div className="twin-detail-row">
              <span>
                Tool calls
              </span>

              <strong>
                {result
                  ? provenance
                      ?.call_count ??
                    0
                  : "—"}
              </strong>
            </div>
          </div>

          {/* ===============================================
              DATA LINEAGE
              =============================================== */}

          <div className="twin-detail-section">
            <div className="twin-detail-title">
              <Activity size={15} />

              LINEAGE
            </div>

            {lineageSteps.length >
            0 ? (
              <div className="lineage-flow">
                {lineageSteps.map(
                  (
                    step,
                    index,
                  ) => (
                    <span
                      key={`${step}-${index}`}
                      className={
                        index ===
                        lineageSteps.length -
                          1
                          ? "lineage-external"
                          : ""
                      }
                    >
                      {step}

                      {index <
                        lineageSteps.length -
                          1 && (
                        <b>
                          →
                        </b>
                      )}
                    </span>
                  ),
                )}
              </div>
            ) : (
              <div className="lineage-flow">
                <span>
                  Awaiting lineage
                  analysis
                </span>
              </div>
            )}
          </div>

          {/* ===============================================
              LEAST PRIVILEGE
              =============================================== */}

          <div className="twin-detail-section">
            <div className="twin-detail-title">
              <ShieldCheck size={15} />

              LEAST PRIVILEGE
            </div>

            {privilegeRecommendation ? (
              <>
                <div className="privilege-card">
                  <div>
                    <span>
                      {
                        privilegeRecommendation
                          .tool_name
                      }
                    </span>

                    <strong>
                      {privilegeRecommendation
                        .least_privilege_satisfied
                        ? "MINIMUM PRIVILEGE"
                        : `${privilegeRecommendation.removable_capabilities.length} REMOVABLE`}
                    </strong>
                  </div>

                  <ShieldCheck
                    size={18}
                  />
                </div>

                <p className="privilege-copy">
                  {privilegeRecommendation
                    .removable_capabilities
                    .length > 0
                    ? `Recommended reduction: ${privilegeRecommendation.removable_capabilities.join(", ")}.`
                    : "Current capability set already satisfies least-privilege analysis."}
                </p>
              </>
            ) : (
              <>
                <div className="privilege-card">
                  <div>
                    <span>
                      Analysis
                    </span>

                    <strong>
                      PENDING
                    </strong>
                  </div>

                  <ShieldCheck
                    size={18}
                  />
                </div>

                <p className="privilege-copy">
                  Run Attack My Agent to
                  calculate minimum required
                  capabilities.
                </p>
              </>
            )}
          </div>

          {/* ===============================================
              GUARDRAIL
              =============================================== */}

          {guardrail && (
            <div className="twin-detail-section">
              <div className="twin-detail-title">
                <LockKeyhole size={15} />

                ACTIVE CONTROL
              </div>

              <div className="privilege-card">
                <div>
                  <span>
                    {
                      guardrail.guardrail_id
                    }
                  </span>

                  <strong>
                    {
                      guardrail.action
                    }
                  </strong>
                </div>

                <ShieldCheck
                  size={18}
                />
              </div>

              <p className="privilege-copy">
                {guardrail.source_labels.join(
                  " / ",
                )}{" "}
                →{" "}
                {
                  guardrail.destination
                }
              </p>
            </div>
          )}

          {/* ===============================================
              DRIFT
              =============================================== */}

          <div className="twin-detail-section">
            <div className="twin-detail-title">
              <Globe2 size={15} />

              DRIFT
            </div>

            <div className="drift-status">
              <span className="drift-status__dot" />

              <div>
                <strong>
                  {!result
                    ? "Awaiting baseline"
                    : drift?.available
                      ? "Drift analysis available"
                      : "Snapshot required"}
                </strong>

                <small>
                  {!result
                    ? "Run the twin analysis first"
                    : drift
                        ?.reason ??
                      "Temporal comparison available"}
                </small>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}