import {
  Activity,
  ArrowLeft,
  Boxes,
  Check,
  Database,
  LayoutDashboard,
  LoaderCircle,
  Play,
  Radar,
  RotateCcw,
  ScrollText,
  ShieldCheck,
  Swords,
  TriangleAlert,
} from "lucide-react";

import { useState } from "react";

import useAegisConsole from "../../hooks/useAegisConsole";

import AttacksView from "./AttacksView";
import DigitalTwinView from "./DigitalTwinView";
import GuardrailsView from "./GuardrailsView";
import ReplayView from "./ReplayView";
import ReportsView from "./ReportsView";
import TwinGraph from "./TwinGraph";

/* =========================================================
   TYPES
   ========================================================= */

interface DashboardProps {
  onBack: () => void;
}

type AttackStage =
  | "idle"
  | "discover"
  | "analyze"
  | "compile"
  | "replay"
  | "verify"
  | "complete"
  | "error";

type ConsolePage =
  | "overview"
  | "digitalTwin"
  | "attacks"
  | "guardrails"
  | "replay"
  | "reports";

/* =========================================================
   HELPERS
   ========================================================= */

const delay = (milliseconds: number) =>
  new Promise<void>((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });

/* =========================================================
   DASHBOARD
   ========================================================= */

export default function Dashboard({
  onBack,
}: DashboardProps) {
  /* =======================================================
     ACTIVE PAGE
     ======================================================= */

  const [activePage, setActivePage] =
    useState<ConsolePage>("overview");

  /* =======================================================
     ATTACK PIPELINE STATE
     ======================================================= */

  const [stage, setStage] =
    useState<AttackStage>("idle");

  /* =======================================================
     REAL AEGISTWIN BACKEND
     ======================================================= */

  const {
    result,
    runtime,
    model,

    runtimeLoading,
    resetLoading,

    error,

    executeAttack,
    executeReset,

    clearResult,
    clearError,
  } = useAegisConsole();

  /* =======================================================
     RUNNING STATE
     ======================================================= */

  const isRunning =
    stage !== "idle" &&
    stage !== "complete" &&
    stage !== "error";

  /* =======================================================
     PIPELINE INDEX

     -1 = idle / error
      0 = discover
      1 = analyze
      2 = compile
      3 = replay
      4 = verify / complete
     ======================================================= */

  const stageIndex = (() => {
    switch (stage) {
      case "discover":
        return 0;

      case "analyze":
        return 1;

      case "compile":
        return 2;

      case "replay":
        return 3;

      case "verify":
      case "complete":
        return 4;

      default:
        return -1;
    }
  })();

  const pipelineSteps = [
    "Discover",
    "Analyze",
    "Compile",
    "Replay",
    "Verify",
  ];

  /* =======================================================
     PAGE TITLE
     ======================================================= */

  const pageTitle = (() => {
    switch (activePage) {
      case "digitalTwin":
        return "Digital Twin Console";

      case "attacks":
        return "Adversarial Attack Lab";

      case "guardrails":
        return "Guardrail Control Center";

      case "replay":
        return "Execution Replay";

      case "reports":
        return "Security Evidence Report";

      default:
        return "Agent Control Console";
    }
  })();

  /* =======================================================
     ATTACK MY AGENT
     ======================================================= */

  const runAttack = async () => {
    if (
      isRunning ||
      resetLoading
    ) {
      return;
    }

    clearError();
    clearResult();

    try {
      /* ===================================================
         01 — DISCOVER
         =================================================== */

      setStage("discover");

      /*
       * Start the actual backend operation immediately.
       */

      const backendRequest =
        executeAttack();

      await delay(700);

      /* ===================================================
         02 — ANALYZE
         =================================================== */

      setStage("analyze");

      await delay(900);

      /* ===================================================
         03 — COMPILE
         =================================================== */

      setStage("compile");

      await delay(750);

      /*
       * Do not expose replay evidence before the real
       * backend has returned the complete analysis.
       */

      await backendRequest;

      /* ===================================================
         04 — REPLAY
         =================================================== */

      setStage("replay");

      await delay(900);

      /* ===================================================
         05 — VERIFY
         =================================================== */

      setStage("verify");

      await delay(750);

      /* ===================================================
         COMPLETE
         =================================================== */

      setStage("complete");
    } catch {
      setStage("error");
    }
  };

  /* =======================================================
     RESET RUNTIME
     ======================================================= */

  const resetConsole = async () => {
    if (
      isRunning ||
      resetLoading
    ) {
      return;
    }

    clearError();

    try {
      await executeReset();

      /*
       * executeReset clears the backend runtime/result.
       * Reset the visual workflow as well.
       */

      setStage("idle");
    } catch {
      setStage("error");
    }
  };

  /* =======================================================
     RENDER
     ======================================================= */

  return (
    <div className="console-shell">
      {/* ===================================================
          SIDEBAR
          =================================================== */}

      <aside className="console-sidebar">
        {/* BRAND */}

        <div className="console-sidebar__brand">
          <div className="console-sidebar__mark">
            A
          </div>

          <span>
            AEGISTWIN
          </span>
        </div>

        {/* =================================================
            NAVIGATION
            ================================================= */}

        <nav className="console-sidebar__nav">
          {/* OVERVIEW */}

          <button
            type="button"
            className={`console-nav-item ${
              activePage === "overview"
                ? "active"
                : ""
            }`}
            onClick={() =>
              setActivePage("overview")
            }
          >
            <LayoutDashboard
              size={17}
            />

            <span>
              Overview
            </span>
          </button>

          {/* DIGITAL TWIN */}

          <button
            type="button"
            className={`console-nav-item ${
              activePage ===
              "digitalTwin"
                ? "active"
                : ""
            }`}
            onClick={() =>
              setActivePage(
                "digitalTwin",
              )
            }
          >
            <Radar size={17} />

            <span>
              Digital Twin
            </span>
          </button>

          {/* ATTACKS */}

          <button
            type="button"
            className={`console-nav-item ${
              activePage === "attacks"
                ? "active"
                : ""
            }`}
            onClick={() =>
              setActivePage("attacks")
            }
          >
            <Swords size={17} />

            <span>
              Attacks
            </span>
          </button>

          {/* GUARDRAILS */}

          <button
            type="button"
            className={`console-nav-item ${
              activePage ===
              "guardrails"
                ? "active"
                : ""
            }`}
            onClick={() =>
              setActivePage(
                "guardrails",
              )
            }
          >
            <ShieldCheck
              size={17}
            />

            <span>
              Guardrails
            </span>
          </button>

          {/* REPLAY */}

          <button
            type="button"
            className={`console-nav-item ${
              activePage === "replay"
                ? "active"
                : ""
            }`}
            onClick={() =>
              setActivePage("replay")
            }
          >
            <Play size={17} />

            <span>
              Replay
            </span>
          </button>

          {/* REPORTS */}

          <button
            type="button"
            className={`console-nav-item ${
              activePage === "reports"
                ? "active"
                : ""
            }`}
            onClick={() =>
              setActivePage("reports")
            }
          >
            <ScrollText
              size={17}
            />

            <span>
              Reports
            </span>
          </button>
        </nav>

        {/* =================================================
            SIDEBAR BOTTOM
            ================================================= */}

        <div className="console-sidebar__bottom">
          {/* ENGINE */}

          <div className="console-engine-status">
            <span />

            <div>
              <strong>
                {runtimeLoading
                  ? "ENGINE CHECKING"
                  : runtime
                    ? "ENGINE ONLINE"
                    : "ENGINE OFFLINE"}
              </strong>

              <small>
                {runtimeLoading
                  ? "Checking runtime"
                  : runtime
                    ? `${model.runtime.decisions} decisions recorded`
                    : "Runtime unavailable"}
              </small>
            </div>
          </div>

          {/* RESET */}

          <button
            type="button"
            className="console-back"
            onClick={
              resetConsole
            }
            disabled={
              isRunning ||
              resetLoading
            }
          >
            {resetLoading ? (
              <LoaderCircle
                size={15}
                className="attack-spinner"
              />
            ) : (
              <RotateCcw
                size={15}
              />
            )}

            <span>
              {resetLoading
                ? "Resetting runtime"
                : "Reset runtime"}
            </span>
          </button>

          {/* BACK */}

          <button
            type="button"
            className="console-back"
            onClick={onBack}
          >
            <ArrowLeft
              size={15}
            />

            <span>
              Back to site
            </span>
          </button>
        </div>
      </aside>

      {/* ===================================================
          MAIN
          =================================================== */}

      <main className="console-main">
        {/* =================================================
            TOP BAR
            ================================================= */}

        <header className="console-topbar">
          <div>
            <span className="console-kicker">
              SECURITY DIGITAL TWIN
            </span>

            <h1>
              {pageTitle}
            </h1>
          </div>

          <div className="console-topbar__right">
            {/* RUNTIME */}

            <div className="runtime-pill">
              <span />

              {runtimeLoading
                ? "Checking runtime"
                : runtime
                  ? `Runtime connected · ${model.runtime.receipts} receipts`
                  : "Runtime unavailable"}
            </div>

            {/* ATTACK */}

            <button
              type="button"
              className={`attack-agent-btn ${
                isRunning
                  ? "running"
                  : ""
              }`}
              onClick={
                runAttack
              }
              disabled={
                isRunning ||
                resetLoading
              }
            >
              {isRunning ? (
                <LoaderCircle
                  size={17}
                  className="attack-spinner"
                />
              ) : stage ===
                "complete" ? (
                <Check
                  size={17}
                />
              ) : (
                <Swords
                  size={17}
                />
              )}

              <span>
                {isRunning
                  ? "ANALYZING AGENT"
                  : stage ===
                      "complete"
                    ? "ATTACK VERIFIED"
                    : "ATTACK MY AGENT"}
              </span>
            </button>
          </div>
        </header>

        {/* =================================================
            DIGITAL TWIN
            ================================================= */}

        {activePage ===
          "digitalTwin" && (
          <DigitalTwinView
            stageIndex={
              stageIndex
            }
            result={result}
          />
        )}

        {/* =================================================
            ATTACKS
            ================================================= */}

        {activePage ===
          "attacks" && (
          <AttacksView
            stage={stage}
            stageIndex={
              stageIndex
            }
            isRunning={
              isRunning
            }
            error={error}
            onRunAttack={
              runAttack
            }
            result={result}
          />
        )}

        {/* =================================================
            GUARDRAILS
            ================================================= */}

        {activePage ===
          "guardrails" && (
          <GuardrailsView
            stage={stage}
            stageIndex={
              stageIndex
            }
            isRunning={
              isRunning
            }
            onRunAttack={
              runAttack
            }
            model={model}
          />
        )}

        {/* =================================================
            REPLAY
            ================================================= */}

        {activePage ===
          "replay" && (
          <ReplayView
            stage={stage}
            stageIndex={
              stageIndex
            }
            isRunning={
              isRunning
            }
            onRunAttack={
              runAttack
            }
            result={result}
          />
        )}

        {/* =================================================
            REPORTS
            ================================================= */}

        {activePage ===
          "reports" && (
          <ReportsView
            stage={stage}
            stageIndex={
              stageIndex
            }
            result={result}
            error={error}
            model={model}
          />
        )}

        {/* =================================================
            OVERVIEW
            ================================================= */}

        {activePage ===
          "overview" && (
          <>
            {/* =============================================
                METRICS
                ============================================= */}

            <section className="console-metrics">
              {/* TOOLS */}

              <article>
                <Boxes
                  size={19}
                />

                <div>
                  <span>
                    TOOLS
                  </span>

                  <strong>
                    {result
                      ? model.twin
                          .totalTools
                      : "—"}
                  </strong>

                  <small>
                    discovered
                  </small>
                </div>
              </article>

              {/* SENSITIVE TOOLS */}

              <article>
                <Database
                  size={19}
                />

                <div>
                  <span>
                    SENSITIVE TOOLS
                  </span>

                  <strong>
                    {result
                      ? model.twin
                          .sensitiveDataTools
                      : "—"}
                  </strong>

                  <small>
                    mapped
                  </small>
                </div>
              </article>

              {/* ATTACK PATHS */}

              <article>
                <Activity
                  size={19}
                />

                <div>
                  <span>
                    ATTACK PATHS
                  </span>

                  <strong>
                    {result
                      ? model.twin
                          .attackPaths
                      : "—"}
                  </strong>

                  <small
                    className={
                      result &&
                      model.attack
                        .severity ===
                        "CRITICAL"
                        ? "metric-risk"
                        : ""
                    }
                  >
                    {result
                      ? model.attack
                          .severity.toLowerCase()
                      : "pending"}
                  </small>
                </div>
              </article>

              {/* GUARDRAILS */}

              <article>
                <ShieldCheck
                  size={19}
                />

                <div>
                  <span>
                    GUARDRAILS
                  </span>

                  <strong>
                    {
                      model.twin
                        .activeGuardrails
                    }
                  </strong>

                  <small
                    className={
                      model.guardrail
                        .enabled
                        ? "metric-safe"
                        : ""
                    }
                  >
                    {model.guardrail
                      .enabled
                      ? "enforced"
                      : "pending"}
                  </small>
                </div>
              </article>
            </section>

            {/* =============================================
                ATTACK RUNNING
                ============================================= */}

            {isRunning && (
              <div className="attack-running-banner">
                <LoaderCircle
                  size={15}
                  className="attack-spinner"
                />

                <span>
                  {stage ===
                    "discover" &&
                    "Discovering agent tools and trust boundaries..."}

                  {stage ===
                    "analyze" &&
                    "Tracing provenance, intent and sensitive data lineage..."}

                  {stage ===
                    "compile" &&
                    "Compiling the minimum targeted guardrail..."}

                  {stage ===
                    "replay" &&
                    "Replaying the discovered attack path..."}

                  {stage ===
                    "verify" &&
                    "Verifying attack prevention and legitimate utility..."}
                </span>
              </div>
            )}

            {/* =============================================
                SUCCESS
                ============================================= */}

            {stage ===
              "complete" && (
              <div className="attack-success-banner">
                <ShieldCheck
                  size={15}
                />

                <span>
                  {model.replay
                    .maliciousBlockedAfter
                    ? "Attack blocked. Guardrail verified. "
                    : "Replay completed. "}

                  {model.replay
                    .legitimateAllowedAfter
                    ? "Legitimate workflow preserved."
                    : "Legitimate workflow requires review."}
                </span>
              </div>
            )}

            {/* =============================================
                ERROR
                ============================================= */}

            {stage ===
              "error" && (
              <div className="attack-error-banner">
                <TriangleAlert
                  size={15}
                />

                <span>
                  Backend request
                  failed:{" "}
                  {error ||
                    "Unknown backend error"}
                </span>

                <button
                  type="button"
                  onClick={
                    runAttack
                  }
                >
                  <RotateCcw
                    size={13}
                  />

                  Retry
                </button>
              </div>
            )}

            {/* =============================================
                WORKSPACE
                ============================================= */}

            <section className="console-workspace">
              {/* ===========================================
                  DIGITAL TWIN
                  =========================================== */}

              <div className="twin-workspace">
                <div className="panel-heading">
                  <div>
                    <span>
                      EXECUTABLE TWIN
                    </span>

                    <h2>
                      Agent capability map
                    </h2>
                  </div>

                  <div className="panel-heading__status">
                    {result
                      ? "LIVE"
                      : "READY"}
                  </div>
                </div>

                {/* REAL GRAPH */}

                <TwinGraph
                  stageIndex={
                    stageIndex
                  }
                  result={result}
                />

                {/* =========================================
                    PIPELINE
                    ========================================= */}

                <div className="analysis-pipeline">
                  {pipelineSteps.map(
                    (
                      pipelineStep,
                      index,
                    ) => {
                      const isDone =
                        index <
                        stageIndex;

                      const isActive =
                        index ===
                        stageIndex;

                      return (
                        <div
                          className="pipeline-group"
                          key={
                            pipelineStep
                          }
                        >
                          <div
                            className={`pipeline-step ${
                              isDone
                                ? "done"
                                : isActive
                                  ? "active"
                                  : ""
                            }`}
                          >
                            <span>
                              {String(
                                index +
                                  1,
                              ).padStart(
                                2,
                                "0",
                              )}
                            </span>

                            {isDone && (
                              <Check
                                size={
                                  11
                                }
                              />
                            )}

                            <strong>
                              {
                                pipelineStep
                              }
                            </strong>
                          </div>

                          {index <
                            pipelineSteps.length -
                              1 && (
                            <i
                              className={
                                isDone
                                  ? "pipeline-line-done"
                                  : ""
                              }
                            />
                          )}
                        </div>
                      );
                    },
                  )}
                </div>
              </div>

              {/* ===========================================
                  LIVE INTELLIGENCE
                  =========================================== */}

              <aside className="intelligence-panel">
                {/* HEADER */}

                <div className="panel-heading intelligence-heading">
                  <div>
                    <span>
                      LIVE INTELLIGENCE
                    </span>

                    <h2>
                      Analysis
                    </h2>
                  </div>

                  <Activity
                    size={18}
                  />
                </div>

                {/* =========================================
                    ATTACK PATH
                    ========================================= */}

                <div className="intel-section">
                  <div className="intel-label">
                    ATTACK PATH
                  </div>

                  <div className="attack-path-card">
                    <TriangleAlert
                      size={18}
                    />

                    <div>
                      <strong>
                        {result
                          ? "Sensitive data exfiltration"
                          : "Awaiting attack analysis"}
                      </strong>

                      <span>
                        {result
                          ? model.attack
                              .severity
                          : "PENDING"}
                      </span>
                    </div>
                  </div>

                  <div className="attack-route">
                    {result &&
                    model.attack.path
                      .length >
                      0 ? (
                      model.attack.path.map(
                        (
                          tool,
                          index,
                        ) => (
                          <span
                            key={`${tool}-${index}`}
                            className={
                              index ===
                              model.attack
                                .path
                                .length -
                                1
                                ? "route-danger"
                                : ""
                            }
                          >
                            {
                              tool
                            }

                            {index <
                              model.attack
                                .path
                                .length -
                                1 &&
                              " → "}
                          </span>
                        ),
                      )
                    ) : (
                      <span>
                        Run Attack My
                        Agent to discover
                        the execution
                        route.
                      </span>
                    )}
                  </div>
                </div>

                {/* =========================================
                    PROVENANCE
                    ========================================= */}

                <div className="intel-section">
                  <div className="intel-label">
                    PROVENANCE
                  </div>

                  <div className="intel-row">
                    <span>
                      Source
                    </span>

                    <strong>
                      {result
                        ? model
                            .provenance
                            .origin
                        : "PENDING"}
                    </strong>
                  </div>

                  <div className="intel-row">
                    <span>
                      Risk
                    </span>

                    <strong>
                      {result
                        ? model
                            .provenance
                            .risk
                        : "PENDING"}
                    </strong>
                  </div>

                  <div className="intel-row">
                    <span>
                      Sensitive data
                    </span>

                    <strong>
                      {result
                        ? model.lineage
                            .labels[0] ??
                          "None"
                        : "PENDING"}
                    </strong>
                  </div>

                  <div className="intel-row">
                    <span>
                      Derived data
                    </span>

                    <strong>
                      {result
                        ? model.lineage
                            .labels[1] ??
                          "None"
                        : "PENDING"}
                    </strong>
                  </div>

                  <div className="intel-row">
                    <span>
                      Intent
                    </span>

                    <strong
                      className={
                        model.intent
                          .mismatchFound
                          ? "intel-warning"
                          : ""
                      }
                    >
                      {result
                        ? model.intent
                            .mismatchFound
                          ? "MISMATCH"
                          : "ALIGNED"
                        : "PENDING"}
                    </strong>
                  </div>
                </div>

                {/* =========================================
                    GUARDRAIL
                    ========================================= */}

                <div className="intel-section guardrail-section">
                  <div className="intel-label">
                    COMPILED GUARDRAIL
                  </div>

                  {stageIndex >=
                    2 &&
                  model.guardrail
                    .data ? (
                    <>
                      <code>
                        {
                          model
                            .guardrail
                            .text
                        }
                      </code>

                      <div className="guardrail-result">
                        <ShieldCheck
                          size={17}
                        />

                        <span>
                          {stage ===
                          "complete"
                            ? "Guardrail verified"
                            : "Minimum policy generated"}
                        </span>
                      </div>
                    </>
                  ) : (
                    <div className="guardrail-awaiting">
                      {stageIndex >=
                      2
                        ? "Waiting for backend policy"
                        : "Awaiting analysis"}
                    </div>
                  )}
                </div>

                {/* =========================================
                    REPLAY
                    ========================================= */}

                {stageIndex >=
                  3 &&
                  result && (
                    <div className="intel-section">
                      <div className="intel-label">
                        ATTACK REPLAY
                      </div>

                      <div className="replay-result-card">
                        <ShieldCheck
                          size={17}
                        />

                        <div>
                          <strong>
                            {model
                              .replay
                              .maliciousBlockedAfter
                              ? "Attack blocked"
                              : "Replay requires review"}
                          </strong>

                          <span>
                            {model
                              .attack
                              .destination
                              ? `${model.attack.destination} boundary evaluated`
                              : "Runtime decision evaluated"}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                {/* =========================================
                    VERIFICATION
                    ========================================= */}

                {stage ===
                  "complete" &&
                  result && (
                    <div className="intel-section">
                      <div className="intel-label">
                        VERIFICATION
                      </div>

                      <div className="verification-grid">
                        {/* ATTACK */}

                        <div>
                          <span>
                            ATTACK
                          </span>

                          <strong
                            className={
                              model
                                .replay
                                .maliciousBlockedAfter
                                ? "verification-safe"
                                : ""
                            }
                          >
                            {model
                              .replay
                              .maliciousBlockedAfter
                              ? "BLOCKED"
                              : "REVIEW"}
                          </strong>
                        </div>

                        {/* UTILITY */}

                        <div>
                          <span>
                            UTILITY
                          </span>

                          <strong
                            className={
                              model
                                .replay
                                .legitimateAllowedAfter
                                ? "verification-safe"
                                : ""
                            }
                          >
                            {
                              model
                                .replay
                                .utilityAfter
                            }
                            %
                          </strong>
                        </div>

                        {/* FALSE POSITIVES */}

                        <div>
                          <span>
                            FALSE
                            POSITIVES
                          </span>

                          <strong>
                            {
                              model
                                .replay
                                .falsePositiveAfter
                            }
                            %
                          </strong>
                        </div>
                      </div>
                    </div>
                  )}

                {/* =========================================
                    BACKEND MODULES
                    ========================================= */}

                {result && (
                  <div className="intel-section backend-result">
                    <div className="intel-label">
                      TWIN
                      INTELLIGENCE
                    </div>

                    <div className="backend-connected">
                      <Check
                        size={14}
                      />

                      <span>
                        Backend analysis
                        received
                      </span>
                    </div>

                    <div className="backend-modules">
                      <span>
                        Capability Map
                      </span>

                      <span>
                        Provenance
                      </span>

                      <span>
                        Intent
                      </span>

                      <span>
                        Lineage
                      </span>

                      <span>
                        Attack Paths
                      </span>

                      <span>
                        Least Privilege
                      </span>

                      <span>
                        Drift
                      </span>
                    </div>
                  </div>
                )}
              </aside>
            </section>
          </>
        )}
      </main>
    </div>
  );
}