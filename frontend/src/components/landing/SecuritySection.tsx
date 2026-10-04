import {
  Activity,
  ArrowRight,
  Eye,
  Fingerprint,
  GitBranch,
  LockKeyhole,
  Radar,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";

interface SecuritySectionProps {
  onOpenConsole: () => void;
}

const intelligenceModules = [
  {
    number: "01",
    title: "Provenance",
    subtitle: "Know where influence begins.",
    description:
      "Track whether instructions and data originated from trusted systems, users, tools, documents, or external content.",
    metric: "WEB_UNTRUSTED",
    icon: Fingerprint,
    tone: "blue",
  },
  {
    number: "02",
    title: "Intent",
    subtitle: "Understand what the agent is trying to do.",
    description:
      "Compare requested actions with the expected workflow and flag behavior that violates the intended operation.",
    metric: "MISMATCH",
    icon: Eye,
    tone: "red",
  },
  {
    number: "03",
    title: "Data Lineage",
    subtitle: "Sensitivity survives transformation.",
    description:
      "Follow protected information through tools, summaries, and derived content instead of losing classification after transformation.",
    metric: "PII → DERIVED",
    icon: GitBranch,
    tone: "gold",
  },
  {
    number: "04",
    title: "Attack Paths",
    subtitle: "Find dangerous tool combinations.",
    description:
      "Identify execution sequences that become unsafe only when individually legitimate capabilities are chained together.",
    metric: "1 CRITICAL",
    icon: TriangleAlert,
    tone: "red",
  },
  {
    number: "05",
    title: "Least Privilege",
    subtitle: "Remove unnecessary exposure.",
    description:
      "Determine the smallest capability set required for legitimate work and restrict dangerous access without disabling the agent.",
    metric: "MINIMUM",
    icon: LockKeyhole,
    tone: "green",
  },
  {
    number: "06",
    title: "Drift",
    subtitle: "Detect behavior that changed.",
    description:
      "Compare observed runtime behavior with the security twin and surface capability, permission, or execution drift.",
    metric: "NO DRIFT",
    icon: Radar,
    tone: "blue",
  },
];

export default function SecuritySection({
  onOpenConsole,
}: SecuritySectionProps) {
  return (
    <section
      id="security-details"
      className="aegis-security"
    >
      {/* ===================================================
          AMBIENT BACKGROUND
          =================================================== */}

      <div className="aegis-security__ambient" />

      <div className="aegis-security__shell">
        {/* =================================================
            HEADER
            ================================================= */}

        <header className="aegis-security__header">
          <div>
            <div className="aegis-security__eyebrow">
              <span />

              SECURITY INTELLIGENCE
            </div>

            <h2>
              Understand the execution.
              <br />
              Govern the consequence.
            </h2>
          </div>

          <div className="aegis-security__header-copy">
            <p>
              AegisTwin evaluates more than individual prompts.
              It reasons across origin, intent, data sensitivity,
              tool composition, and runtime behavior to determine
              whether an action should actually be allowed.
            </p>

            <button
              type="button"
              onClick={onOpenConsole}
            >
              INSPECT LIVE INTELLIGENCE

              <ArrowRight size={15} />
            </button>
          </div>
        </header>

        {/* =================================================
            SECURITY REASONING ENGINE
            ================================================= */}

        <div className="aegis-security-engine">
          <div className="aegis-security-engine__top">
            <div>
              <span>
                SECURITY REASONING ENGINE
              </span>

              <strong>
                Context before control
              </strong>
            </div>

            <div className="aegis-security-engine__state">
              <span />

              ANALYSIS ONLINE
            </div>
          </div>

          <div className="aegis-security-engine__body">
            {/* =============================================
                SOURCE
                ============================================= */}

            <div className="aegis-security-engine__source">
              <span className="aegis-security-engine__micro">
                UNTRUSTED INPUT
              </span>

              <div className="aegis-security-engine__source-card">
                <Fingerprint size={20} />

                <div>
                  <strong>
                    invoice_1042.pdf
                  </strong>

                  <span>
                    WEB_UNTRUSTED
                  </span>
                </div>
              </div>

              <div className="aegis-security-engine__source-line">
                <span />

                <ArrowRight size={13} />
              </div>
            </div>

            {/* =============================================
                DECISION CORE
                ============================================= */}

            <div className="aegis-security-core">
              <div className="aegis-security-core__rings">
                <div className="aegis-security-core__ring aegis-security-core__ring--one" />

                <div className="aegis-security-core__ring aegis-security-core__ring--two" />

                <div className="aegis-security-core__ring aegis-security-core__ring--three" />
              </div>

              <div className="aegis-security-core__center">
                <ShieldCheck size={31} />

                <span>
                  AEGISTWIN
                </span>

                <strong>
                  POLICY DECISION
                </strong>
              </div>

              <div className="aegis-security-core__signal aegis-security-core__signal--one">
                PROVENANCE
              </div>

              <div className="aegis-security-core__signal aegis-security-core__signal--two">
                INTENT
              </div>

              <div className="aegis-security-core__signal aegis-security-core__signal--three">
                LINEAGE
              </div>

              <div className="aegis-security-core__signal aegis-security-core__signal--four">
                PRIVILEGE
              </div>
            </div>

            {/* =============================================
                RUNTIME DECISION
                ============================================= */}

            <div className="aegis-security-engine__decision">
              <span className="aegis-security-engine__micro">
                RUNTIME DECISION
              </span>

              <div className="aegis-security-engine__decision-card">
                <TriangleAlert size={20} />

                <div>
                  <span>
                    external_http
                  </span>

                  <strong>
                    BLOCK
                  </strong>
                </div>
              </div>

              <small>
                Sensitive lineage cannot cross the
                external trust boundary.
              </small>
            </div>
          </div>
        </div>

        {/* =================================================
            TWIN INTELLIGENCE HEADER
            ================================================= */}

        <div className="aegis-security__section-heading">
          <div>
            <span>
              TWIN INTELLIGENCE
            </span>

            <h3>
              Seven signals. One runtime decision.
            </h3>
          </div>

          <p>
            Every signal contributes evidence. Controls are
            generated from the combined execution context,
            not from isolated keyword matching.
          </p>
        </div>

        {/* =================================================
            INTELLIGENCE MODULES
            ================================================= */}

        <div className="aegis-security-modules">
          {intelligenceModules.map((module) => {
            const Icon = module.icon;

            return (
              <article
                key={module.number}
                className={`aegis-security-module aegis-security-module--${module.tone}`}
              >
                <header>
                  <span>
                    {module.number}
                  </span>

                  <div>
                    <Icon size={18} />
                  </div>
                </header>

                <div className="aegis-security-module__copy">
                  <span>
                    {module.metric}
                  </span>

                  <h3>
                    {module.title}
                  </h3>

                  <strong>
                    {module.subtitle}
                  </strong>

                  <p>
                    {module.description}
                  </p>
                </div>
              </article>
            );
          })}

          {/* ===============================================
              RUNTIME ENFORCEMENT
              =============================================== */}

          <article className="aegis-security-module aegis-security-module--enforcement">
            <header>
              <span>
                07
              </span>

              <div>
                <ShieldCheck size={18} />
              </div>
            </header>

            <div className="aegis-security-module__copy">
              <span>
                ENFORCED
              </span>

              <h3>
                Runtime Control
              </h3>

              <strong>
                Stop the unsafe action before execution.
              </strong>

              <p>
                Apply deterministic controls at the final
                tool boundary while preserving operations
                that remain within policy.
              </p>
            </div>
          </article>
        </div>

        {/* =================================================
            LINEAGE-AWARE ENFORCEMENT
            ================================================= */}

        <div className="aegis-security-lineage">
          <div className="aegis-security-lineage__intro">
            <span>
              LINEAGE-AWARE ENFORCEMENT
            </span>

            <h3>
              The data changed form.
              <br />
              The sensitivity did not.
            </h3>

            <p>
              A normal output filter may only see a summary.
              AegisTwin still understands that the summary
              was derived from protected customer information.
            </p>
          </div>

          <div className="aegis-security-lineage__flow">
            {/* 01 */}

            <div>
              <span>
                01
              </span>

              <strong>
                WEB_UNTRUSTED
              </strong>

              <small>
                invoice
              </small>
            </div>

            <ArrowRight size={15} />

            {/* 02 */}

            <div>
              <span>
                02
              </span>

              <strong>
                CustomerPII
              </strong>

              <small>
                database
              </small>
            </div>

            <ArrowRight size={15} />

            {/* 03 */}

            <div>
              <span>
                03
              </span>

              <strong>
                Derived PII
              </strong>

              <small>
                summary
              </small>
            </div>

            <ArrowRight size={15} />

            {/* 04 */}

            <div className="aegis-security-lineage__blocked">
              <span>
                04
              </span>

              <strong>
                EXTERNAL
              </strong>

              <small>
                BLOCKED
              </small>
            </div>
          </div>
        </div>

        {/* =================================================
            SECURITY RESULT
            ================================================= */}

        <div className="aegis-security-proof">
          <div className="aegis-security-proof__statement">
            <Activity size={20} />

            <div>
              <span>
                SECURITY OUTCOME
              </span>

              <strong>
                Target the dangerous flow,
                not the entire agent.
              </strong>
            </div>
          </div>

          <div className="aegis-security-proof__metrics">
            <div>
              <span>
                MALICIOUS FLOW
              </span>

              <strong className="blocked">
                BLOCKED
              </strong>
            </div>

            <div>
              <span>
                INTERNAL SUMMARY
              </span>

              <strong className="allowed">
                ALLOWED
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
          </div>
        </div>

        {/* =================================================
            FINAL CTA
            ================================================= */}

        <div className="aegis-security__cta">
          <div>
            <span>
              FROM REASONING TO ENFORCEMENT
            </span>

            <h3>
              See the complete attack path
              inside the control console.
            </h3>
          </div>

          <button
            type="button"
            onClick={onOpenConsole}
          >
            OPEN SECURITY CONSOLE

            <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </section>
  );
}