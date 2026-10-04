import {
  AnimatePresence,
  motion,
} from "framer-motion";

import {
  BrainCircuit,
  CheckCircle2,
  Database,
  FileText,
  Fingerprint,
  Globe2,
  LockKeyhole,
  Network,
  ScanSearch,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

import {
  useEffect,
  useRef,
  useState,
} from "react";

interface SplashScreenProps {
  onComplete: () => void;
}

type Phase =
  | "observe"
  | "twin"
  | "attack"
  | "control"
  | "brand";

/*
  FINAL TIMING

  0.0  - 3.2s   Observe
  3.2  - 6.5s   Digital Twin
  6.5  - 10.0s  Attack
  10.0 - 12.5s  Control
  12.5 - 20.5s  Final AegisTwin reveal
*/

const TOTAL_TIME = 20500;

/* =========================================================
   SHARED TOOL NODE
   ========================================================= */

interface ToolNodeProps {
  icon: LucideIcon;
  title: string;
  subtitle: string;
  danger?: boolean;
  safe?: boolean;
  delay?: number;
}

function ToolNode({
  icon: Icon,
  title,
  subtitle,
  danger = false,
  safe = false,
  delay = 0,
}: ToolNodeProps) {
  return (
    <motion.div
      className={[
        "cin-tool-node",
        danger
          ? "cin-tool-danger"
          : "",
        safe
          ? "cin-tool-safe"
          : "",
      ].join(" ")}
      initial={{
        opacity: 0,
        y: 14,
        scale: 0.96,
      }}
      animate={{
        opacity: 1,
        y: 0,
        scale: 1,
      }}
      transition={{
        duration: 0.7,
        delay,
        ease: [0.16, 1, 0.3, 1],
      }}
    >
      <div className="cin-tool-icon">
        <Icon
          size={17}
          strokeWidth={1.6}
        />
      </div>

      <div className="cin-tool-copy">
        <strong>
          {title}
        </strong>

        <span>
          {subtitle}
        </span>
      </div>

      <span className="cin-tool-led" />
    </motion.div>
  );
}

/* =========================================================
   OBSERVE
   ========================================================= */

function ObserveScene() {
  return (
    <motion.section
      className="cin-scene cin-observe"
      initial={{
        opacity: 0,
      }}
      animate={{
        opacity: 1,
      }}
      exit={{
        opacity: 0,
        scale: 0.97,
      }}
      transition={{
        duration: 0.8,
      }}
    >
      <div className="cin-copy-block">
        <motion.div
          className="cin-section-number"
          initial={{
            opacity: 0,
          }}
          animate={{
            opacity: 1,
          }}
          transition={{
            delay: 0.2,
          }}
        >
          01 / OBSERVE
        </motion.div>

        <motion.h1
          initial={{
            opacity: 0,
            y: 22,
          }}
          animate={{
            opacity: 1,
            y: 0,
          }}
          transition={{
            duration: 0.9,
            delay: 0.25,
            ease: [0.16, 1, 0.3, 1],
          }}
        >
          Watch the agent
          <br />

          <span>
            before you trust it.
          </span>
        </motion.h1>

        <motion.p
          initial={{
            opacity: 0,
            y: 10,
          }}
          animate={{
            opacity: 1,
            y: 0,
          }}
          transition={{
            delay: 0.8,
            duration: 0.8,
          }}
        >
          AegisTwin observes real tool use,
          data movement and trust boundaries
          before autonomous actions are trusted.
        </motion.p>

        <motion.div
          className="cin-mini-metrics"
          initial={{
            opacity: 0,
          }}
          animate={{
            opacity: 1,
          }}
          transition={{
            delay: 1.25,
            duration: 0.8,
          }}
        >
          <div>
            <strong>04</strong>
            <span>TOOLS</span>
          </div>

          <div>
            <strong>03</strong>
            <span>BOUNDARIES</span>
          </div>

          <div>
            <strong>01</strong>
            <span>EGRESS</span>
          </div>
        </motion.div>
      </div>

      <div className="cin-observe-visual">
        <motion.div
          className="cin-radar-ring ring-a"
          animate={{
            rotate: 360,
          }}
          transition={{
            duration: 26,
            repeat: Infinity,
            ease: "linear",
          }}
        />

        <motion.div
          className="cin-radar-ring ring-b"
          animate={{
            rotate: -360,
          }}
          transition={{
            duration: 34,
            repeat: Infinity,
            ease: "linear",
          }}
        />

        <motion.div
          className="cin-core"
          initial={{
            opacity: 0,
            scale: 0,
          }}
          animate={{
            opacity: 1,
            scale: 1,
          }}
          transition={{
            duration: 1,
            ease: [0.16, 1, 0.3, 1],
          }}
        >
          <Fingerprint
            size={34}
            strokeWidth={1.25}
          />

          <span>
            AGENT
          </span>
        </motion.div>

        <motion.div
          className="cin-orbit-node node-one"
          initial={{
            opacity: 0,
            x: -15,
          }}
          animate={{
            opacity: 1,
            x: 0,
          }}
          transition={{
            delay: 0.75,
          }}
        >
          <FileText size={16} />
          <span>
            invoice_reader
          </span>
        </motion.div>

        <motion.div
          className="cin-orbit-node node-two"
          initial={{
            opacity: 0,
            x: 15,
          }}
          animate={{
            opacity: 1,
            x: 0,
          }}
          transition={{
            delay: 1,
          }}
        >
          <Database size={16} />
          <span>
            customer_database
          </span>
        </motion.div>

        <motion.div
          className="cin-orbit-node node-three"
          initial={{
            opacity: 0,
            x: 15,
          }}
          animate={{
            opacity: 1,
            x: 0,
          }}
          transition={{
            delay: 1.25,
          }}
        >
          <BrainCircuit size={16} />
          <span>
            summarizer
          </span>
        </motion.div>

        <motion.div
          className="cin-orbit-node node-four"
          initial={{
            opacity: 0,
            x: -15,
          }}
          animate={{
            opacity: 1,
            x: 0,
          }}
          transition={{
            delay: 1.5,
          }}
        >
          <Globe2 size={16} />
          <span>
            external_http
          </span>
        </motion.div>
      </div>
    </motion.section>
  );
}

/* =========================================================
   DIGITAL TWIN
   ========================================================= */

function TwinPanel({
  twin = false,
}: {
  twin?: boolean;
}) {
  return (
    <motion.div
      className={
        twin
          ? "cin-twin-panel twin-copy"
          : "cin-twin-panel"
      }
      initial={{
        opacity: 0,
        x: twin
          ? 35
          : -35,
      }}
      animate={{
        opacity: 1,
        x: 0,
      }}
      transition={{
        duration: 0.9,
        delay: twin
          ? 0.45
          : 0.2,
        ease: [0.16, 1, 0.3, 1],
      }}
    >
      <div className="cin-panel-head">
        <div>
          {twin ? (
            <Network size={16} />
          ) : (
            <Fingerprint size={16} />
          )}

          <span>
            {twin
              ? "EXECUTABLE TWIN"
              : "LIVE AGENT"}
          </span>
        </div>

        <span className="cin-panel-status">
          {twin
            ? "SYNCHRONIZED"
            : "OBSERVED"}
        </span>
      </div>

      <div className="cin-panel-body">
        <ToolNode
          icon={FileText}
          title="invoice_reader"
          subtitle="READ DOCUMENT"
          delay={0.15}
        />

        <ToolNode
          icon={Database}
          title="customer_database"
          subtitle="SENSITIVE ACCESS"
          delay={0.28}
        />

        <ToolNode
          icon={BrainCircuit}
          title="summarizer"
          subtitle="MODEL TOOL"
          delay={0.41}
        />

        <ToolNode
          icon={Globe2}
          title="external_http"
          subtitle="NETWORK EGRESS"
          delay={0.54}
        />
      </div>

      {twin && (
        <motion.div
          className="cin-twin-tags"
          initial={{
            opacity: 0,
          }}
          animate={{
            opacity: 1,
          }}
          transition={{
            delay: 1,
          }}
        >
          <span>
            CAPABILITY
          </span>

          <span>
            PROVENANCE
          </span>

          <span>
            INTENT
          </span>

          <span>
            LINEAGE
          </span>
        </motion.div>
      )}
    </motion.div>
  );
}

function TwinScene() {
  return (
    <motion.section
      className="cin-scene cin-twin"
      initial={{
        opacity: 0,
      }}
      animate={{
        opacity: 1,
      }}
      exit={{
        opacity: 0,
      }}
    >
      <div className="cin-centered-heading">
        <span>
          02 / BUILD THE TWIN
        </span>

        <h1>
          One system.
          <strong>
            {" "}
            Two realities.
          </strong>
        </h1>

        <p>
          A live agent on one side.
          An executable security model on the other.
        </p>
      </div>

      <div className="cin-twin-layout">
        <TwinPanel />

        <div className="cin-sync-column">
          <motion.div
            className="cin-sync-line"
            initial={{
              scaleY: 0,
            }}
            animate={{
              scaleY: 1,
            }}
            transition={{
              duration: 1.2,
              delay: 0.35,
            }}
          />

          <motion.div
            className="cin-sync-core"
            initial={{
              scale: 0,
              opacity: 0,
            }}
            animate={{
              scale: 1,
              opacity: 1,
            }}
            transition={{
              delay: 0.75,
              duration: 0.7,
            }}
          >
            <BrainCircuit size={21} />
          </motion.div>

          <span>
            SYNC
          </span>
        </div>

        <TwinPanel twin />
      </div>
    </motion.section>
  );
}

/* =========================================================
   ATTACK
   ========================================================= */

function AttackConnector({
  delay,
}: {
  delay: number;
}) {
  return (
    <div className="cin-attack-connector">
      <motion.div
        className="cin-attack-line"
        initial={{
          scaleX: 0,
        }}
        animate={{
          scaleX: 1,
        }}
        transition={{
          delay,
          duration: 0.65,
        }}
      />

      <motion.span
        initial={{
          left: "0%",
          opacity: 0,
        }}
        animate={{
          left: "100%",
          opacity: [
            0,
            1,
            0,
          ],
        }}
        transition={{
          delay:
            delay + 0.3,
          duration: 1.4,
          repeat: Infinity,
          repeatDelay: 0.7,
          ease: "linear",
        }}
      />
    </div>
  );
}

function AttackScene() {
  return (
    <motion.section
      className="cin-scene cin-attack"
      initial={{
        opacity: 0,
      }}
      animate={{
        opacity: 1,
      }}
      exit={{
        opacity: 0,
      }}
    >
      <div className="cin-centered-heading attack-heading">
        <span>
          03 / ATTACK MY AGENT
        </span>

        <h1>
          The twin finds the path
          <strong>
            {" "}
            before production does.
          </strong>
        </h1>
      </div>

      <motion.div
        className="cin-attack-origin"
        initial={{
          opacity: 0,
          y: -10,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        transition={{
          delay: 0.5,
        }}
      >
        <ScanSearch size={15} />

        <div>
          <strong>
            WEB_UNTRUSTED
          </strong>

          <span>
            invoice_1042.pdf
          </span>
        </div>
      </motion.div>

      <div className="cin-attack-flow">
        <ToolNode
          icon={FileText}
          title="invoice_reader"
          subtitle="DOCUMENT"
          delay={0.15}
        />

        <AttackConnector
          delay={0.65}
        />

        <ToolNode
          icon={Database}
          title="customer_database"
          subtitle="CustomerPII"
          danger
          delay={0.35}
        />

        <AttackConnector
          delay={1.1}
        />

        <ToolNode
          icon={BrainCircuit}
          title="summarizer"
          subtitle="DerivedFrom<CustomerPII>"
          danger
          delay={0.55}
        />

        <AttackConnector
          delay={1.55}
        />

        <ToolNode
          icon={Globe2}
          title="external_http"
          subtitle="EXTERNAL"
          danger
          delay={0.75}
        />
      </div>

      <motion.div
        className="cin-evidence-grid"
        initial={{
          opacity: 0,
        }}
        animate={{
          opacity: 1,
        }}
        transition={{
          delay: 1.7,
          duration: 0.8,
        }}
      >
        <div>
          <span>
            PROVENANCE
          </span>

          <strong>
            WEB_UNTRUSTED
          </strong>
        </div>

        <div>
          <span>
            INTENT
          </span>

          <strong>
            MISMATCH
          </strong>
        </div>

        <div>
          <span>
            LINEAGE
          </span>

          <strong>
            CustomerPII
          </strong>
        </div>

        <div className="critical-evidence">
          <span>
            PATH RISK
          </span>

          <strong>
            CRITICAL
          </strong>
        </div>
      </motion.div>
    </motion.section>
  );
}

/* =========================================================
   CONTROL
   ========================================================= */

function ControlScene() {
  return (
    <motion.section
      className="cin-scene cin-control"
      initial={{
        opacity: 0,
      }}
      animate={{
        opacity: 1,
      }}
      exit={{
        opacity: 0,
        scale: 0.96,
      }}
    >
      <div className="cin-centered-heading">
        <span>
          04 / GOVERN
        </span>

        <h1>
          Discover.
          <strong>
            {" "}
            Compile. Prove.
          </strong>
        </h1>

        <p>
          The discovered failure becomes
          an enforceable deterministic control.
        </p>
      </div>

      <motion.div
        className="cin-policy-hero"
        initial={{
          opacity: 0,
          scale: 0.93,
          y: 18,
        }}
        animate={{
          opacity: 1,
          scale: 1,
          y: 0,
        }}
        transition={{
          duration: 0.9,
          delay: 0.35,
          ease: [0.16, 1, 0.3, 1],
        }}
      >
        <div className="cin-policy-symbol">
          <ShieldCheck
            size={31}
            strokeWidth={1.4}
          />
        </div>

        <div className="cin-policy-content">
          <span>
            MINIMUM GUARDRAIL
          </span>

          <strong>
            CustomerPII /
            DerivedFrom&lt;CustomerPII&gt;
          </strong>

          <div>
            TO EXTERNAL DESTINATION
          </div>
        </div>

        <motion.div
          className="cin-block-badge"
          initial={{
            opacity: 0,
            x: 18,
          }}
          animate={{
            opacity: 1,
            x: 0,
          }}
          transition={{
            delay: 1,
          }}
        >
          BLOCK
        </motion.div>
      </motion.div>

      <motion.div
        className="cin-proof-grid"
        initial={{
          opacity: 0,
          y: 15,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        transition={{
          delay: 1.25,
          duration: 0.75,
        }}
      >
        <div>
          <CheckCircle2 size={18} />

          <span>
            ATTACK REPLAY
          </span>

          <strong>
            BLOCKED
          </strong>
        </div>

        <div>
          <CheckCircle2 size={18} />

          <span>
            LEGITIMATE WORK
          </span>

          <strong>
            ALLOWED
          </strong>
        </div>

        <div>
          <LockKeyhole size={18} />

          <span>
            FALSE POSITIVES
          </span>

          <strong>
            0
          </strong>
        </div>
      </motion.div>
    </motion.section>
  );
}

/* =========================================================
   BRAND EMBLEM
   ========================================================= */

function BrandEmblem() {
  return (
    <motion.svg
      className="cin-brand-svg"
      viewBox="0 0 500 350"
      aria-label="AegisTwin"
    >
      <defs>
        <linearGradient
          id="cinSilver"
          x1="0"
          y1="0"
          x2="1"
          y2="1"
        >
          <stop
            offset="0%"
            stopColor="#ffffff"
          />

          <stop
            offset="45%"
            stopColor="#aab2bb"
          />

          <stop
            offset="70%"
            stopColor="#f4f6f7"
          />

          <stop
            offset="100%"
            stopColor="#747e88"
          />
        </linearGradient>

        <linearGradient
          id="cinGold"
          x1="0"
          y1="0"
          x2="1"
          y2="1"
        >
          <stop
            offset="0%"
            stopColor="#fff0ac"
          />

          <stop
            offset="45%"
            stopColor="#e7b94d"
          />

          <stop
            offset="72%"
            stopColor="#a66f1e"
          />

          <stop
            offset="100%"
            stopColor="#f5d477"
          />
        </linearGradient>

        <filter id="cinGlow">
          <feGaussianBlur
            stdDeviation="5"
            result="blur"
          />

          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <motion.ellipse
        cx="250"
        cy="175"
        rx="188"
        ry="145"
        fill="none"
        stroke="rgba(220,177,79,.15)"
        strokeWidth="1"
        initial={{
          pathLength: 0,
          opacity: 0,
        }}
        animate={{
          pathLength: 1,
          opacity: 1,
        }}
        transition={{
          duration: 2.1,
        }}
      />

      <motion.path
        d="
          M244 45
          C176 42 115 92 106 164
          C97 241 142 294 220 311
          C238 315 244 301 244 282
          Z
        "
        fill="rgba(255,255,255,.015)"
        stroke="url(#cinSilver)"
        strokeWidth="3"
        initial={{
          pathLength: 0,
          opacity: 0,
        }}
        animate={{
          pathLength: 1,
          opacity: 1,
        }}
        transition={{
          duration: 1.8,
          ease: [0.16, 1, 0.3, 1],
        }}
      />

      <motion.path
        d="
          M256 45
          C324 42 385 92 394 164
          C403 241 358 294 280 311
          C262 315 256 301 256 282
          Z
        "
        fill="rgba(215,169,71,.018)"
        stroke="url(#cinGold)"
        strokeWidth="3"
        initial={{
          pathLength: 0,
          opacity: 0,
        }}
        animate={{
          pathLength: 1,
          opacity: 1,
        }}
        transition={{
          duration: 1.8,
          ease: [0.16, 1, 0.3, 1],
        }}
      />

      {[
        "M230 87 C177 82 139 116 136 164",
        "M230 123 C188 116 161 144 161 181",
        "M230 159 C194 155 178 180 181 210",
        "M230 223 C194 216 175 240 184 267",
      ].map(
        (path, index) => (
          <motion.path
            key={path}
            d={path}
            fill="none"
            stroke="rgba(224,231,236,.5)"
            strokeWidth="1.2"
            initial={{
              pathLength: 0,
              opacity: 0,
            }}
            animate={{
              pathLength: 1,
              opacity: 1,
            }}
            transition={{
              duration: 1.3,
              delay:
                0.5 +
                index * 0.12,
            }}
          />
        ),
      )}

      {[
        [290, 96, 332, 125],
        [332, 125, 363, 96],
        [332, 125, 345, 181],
        [345, 181, 378, 164],
        [345, 181, 369, 227],
        [369, 227, 333, 269],
        [333, 269, 300, 221],
        [300, 221, 345, 181],
      ].map(
        (
          line,
          index,
        ) => (
          <motion.line
            key={index}
            x1={line[0]}
            y1={line[1]}
            x2={line[2]}
            y2={line[3]}
            stroke="rgba(233,185,73,.62)"
            strokeWidth="1.2"
            initial={{
              pathLength: 0,
              opacity: 0,
            }}
            animate={{
              pathLength: 1,
              opacity: 1,
            }}
            transition={{
              duration: 1,
              delay:
                0.55 +
                index * 0.08,
            }}
          />
        ),
      )}

      {[
        [290, 96],
        [332, 125],
        [363, 96],
        [345, 181],
        [378, 164],
        [369, 227],
        [333, 269],
        [300, 221],
      ].map(
        (
          node,
          index,
        ) => (
          <motion.circle
            key={index}
            cx={node[0]}
            cy={node[1]}
            r={
              index % 3 === 0
                ? 6
                : 4
            }
            fill="#efc45a"
            filter="url(#cinGlow)"
            initial={{
              scale: 0,
              opacity: 0,
            }}
            animate={{
              scale: 1,
              opacity: 1,
            }}
            transition={{
              delay:
                0.8 +
                index * 0.08,
            }}
          />
        ),
      )}

      <motion.line
        x1="250"
        y1="30"
        x2="250"
        y2="320"
        stroke="url(#cinGold)"
        strokeWidth="1.8"
        initial={{
          pathLength: 0,
        }}
        animate={{
          pathLength: 1,
        }}
        transition={{
          duration: 1.5,
        }}
      />

      <motion.circle
        cx="250"
        cy="177"
        r="29"
        fill="rgba(215,169,71,.08)"
        stroke="url(#cinGold)"
        strokeWidth="1.5"
        animate={{
          r: [
            27,
            32,
            27,
          ],
          opacity: [
            0.6,
            1,
            0.6,
          ],
        }}
        transition={{
          duration: 3,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />

      <circle
        cx="250"
        cy="177"
        r="13"
        fill="#e5b648"
        filter="url(#cinGlow)"
      />

      <circle
        cx="250"
        cy="177"
        r="5"
        fill="#fff8dc"
      />
    </motion.svg>
  );
}

/* =========================================================
   BRAND LETTER
   ========================================================= */

function BrandLetter({
  letter,
  index,
  gold = false,
}: {
  letter: string;
  index: number;
  gold?: boolean;
}) {
  return (
    <motion.span
      className={
        gold
          ? "brand-letter brand-letter-gold"
          : "brand-letter brand-letter-silver"
      }
      initial={{
        opacity: 0,
        y: gold
          ? 42
          : -42,
        rotateX: gold
          ? -70
          : 70,
        rotateY: gold
          ? 24
          : -24,
        scale: 0.82,
        filter:
          "blur(14px)",
      }}
      animate={{
        opacity: 1,
        y: 0,
        rotateX: 0,
        rotateY: 0,
        scale: 1,
        filter:
          "blur(0px)",
      }}
      transition={{
        duration: 0.9,
        delay:
          0.75 +
          index * 0.09,
        ease: [0.16, 1, 0.3, 1],
      }}
    >
      {letter}
    </motion.span>
  );
}

/* =========================================================
   BRAND
   ========================================================= */

function BrandScene() {
  const aegisLetters =
    "AEGIS".split("");

  const twinLetters =
    "TWIN".split("");

  return (
    <motion.section
      className="cin-scene cin-brand-scene"
      initial={{
        opacity: 0,
      }}
      animate={{
        opacity: 1,
      }}
      transition={{
        duration: 0.7,
      }}
    >
      <motion.div
        className="brand-energy-ring brand-energy-ring-one"
        initial={{
          opacity: 0,
          scale: 0.35,
        }}
        animate={{
          opacity: [
            0,
            0.65,
            0.18,
          ],
          scale: [
            0.35,
            1,
            1.18,
          ],
        }}
        transition={{
          duration: 2,
          ease: [0.16, 1, 0.3, 1],
        }}
      />

      <motion.div
        className="brand-energy-ring brand-energy-ring-two"
        initial={{
          opacity: 0,
          scale: 0.45,
        }}
        animate={{
          opacity: [
            0,
            0.35,
            0.1,
          ],
          scale: [
            0.45,
            1.1,
            1.35,
          ],
        }}
        transition={{
          duration: 2.4,
          delay: 0.15,
          ease: [0.16, 1, 0.3, 1],
        }}
      />

      <motion.div
        className="brand-ignition"
        initial={{
          opacity: 0,
          scaleY: 0,
        }}
        animate={{
          opacity: [
            0,
            1,
            0.4,
          ],
          scaleY: 1,
        }}
        transition={{
          duration: 1.15,
          ease: [0.16, 1, 0.3, 1],
        }}
      />

      <motion.div
        className="cin-brand-emblem premium-brand-emblem"
        initial={{
          opacity: 0,
          scale: 0.72,
          y: 18,
          filter:
            "blur(20px)",
        }}
        animate={{
          opacity: 1,
          scale: 1,
          y: 0,
          filter:
            "blur(0px)",
        }}
        transition={{
          duration: 1.45,
          delay: 0.15,
          ease: [0.16, 1, 0.3, 1],
        }}
      >
        <BrandEmblem />
      </motion.div>

      <motion.div
        className="premium-wordmark"
        initial={{
          letterSpacing:
            "0.22em",
        }}
        animate={{
          letterSpacing:
            "0.035em",
        }}
        transition={{
          duration: 1.5,
          delay: 0.65,
          ease: [0.16, 1, 0.3, 1],
        }}
      >
        <span className="premium-word">
          {aegisLetters.map(
            (
              letter,
              index,
            ) => (
              <BrandLetter
                key={`aegis-${index}`}
                letter={letter}
                index={index}
              />
            ),
          )}
        </span>

        <motion.span
          className="brand-divider"
          initial={{
            scaleY: 0,
            opacity: 0,
          }}
          animate={{
            scaleY: 1,
            opacity: 0.75,
          }}
          transition={{
            delay: 1.2,
            duration: 0.65,
          }}
        />

        <span className="premium-word">
          {twinLetters.map(
            (
              letter,
              index,
            ) => (
              <BrandLetter
                key={`twin-${index}`}
                letter={letter}
                index={
                  index + 5
                }
                gold
              />
            ),
          )}
        </span>

        <motion.div
          className="premium-wordmark-sheen"
          initial={{
            x: "-190%",
          }}
          animate={{
            x: "250%",
          }}
          transition={{
            delay: 2.2,
            duration: 1.5,
            ease: "easeInOut",
          }}
        />
      </motion.div>

      <motion.div
        className="brand-title-line"
        initial={{
          scaleX: 0,
          opacity: 0,
        }}
        animate={{
          scaleX: 1,
          opacity: 1,
        }}
        transition={{
          delay: 1.65,
          duration: 1.1,
          ease: [0.16, 1, 0.3, 1],
        }}
      >
        <span />
      </motion.div>

      <motion.div
        className="premium-brand-subtitle"
        initial={{
          opacity: 0,
          y: 13,
          letterSpacing:
            "0.35em",
        }}
        animate={{
          opacity: 1,
          y: 0,
          letterSpacing:
            "0.18em",
        }}
        transition={{
          delay: 2,
          duration: 1,
          ease: [0.16, 1, 0.3, 1],
        }}
      >
        AI CONTROL LAYER

        <i />

        SECURITY DIGITAL TWIN
      </motion.div>

      <motion.div
        className="premium-brand-values"
        initial={{
          opacity: 0,
          y: 8,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        transition={{
          delay: 2.85,
          duration: 0.8,
        }}
      >
        <span>
          OBSERVE
        </span>

        <i />

        <span>
          UNDERSTAND
        </span>

        <i />

        <span>
          GOVERN
        </span>

        <i />

        <span>
          PROTECT
        </span>

        <i />

        <span>
          EVOLVE
        </span>
      </motion.div>

      <motion.div
        className="brand-idle-pulse"
        initial={{
          opacity: 0,
          scale: 0.8,
        }}
        animate={{
          opacity: [
            0,
            0.3,
            0,
          ],
          scale: [
            0.8,
            1.25,
            1.5,
          ],
        }}
        transition={{
          delay: 3.8,
          duration: 3,
          repeat: Infinity,
          repeatDelay: 0.4,
          ease: "easeOut",
        }}
      />
    </motion.section>
  );
}

/* =========================================================
   MAIN SPLASH
   ========================================================= */

export default function SplashScreen({
  onComplete,
}: SplashScreenProps) {
  const [
    phase,
    setPhase,
  ] =
    useState<Phase>(
      "observe",
    );

  const completed =
    useRef(false);

  useEffect(() => {
    const timers = [
      window.setTimeout(
        () =>
          setPhase(
            "twin",
          ),
        3200,
      ),

      window.setTimeout(
        () =>
          setPhase(
            "attack",
          ),
        6500,
      ),

      window.setTimeout(
        () =>
          setPhase(
            "control",
          ),
        10000,
      ),

      window.setTimeout(
        () =>
          setPhase(
            "brand",
          ),
        12500,
      ),

      window.setTimeout(
        () => {
          if (
            completed.current
          ) {
            return;
          }

          completed.current =
            true;

          onComplete();
        },
        TOTAL_TIME,
      ),
    ];

    return () => {
      timers.forEach(
        (timer) => {
          window.clearTimeout(
            timer,
          );
        },
      );
    };
  }, [onComplete]);

  return (
    <main
      className={`cin-splash cin-phase-${phase}`}
    >
      <div className="cin-bg-blue" />
      <div className="cin-bg-gold" />
      <div className="cin-noise" />
      <div className="cin-vignette" />

      {phase !==
        "brand" && (
        <header className="cin-global-header">
          <div>
            <span />

            AEGISTWIN SECURITY ENGINE
          </div>

          <strong>
            AUTONOMOUS AI CONTROL
          </strong>
        </header>
      )}

      <AnimatePresence
        mode="wait"
      >
        {phase ===
          "observe" && (
          <ObserveScene
            key="observe"
          />
        )}

        {phase ===
          "twin" && (
          <TwinScene
            key="twin"
          />
        )}

        {phase ===
          "attack" && (
          <AttackScene
            key="attack"
          />
        )}

        {phase ===
          "control" && (
          <ControlScene
            key="control"
          />
        )}

        {phase ===
          "brand" && (
          <BrandScene
            key="brand"
          />
        )}
      </AnimatePresence>
    </main>
  );
}