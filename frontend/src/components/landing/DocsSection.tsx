import {
  ArrowRight,
  BookOpen,
  Braces,
  CheckCircle2,
  Code2,
  Database,
  GitBranch,
  Network,
  Play,
  Server,
  ShieldCheck,
  Swords,
  Terminal,
} from "lucide-react";

interface DocsSectionProps {
  onOpenConsole: () => void;
}

const endpoints = [
  {
    method: "GET",
    path: "/health",
    description:
      "Check whether the AegisTwin API is available.",
    tone: "green",
  },
  {
    method: "POST",
    path: "/attack-my-agent",
    description:
      "Run the complete digital-twin attack, policy compilation, replay, and verification workflow.",
    tone: "gold",
  },
  {
    method: "GET",
    path: "/runtime/status",
    description:
      "Inspect the current runtime enforcement state.",
    tone: "green",
  },
  {
    method: "POST",
    path: "/runtime/reset",
    description:
      "Reset runtime state and compiled controls.",
    tone: "gold",
  },
];

const intelligence = [
  "Tool Profiles",
  "Capability Map",
  "Execution Graph",
  "Provenance",
  "Intent / Action",
  "Data Lineage",
  "Attack Paths",
  "Least Privilege",
  "Drift",
];

export default function DocsSection({
  onOpenConsole,
}: DocsSectionProps) {
  return (
    <section
      id="docs-details"
      className="aegis-docs"
    >
      <div className="aegis-docs__ambient" />

      <div className="aegis-docs__shell">
        {/* =================================================
            HEADER
            ================================================= */}

        <header className="aegis-docs__header">
          <div>
            <div className="aegis-docs__eyebrow">
              <span />

              DOCUMENTATION
            </div>

            <h2>
              Understand the system.
              <br />
              Inspect the evidence.
            </h2>
          </div>

          <div className="aegis-docs__header-copy">
            <p>
              A technical overview of AegisTwin's
              architecture, security reasoning, attack
              workflow, policy compiler, runtime controls,
              and API surface.
            </p>

            <button
              type="button"
              onClick={onOpenConsole}
            >
              OPEN LIVE CONSOLE

              <ArrowRight size={15} />
            </button>
          </div>
        </header>

        {/* =================================================
            DOCUMENTATION FRAME
            ================================================= */}

        <div className="aegis-docs-frame">
          {/* ===============================================
              SIDEBAR
              =============================================== */}

          <aside className="aegis-docs-sidebar">
            <div className="aegis-docs-sidebar__brand">
              <BookOpen size={17} />

              <div>
                <span>
                  AEGISTWIN
                </span>

                <strong>
                  Technical Docs
                </strong>
              </div>
            </div>

            <nav className="aegis-docs-sidebar__nav">
              <a href="#docs-overview">
                <span>
                  01
                </span>

                Overview
              </a>

              <a href="#docs-architecture">
                <span>
                  02
                </span>

                Architecture
              </a>

              <a href="#docs-security-model">
                <span>
                  03
                </span>

                Security Model
              </a>

              <a href="#docs-attack-pipeline">
                <span>
                  04
                </span>

                Attack Pipeline
              </a>

              <a href="#docs-policy">
                <span>
                  05
                </span>

                Policy Compiler
              </a>

              <a href="#docs-api">
                <span>
                  06
                </span>

                API
              </a>
            </nav>

            <div className="aegis-docs-sidebar__state">
              <span />

              DOCUMENTATION READY
            </div>
          </aside>

          {/* ===============================================
              MAIN DOCUMENT
              =============================================== */}

          <div className="aegis-docs-content">
            {/* =============================================
                OVERVIEW
                ============================================= */}

            <article
              id="docs-overview"
              className="aegis-docs-block"
            >
              <div className="aegis-docs-block__label">
                01 / OVERVIEW
              </div>

              <div className="aegis-docs-block__heading">
                <div>
                  <ShieldCheck size={22} />

                  <h3>
                    What is AegisTwin?
                  </h3>
                </div>

                <span>
                  AI CONTROL LAYER
                </span>
              </div>

              <p className="aegis-docs-block__lead">
                AegisTwin is a security digital twin and
                runtime control layer for autonomous AI
                agents. It observes agent capabilities,
                discovers dangerous compositions, compiles
                minimum guardrails, replays the attack, and
                verifies that legitimate behavior remains
                available.
              </p>

              <div className="aegis-docs-principles">
                <div>
                  <strong>
                    DISCOVER
                  </strong>

                  <span>
                    Model actual agent capability.
                  </span>
                </div>

                <div>
                  <strong>
                    ATTACK
                  </strong>

                  <span>
                    Find dangerous execution paths.
                  </span>
                </div>

                <div>
                  <strong>
                    COMPILE
                  </strong>

                  <span>
                    Generate minimum runtime controls.
                  </span>
                </div>

                <div>
                  <strong>
                    PROVE
                  </strong>

                  <span>
                    Replay and preserve utility.
                  </span>
                </div>
              </div>
            </article>

            {/* =============================================
                ARCHITECTURE
                ============================================= */}

            <article
              id="docs-architecture"
              className="aegis-docs-block"
            >
              <div className="aegis-docs-block__label">
                02 / ARCHITECTURE
              </div>

              <div className="aegis-docs-block__heading">
                <div>
                  <Network size={22} />

                  <h3>
                    System Architecture
                  </h3>
                </div>

                <span>
                  OBSERVE → ENFORCE
                </span>
              </div>

              <p className="aegis-docs-block__lead">
                The platform separates security reasoning
                from the agent itself. Observed behavior
                becomes twin intelligence, twin intelligence
                becomes evidence, and evidence becomes a
                deterministic runtime decision.
              </p>

              <div className="aegis-docs-architecture">
                <div>
                  <Terminal size={18} />

                  <span>
                    AGENT
                  </span>

                  <strong>
                    Tools + Data
                  </strong>
                </div>

                <ArrowRight size={15} />

                <div>
                  <Database size={18} />

                  <span>
                    DIGITAL TWIN
                  </span>

                  <strong>
                    Capability Model
                  </strong>
                </div>

                <ArrowRight size={15} />

                <div>
                  <Swords size={18} />

                  <span>
                    ADVERSARIAL
                  </span>

                  <strong>
                    Attack Discovery
                  </strong>
                </div>

                <ArrowRight size={15} />

                <div>
                  <Braces size={18} />

                  <span>
                    COMPILER
                  </span>

                  <strong>
                    Guardrail
                  </strong>
                </div>

                <ArrowRight size={15} />

                <div className="aegis-docs-architecture__final">
                  <ShieldCheck size={18} />

                  <span>
                    RUNTIME
                  </span>

                  <strong>
                    Enforced
                  </strong>
                </div>
              </div>
            </article>

            {/* =============================================
                SECURITY MODEL
                ============================================= */}

            <article
              id="docs-security-model"
              className="aegis-docs-block"
            >
              <div className="aegis-docs-block__label">
                03 / SECURITY MODEL
              </div>

              <div className="aegis-docs-block__heading">
                <div>
                  <GitBranch size={22} />

                  <h3>
                    Twin Intelligence
                  </h3>
                </div>

                <span>
                  CONTEXTUAL SECURITY
                </span>
              </div>

              <p className="aegis-docs-block__lead">
                AegisTwin does not make security decisions
                from one prompt or one tool call. It combines
                structural and semantic evidence across the
                complete execution context.
              </p>

              <div className="aegis-docs-intelligence">
                {intelligence.map(
                  (
                    item,
                    index,
                  ) => (
                    <div key={item}>
                      <span>
                        {String(
                          index + 1,
                        ).padStart(
                          2,
                          "0",
                        )}
                      </span>

                      <strong>
                        {item}
                      </strong>

                      <CheckCircle2
                        size={13}
                      />
                    </div>
                  ),
                )}
              </div>
            </article>

            {/* =============================================
                ATTACK PIPELINE
                ============================================= */}

            <article
              id="docs-attack-pipeline"
              className="aegis-docs-block"
            >
              <div className="aegis-docs-block__label">
                04 / ATTACK PIPELINE
              </div>

              <div className="aegis-docs-block__heading">
                <div>
                  <Swords size={22} />

                  <h3>
                    Canonical Demo Scenario
                  </h3>
                </div>

                <span className="aegis-docs-danger">
                  CRITICAL
                </span>
              </div>

              <p className="aegis-docs-block__lead">
                An untrusted invoice contains an injected
                instruction that attempts to retrieve
                customer information, transform it through
                the summarizer, and transmit the derived
                content through an external HTTP tool.
              </p>

              <div className="aegis-docs-attack-path">
                <div>
                  <span>
                    01
                  </span>

                  <strong>
                    invoice_reader
                  </strong>

                  <small>
                    WEB_UNTRUSTED
                  </small>
                </div>

                <ArrowRight size={14} />

                <div>
                  <span>
                    02
                  </span>

                  <strong>
                    customer_database
                  </strong>

                  <small>
                    CustomerPII
                  </small>
                </div>

                <ArrowRight size={14} />

                <div>
                  <span>
                    03
                  </span>

                  <strong>
                    summarizer
                  </strong>

                  <small>
                    Derived PII
                  </small>
                </div>

                <ArrowRight size={14} />

                <div className="aegis-docs-attack-path__danger">
                  <span>
                    04
                  </span>

                  <strong>
                    external_http
                  </strong>

                  <small>
                    EXTERNAL
                  </small>
                </div>
              </div>
            </article>

            {/* =============================================
                POLICY COMPILER
                ============================================= */}

            <article
              id="docs-policy"
              className="aegis-docs-block"
            >
              <div className="aegis-docs-block__label">
                05 / POLICY COMPILER
              </div>

              <div className="aegis-docs-block__heading">
                <div>
                  <Code2 size={22} />

                  <h3>
                    Minimum Generated Control
                  </h3>
                </div>

                <span className="aegis-docs-success">
                  COMPILED
                </span>
              </div>

              <p className="aegis-docs-block__lead">
                The compiler targets the unsafe information
                flow instead of disabling the entire external
                tool or preventing legitimate internal
                summarization.
              </p>

              <div className="aegis-docs-code">
                <div className="aegis-docs-code__head">
                  <span>
                    aegistwin.policy
                  </span>

                  <small>
                    GENERATED
                  </small>
                </div>

                <pre>
                  <code>
{`policy "customer-pii-egress" {
  source      = CustomerPII
  derived     = DerivedFrom<CustomerPII>
  destination = EXTERNAL
  action      = BLOCK
}`}
                  </code>
                </pre>
              </div>

              <div className="aegis-docs-verification">
                <div>
                  <span>
                    MALICIOUS PATH
                  </span>

                  <strong className="blocked">
                    BLOCK
                  </strong>
                </div>

                <div>
                  <span>
                    INTERNAL SUMMARY
                  </span>

                  <strong className="allowed">
                    ALLOW
                  </strong>
                </div>

                <div>
                  <span>
                    FALSE POSITIVES
                  </span>

                  <strong>
                    0
                  </strong>
                </div>

                <div>
                  <span>
                    UTILITY
                  </span>

                  <strong className="allowed">
                    100%
                  </strong>
                </div>
              </div>
            </article>

            {/* =============================================
                API
                ============================================= */}

            <article
              id="docs-api"
              className="aegis-docs-block"
            >
              <div className="aegis-docs-block__label">
                06 / API
              </div>

              <div className="aegis-docs-block__heading">
                <div>
                  <Server size={22} />

                  <h3>
                    Runtime API
                  </h3>
                </div>

                <span>
                  FASTAPI
                </span>
              </div>

              <p className="aegis-docs-block__lead">
                The frontend communicates with the AegisTwin
                control service through a compact API surface.
              </p>

              <div className="aegis-docs-endpoints">
                {endpoints.map(
                  (endpoint) => (
                    <div
                      className="aegis-docs-endpoint"
                      key={`${endpoint.method}-${endpoint.path}`}
                    >
                      <span
                        className={`aegis-docs-endpoint__method aegis-docs-endpoint__method--${endpoint.tone}`}
                      >
                        {endpoint.method}
                      </span>

                      <code>
                        {endpoint.path}
                      </code>

                      <p>
                        {
                          endpoint.description
                        }
                      </p>
                    </div>
                  ),
                )}
              </div>

              <div className="aegis-docs-api-note">
                <Terminal size={16} />

                <div>
                  <span>
                    INTERACTIVE API DOCUMENTATION
                  </span>

                  <strong>
                    /docs
                  </strong>
                </div>
              </div>
            </article>
          </div>
        </div>

        {/* =================================================
            FINAL JUDGE CTA
            ================================================= */}

        <div className="aegis-docs__cta">
          <div>
            <Play size={20} />

            <div>
              <span>
                FROM DOCUMENTATION TO PROOF
              </span>

              <strong>
                Run the attack and watch AegisTwin
                compile the fix.
              </strong>
            </div>
          </div>

          <button
            type="button"
            onClick={onOpenConsole}
          >
            OPEN CONSOLE

            <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </section>
  );
}