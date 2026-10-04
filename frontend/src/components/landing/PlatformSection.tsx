import {
  ArrowRight,
  Braces,
  GitBranch,
  Radar,
  ScanSearch,
  ShieldCheck,
  Swords,
} from "lucide-react";

interface PlatformSectionProps {
  onOpenConsole: () => void;
}

const stages = [
  {
    number: "01",
    label: "OBSERVE",
    title: "Discover the agent",
    description:
      "Map tools, permissions, data classes, external destinations and trust boundaries.",
    icon: ScanSearch,
  },
  {
    number: "02",
    label: "MODEL",
    title: "Build the twin",
    description:
      "Create an executable representation of what the agent can actually access and invoke.",
    icon: Radar,
  },
  {
    number: "03",
    label: "ATTACK",
    title: "Expose unsafe paths",
    description:
      "Combine provenance, intent and lineage to discover dangerous tool sequences.",
    icon: Swords,
  },
  {
    number: "04",
    label: "COMPILE",
    title: "Generate the control",
    description:
      "Transform the discovered weakness into the smallest targeted runtime guardrail.",
    icon: Braces,
  },
  {
    number: "05",
    label: "PROVE",
    title: "Replay the attack",
    description:
      "Run the same exploit again and verify that security improves without breaking utility.",
    icon: ShieldCheck,
  },
];

export default function PlatformSection({
  onOpenConsole,
}: PlatformSectionProps) {
  return (
    <section
      className="aegis-platform"
      id="platform-details"
    >
      <div className="aegis-platform__grid" />

      <div className="aegis-platform__shell">
        {/* =================================================
            INTRO
            ================================================= */}

        <div className="aegis-platform__intro">
          <div>
            <div className="aegis-platform__eyebrow">
              <span />

              THE PLATFORM
            </div>

            <h2>
              An executable security layer
              <br />
              for autonomous agents.
            </h2>
          </div>

          <div className="aegis-platform__intro-copy">
            <p>
              AegisTwin learns how an AI agent can act,
              constructs a security digital twin, discovers
              dangerous execution paths and compiles
              targeted controls before those paths become
              production incidents.
            </p>

            <button
              type="button"
              onClick={onOpenConsole}
            >
              OPEN CONTROL CONSOLE

              <ArrowRight size={15} />
            </button>
          </div>
        </div>

        {/* =================================================
            PIPELINE
            ================================================= */}

        <div className="aegis-platform__pipeline">
          <div className="aegis-platform__pipeline-head">
            <div>
              <span>
                EXECUTION PIPELINE
              </span>

              <strong>
                From observation to proof
              </strong>
            </div>

            <div className="aegis-platform__live">
              <i />

              SECURITY MODEL ACTIVE
            </div>
          </div>

          <div className="aegis-platform__stages">
            {stages.map(
              (
                stage,
                index,
              ) => {
                const Icon =
                  stage.icon;

                return (
                  <article
                    className="aegis-platform-stage"
                    key={stage.number}
                  >
                    <span className="aegis-platform-stage__number">
                      {stage.number}
                    </span>

                    <div className="aegis-platform-stage__icon">
                      <Icon size={19} />
                    </div>

                    <span className="aegis-platform-stage__label">
                      {stage.label}
                    </span>

                    <h3>
                      {stage.title}
                    </h3>

                    <p>
                      {stage.description}
                    </p>

                    {index <
                      stages.length -
                        1 && (
                      <div className="aegis-platform-stage__next">
                        <span />

                        <ArrowRight
                          size={12}
                        />
                      </div>
                    )}
                  </article>
                );
              },
            )}
          </div>
        </div>

        {/* =================================================
            CORE SYSTEM
            ================================================= */}

        <div className="aegis-platform__core">
          {/* DIGITAL TWIN */}

          <article className="aegis-platform-card">
            <header>
              <div className="aegis-platform-card__icon">
                <Radar size={20} />
              </div>

              <span>
                01 / DIGITAL TWIN
              </span>
            </header>

            <h3>
              Model what the agent
              can actually do.
            </h3>

            <p>
              AegisTwin maps tool capabilities,
              access relationships, trust boundaries,
              sensitive data classes and execution
              dependencies.
            </p>

            <div className="aegis-platform-card__data">
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
                  BOUNDARIES
                </span>

                <strong>
                  03
                </strong>
              </div>

              <div>
                <span>
                  DRIFT
                </span>

                <strong className="safe">
                  NONE
                </strong>
              </div>
            </div>
          </article>

          {/* ATTACK */}

          <article className="aegis-platform-card aegis-platform-card--attack">
            <header>
              <div className="aegis-platform-card__icon">
                <Swords size={20} />
              </div>

              <span>
                02 / ADVERSARIAL VALIDATION
              </span>
            </header>

            <h3>
              Attack the model
              before attackers do.
            </h3>

            <p>
              Dangerous behavior is tested against the
              digital twin so high-risk combinations can
              be identified before the production agent
              is exposed.
            </p>

            <div className="aegis-platform-card__route">
              <span>
                WEB
              </span>

              <ArrowRight size={11} />

              <span>
                PII
              </span>

              <ArrowRight size={11} />

              <span>
                DERIVED
              </span>

              <ArrowRight size={11} />

              <span className="danger">
                EXTERNAL
              </span>
            </div>
          </article>

          {/* COMPILER */}

          <article className="aegis-platform-card aegis-platform-card--compiler">
            <header>
              <div className="aegis-platform-card__icon">
                <GitBranch size={20} />
              </div>

              <span>
                03 / POLICY COMPILER
              </span>
            </header>

            <h3>
              Fix only what needs
              to be fixed.
            </h3>

            <p>
              AegisTwin compiles a minimal guardrail
              around the unsafe flow instead of
              globally disabling useful tools.
            </p>

            <div className="aegis-platform-card__policy">
              <div>
                <Braces size={13} />

                GENERATED CONTROL
              </div>

              <code>
                CustomerPII /
                DerivedFrom&lt;CustomerPII&gt;
                {"\n"}
                → EXTERNAL = BLOCK
              </code>
            </div>
          </article>
        </div>

        {/* =================================================
            PROOF
            ================================================= */}

        <div className="aegis-platform__proof">
          <div>
            <span>
              THE DIFFERENCE
            </span>

            <h3>
              Detection tells you there is a problem.
              <br />
              AegisTwin proves the problem is fixed.
            </h3>
          </div>

          <div className="aegis-platform__proof-metrics">
            <article>
              <span>
                ATTACK SUCCESS
              </span>

              <div>
                <strong className="danger">
                  100%
                </strong>

                <ArrowRight size={15} />

                <strong className="safe">
                  0%
                </strong>
              </div>
            </article>

            <article>
              <span>
                LEGITIMATE UTILITY
              </span>

              <div>
                <strong>
                  100%
                </strong>

                <ArrowRight size={15} />

                <strong className="safe">
                  100%
                </strong>
              </div>
            </article>
          </div>
        </div>
      </div>
    </section>
  );
}