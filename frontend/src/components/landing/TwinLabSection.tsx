import { motion } from "framer-motion";

import {
  ArrowRight,
  Braces,
  CheckCircle2,
  Database,
  FileText,
  Globe2,
  Play,
  Radar,
  ShieldCheck,
  Sparkles,
  Terminal,
  TriangleAlert,
} from "lucide-react";

interface TwinLabSectionProps {
  onOpenConsole: () => void;
}

const executionPath = [
  {
    number: "01",
    type: "INPUT",
    title: "invoice_1042.pdf",
    subtitle: "WEB_UNTRUSTED",
    icon: FileText,
    tone: "blue",
  },
  {
    number: "02",
    type: "TOOL",
    title: "customer_database",
    subtitle: "CustomerPII",
    icon: Database,
    tone: "gold",
  },
  {
    number: "03",
    type: "TOOL",
    title: "summarizer",
    subtitle: "DerivedFrom<CustomerPII>",
    icon: Terminal,
    tone: "gold",
  },
  {
    number: "04",
    type: "EGRESS",
    title: "external_http",
    subtitle: "EXTERNAL",
    icon: Globe2,
    tone: "red",
  },
];

export default function TwinLabSection({
  onOpenConsole,
}: TwinLabSectionProps) {
  return (
    <section
      id="twin-lab-details"
      className="aegis-twin-lab"
    >
      <div className="aegis-twin-lab__ambient" />

      <div className="aegis-twin-lab__shell">
        {/* =================================================
            HEADER
            ================================================= */}

        <header className="aegis-twin-lab__header">
          <div>
            <div className="aegis-twin-lab__eyebrow">
              <span />

              TWIN LAB
            </div>

            <h2>
              Attack the twin.
              <br />
              Before production.
            </h2>
          </div>

          <div className="aegis-twin-lab__header-copy">
            <p>
              Twin Lab turns an agent configuration into a
              safe adversarial test environment. Explore the
              attack path, compile the minimum guardrail and
              replay the same exploit without touching the
              production agent.
            </p>

            <button
              type="button"
              onClick={onOpenConsole}
            >
              OPEN FULL TWIN LAB

              <ArrowRight size={15} />
            </button>
          </div>
        </header>

        {/* =================================================
            LAB WINDOW
            ================================================= */}

        <div className="aegis-lab-window">
          {/* TOPBAR */}

          <div className="aegis-lab-window__topbar">
            <div className="aegis-lab-window__identity">
              <div className="aegis-lab-window__icon">
                <Radar size={16} />
              </div>

              <div>
                <span>
                  ACTIVE SCENARIO
                </span>

                <strong>
                  Invoice Processing Agent
                </strong>
              </div>
            </div>

            <div className="aegis-lab-window__status">
              <span />

              TWIN READY
            </div>
          </div>

          {/* BODY */}

          <div className="aegis-lab-window__body">
            {/* =============================================
                LEFT SCENARIO PANEL
                ============================================= */}

            <aside className="aegis-lab-scenario">
              <div className="aegis-lab-scenario__label">
                SCENARIO / ATK-001
              </div>

              <h3>
                Indirect Prompt
                <br />
                Injection
              </h3>

              <p>
                A malicious instruction hidden inside an
                untrusted invoice attempts to make the agent
                retrieve customer data and send it to an
                external destination.
              </p>

              <div className="aegis-lab-scenario__risk">
                <div>
                  <TriangleAlert size={17} />

                  <span>
                    RISK
                  </span>
                </div>

                <strong>
                  CUSTOMER DATA
                  <br />
                  EXFILTRATION
                </strong>
              </div>

              <div className="aegis-lab-scenario__facts">
                <div>
                  <span>
                    TOOLS
                  </span>

                  <strong>
                    04
                  </strong>
                </div>

                <div>
                  <span>
                    ATTACK PATHS
                  </span>

                  <strong className="danger">
                    01
                  </strong>
                </div>

                <div>
                  <span>
                    SEVERITY
                  </span>

                  <strong className="danger">
                    CRITICAL
                  </strong>
                </div>
              </div>

              <button
                type="button"
                className="aegis-lab-attack-btn"
                onClick={onOpenConsole}
              >
                <Play size={15} />

                ATTACK THIS AGENT

                <ArrowRight size={15} />
              </button>
            </aside>

            {/* =============================================
                RIGHT EXECUTION CANVAS
                ============================================= */}

            <div className="aegis-lab-canvas">
              <div className="aegis-lab-canvas__header">
                <div>
                  <span>
                    EXECUTION GRAPH
                  </span>

                  <strong>
                    Discovered attack path
                  </strong>
                </div>

                <div className="aegis-lab-canvas__severity">
                  <TriangleAlert size={12} />

                  CRITICAL
                </div>
              </div>

              {/* EXECUTION PATH */}

              <div className="aegis-lab-path">
                {executionPath.map(
                  (
                    step,
                    index,
                  ) => {
                    const Icon =
                      step.icon;

                    return (
                      <div
                        className="aegis-lab-path__group"
                        key={step.number}
                      >
                        <motion.article
                          className={`aegis-lab-node aegis-lab-node--${step.tone}`}
                          initial={{
                            opacity: 0,
                            y: 15,
                          }}
                          whileInView={{
                            opacity: 1,
                            y: 0,
                          }}
                          viewport={{
                            once: true,
                            amount: 0.4,
                          }}
                          transition={{
                            delay:
                              index *
                              0.09,
                            duration: 0.45,
                          }}
                        >
                          <div className="aegis-lab-node__top">
                            <span>
                              {step.number}
                            </span>

                            <div>
                              <Icon size={17} />
                            </div>
                          </div>

                          <span className="aegis-lab-node__type">
                            {step.type}
                          </span>

                          <strong>
                            {step.title}
                          </strong>

                          <small>
                            {step.subtitle}
                          </small>
                        </motion.article>

                        {index <
                          executionPath.length -
                            1 && (
                          <div className="aegis-lab-path__connector">
                            <span />

                            <ArrowRight size={14} />
                          </div>
                        )}
                      </div>
                    );
                  },
                )}
              </div>

              {/* ATTACK DESCRIPTION */}

              <div className="aegis-lab-attack-trace">
                <div className="aegis-lab-attack-trace__icon">
                  <TriangleAlert size={18} />
                </div>

                <div className="aegis-lab-attack-trace__copy">
                  <span>
                    DISCOVERED ATTACK
                  </span>

                  <strong>
                    Untrusted content can influence a
                    sensitive-data flow into an external tool.
                  </strong>
                </div>

                <div className="aegis-lab-attack-trace__score">
                  <span>
                    RISK SCORE
                  </span>

                  <strong>
                    96
                  </strong>

                  <small>
                    / 100
                  </small>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* =================================================
            GENERATED GUARDRAIL
            ================================================= */}

        <div className="aegis-lab-guardrail">
          <div className="aegis-lab-guardrail__intro">
            <div className="aegis-lab-guardrail__icon">
              <Braces size={21} />
            </div>

            <div>
              <span>
                GENERATED MINIMUM CONTROL
              </span>

              <h3>
                Block the unsafe lineage.
                <br />
                Preserve everything else.
              </h3>
            </div>
          </div>

          <div className="aegis-lab-guardrail__code">
            <div className="aegis-lab-guardrail__code-head">
              <span>
                aegistwin.policy
              </span>

              <small>
                COMPILED
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

          <div className="aegis-lab-guardrail__reason">
            <div>
              <ShieldCheck size={18} />

              <span>
                WHY THIS CONTROL
              </span>
            </div>

            <ul>
              <li>
                Untrusted provenance detected
              </li>

              <li>
                CustomerPII entered execution lineage
              </li>

              <li>
                Derived sensitive data reached external egress
              </li>

              <li>
                Internal summarization remains legitimate
              </li>
            </ul>
          </div>
        </div>

        {/* =================================================
            REPLAY PROOF
            ================================================= */}

        <div className="aegis-lab-replay">
          <div className="aegis-lab-replay__header">
            <div>
              <span>
                REPLAY VERIFICATION
              </span>

              <h3>
                Same attack. Different outcome.
              </h3>
            </div>

            <div className="aegis-lab-replay__verified">
              <CheckCircle2 size={15} />

              VERIFIED
            </div>
          </div>

          <div className="aegis-lab-replay__comparison">
            {/* BEFORE */}

            <article className="aegis-lab-replay-card aegis-lab-replay-card--before">
              <div className="aegis-lab-replay-card__top">
                <span>
                  BEFORE
                </span>

                <TriangleAlert size={17} />
              </div>

              <strong>
                Attack succeeds
              </strong>

              <p>
                Sensitive derived data reaches the
                external HTTP destination.
              </p>

              <div>
                <span>
                  RESULT
                </span>

                <strong className="danger">
                  EXFILTRATED
                </strong>
              </div>
            </article>

            {/* CENTER */}

            <div className="aegis-lab-replay__middle">
              <ShieldCheck size={24} />

              <span>
                +1
                <br />
                GUARDRAIL
              </span>
            </div>

            {/* AFTER */}

            <article className="aegis-lab-replay-card aegis-lab-replay-card--after">
              <div className="aegis-lab-replay-card__top">
                <span>
                  AFTER
                </span>

                <CheckCircle2 size={17} />
              </div>

              <strong>
                Attack blocked
              </strong>

              <p>
                The unsafe external action is stopped at
                the runtime boundary.
              </p>

              <div>
                <span>
                  RESULT
                </span>

                <strong className="safe">
                  BLOCKED
                </strong>
              </div>
            </article>
          </div>

          {/* METRICS */}

          <div className="aegis-lab-replay__metrics">
            <div>
              <span>
                ATTACK SUCCESS
              </span>

              <strong className="danger">
                100%
              </strong>

              <ArrowRight size={13} />

              <strong className="safe">
                0%
              </strong>
            </div>

            <div>
              <span>
                LEGITIMATE UTILITY
              </span>

              <strong>
                100%
              </strong>

              <ArrowRight size={13} />

              <strong className="safe">
                100%
              </strong>
            </div>

            <div>
              <span>
                FALSE POSITIVES
              </span>

              <strong className="safe">
                0
              </strong>
            </div>

            <div>
              <span>
                POLICY FRICTION
              </span>

              <strong className="safe">
                0
              </strong>
            </div>
          </div>
        </div>

        {/* =================================================
            FINAL CTA
            ================================================= */}

        <div className="aegis-twin-lab__cta">
          <div>
            <Sparkles size={19} />

            <div>
              <span>
                READY TO RUN
              </span>

              <strong>
                Execute the complete AegisTwin workflow.
              </strong>
            </div>
          </div>

          <button
            type="button"
            onClick={onOpenConsole}
          >
            ATTACK MY AGENT

            <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </section>
  );
}