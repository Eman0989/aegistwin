import { motion } from "framer-motion";

import {
  ArrowRight,
  Boxes,
  Database,
  PlayCircle,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";

import FlowFieldBackground from
  "../components/landing/FlowFieldBackground";

import PlatformSection from
  "../components/landing/PlatformSection";

import SecuritySection from
  "../components/landing/SecuritySection";

import TwinLabSection from
  "../components/landing/TwinLabSection";

import DocsSection from
  "../components/landing/DocsSection";

import HeroCoreMark from
  "../components/HeroCoreMark";

import aegisLogo from
  "../assets/aegistwin-logo.png";

interface LandingPageProps {
  onOpenConsole: () => void;
}

export default function LandingPage({
  onOpenConsole,
}: LandingPageProps) {
  return (
    <div className="landing-page">
      {/* =====================================================
          LIVE PREMIUM BACKGROUND
          ===================================================== */}

      <FlowFieldBackground />

      {/* =====================================================
          NAVIGATION
          ===================================================== */}

      <header className="landing-nav-shell">
        <div className="landing-nav">
          {/* BRAND */}

          <div className="landing-nav__brand">
            <div className="landing-nav__logo-crop">
              <img
                src={aegisLogo}
                alt=""
                aria-hidden="true"
              />
            </div>

            <div className="landing-nav__wordmark">
              <span className="nav-word-silver">
                AEGIS
              </span>

              <span className="nav-word-gold">
                TWIN
              </span>
            </div>
          </div>

          {/* CENTER NAVIGATION */}

          <nav
            className="landing-nav__menu"
            aria-label="Primary navigation"
          >
            <a
              href="#platform-details"
              className="active"
            >
              Platform
            </a>

            <a href="#security-details">
              Security
            </a>

            <a href="#twin-lab-details">
              Twin Lab
            </a>

            <a href="#docs-details">
              Docs
            </a>
          </nav>

          {/* OPEN CONSOLE */}

          <button
            type="button"
            className="landing-console-btn"
            onClick={onOpenConsole}
          >
            <span>
              OPEN CONSOLE
            </span>

            <ArrowRight size={17} />
          </button>
        </div>
      </header>

      {/* =====================================================
          HERO SECTION
          ORIGINAL / FROZEN
          ===================================================== */}

      <main
        className="landing-hero"
        id="platform"
      >
        {/* ===================================================
            LEFT CONTENT
            =================================================== */}

        <section className="landing-hero__content">
          <motion.p
            className="landing-eyebrow"
            initial={{
              opacity: 0,
              y: 14,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            transition={{
              duration: 0.7,
              ease: [
                0.16,
                1,
                0.3,
                1,
              ],
            }}
          >
            AUTONOMOUS AI AGENT SECURITY
          </motion.p>

          <motion.h1
            className="landing-title"
            initial={{
              opacity: 0,
              y: 24,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            transition={{
              delay: 0.12,
              duration: 0.9,
              ease: [
                0.16,
                1,
                0.3,
                1,
              ],
            }}
          >
            <span>
              Discover Risk.
            </span>

            <span className="gold">
              Prove the Fix.
            </span>
          </motion.h1>

          <motion.p
            className="landing-subtitle"
            initial={{
              opacity: 0,
              y: 18,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            transition={{
              delay: 0.27,
              duration: 0.85,
              ease: [
                0.16,
                1,
                0.3,
                1,
              ],
            }}
          >
            A security digital twin that discovers
            dangerous agent behavior, compiles targeted
            guardrails, and verifies the fix before
            production exposure.
          </motion.p>

          {/* =================================================
              PRIMARY ACTIONS
              ================================================= */}

          <motion.div
            className="landing-actions"
            initial={{
              opacity: 0,
              y: 18,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            transition={{
              delay: 0.42,
              duration: 0.8,
              ease: [
                0.16,
                1,
                0.3,
                1,
              ],
            }}
          >
            <button
              type="button"
              className="landing-btn landing-btn--primary"
              onClick={onOpenConsole}
            >
              <span>
                ANALYZE AN AGENT
              </span>

              <ArrowRight size={18} />
            </button>

            <button
              type="button"
              className="landing-btn landing-btn--secondary"
              onClick={onOpenConsole}
            >
              <PlayCircle size={18} />

              <span>
                WATCH ATTACK REPLAY
              </span>
            </button>
          </motion.div>
        </section>

        {/* ===================================================
            RIGHT VISUAL
            =================================================== */}

        <motion.section
          className="landing-hero__visual"
          id="twin-lab"
          initial={{
            opacity: 0,
            x: 28,
            scale: 0.97,
          }}
          animate={{
            opacity: 1,
            x: 0,
            scale: 1,
          }}
          transition={{
            delay: 0.2,
            duration: 1.15,
            ease: [
              0.16,
              1,
              0.3,
              1,
            ],
          }}
        >
          {/* TOP LEFT CARD */}

          <motion.div
            className="
              landing-float-card
              landing-float-card--top-left
            "
            animate={{
              y: [
                0,
                -5,
                0,
              ],
            }}
            transition={{
              duration: 7,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          >
            <div className="landing-float-card__icon">
              <Boxes size={17} />
            </div>

            <div className="landing-float-card__copy">
              <strong>
                4
              </strong>

              <span>
                Tools Mapped
              </span>
            </div>
          </motion.div>

          {/* TOP RIGHT CARD */}

          <motion.div
            className="
              landing-float-card
              landing-float-card--top-right
            "
            animate={{
              y: [
                0,
                5,
                0,
              ],
            }}
            transition={{
              duration: 8.1,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          >
            <div className="landing-float-card__icon">
              <Database size={17} />
            </div>

            <div className="landing-float-card__copy">
              <strong>
                3
              </strong>

              <span>
                Data Boundaries
              </span>
            </div>
          </motion.div>

          {/* =================================================
              UNIQUE HERO MARK
              ================================================= */}

          <div className="landing-hero-mark-shell">
            <div className="landing-hero-mark-glow" />

            <HeroCoreMark />
          </div>

          {/* BOTTOM LEFT CARD */}

          <motion.div
            className="
              landing-float-card
              landing-float-card--bottom-left
              landing-float-card--risk
            "
            animate={{
              y: [
                0,
                -5,
                0,
              ],
            }}
            transition={{
              duration: 7.4,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          >
            <div className="landing-float-card__icon">
              <TriangleAlert size={17} />
            </div>

            <div className="landing-float-card__copy">
              <strong>
                1
              </strong>

              <span>
                Critical Attack Path
              </span>
            </div>
          </motion.div>

          {/* BOTTOM RIGHT CARD */}

          <motion.div
            className="
              landing-float-card
              landing-float-card--bottom-right
            "
            animate={{
              y: [
                0,
                5,
                0,
              ],
            }}
            transition={{
              duration: 8.4,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          >
            <div className="landing-float-card__icon">
              <ShieldCheck size={17} />
            </div>

            <div className="landing-float-card__copy">
              <strong>
                1
              </strong>

              <span>
                Guardrail Active
              </span>
            </div>
          </motion.div>
        </motion.section>
      </main>

      {/* =====================================================
          ORIGINAL WORKFLOW / SECURITY STRIP
          ===================================================== */}

      <section
        className="landing-proof-strip"
        id="security"
      >
        <div className="landing-proof-strip__line" />

        <div className="landing-proof-strip__content">
          {/* OBSERVE */}

          <div className="landing-proof-step">
            <span>
              01
            </span>

            <strong>
              OBSERVE
            </strong>

            <small>
              Map agent behavior
            </small>
          </div>

          <div className="landing-proof-connector">
            <span />
          </div>

          {/* ATTACK */}

          <div className="landing-proof-step">
            <span>
              02
            </span>

            <strong>
              ATTACK
            </strong>

            <small>
              Discover exploit paths
            </small>
          </div>

          <div className="landing-proof-connector">
            <span />
          </div>

          {/* COMPILE */}

          <div className="landing-proof-step">
            <span>
              03
            </span>

            <strong>
              COMPILE
            </strong>

            <small>
              Generate minimum guardrail
            </small>
          </div>

          <div className="landing-proof-connector">
            <span />
          </div>

          {/* PROVE */}

          <div className="landing-proof-step">
            <span>
              04
            </span>

            <strong>
              PROVE
            </strong>

            <small>
              Replay and verify
            </small>
          </div>
        </div>
      </section>

      {/* =====================================================
          PLATFORM
          ===================================================== */}

      <PlatformSection
        onOpenConsole={onOpenConsole}
      />

      {/* =====================================================
          SECURITY
          ===================================================== */}

      <SecuritySection
        onOpenConsole={onOpenConsole}
      />

      {/* =====================================================
          TWIN LAB
          ===================================================== */}

      <TwinLabSection
        onOpenConsole={onOpenConsole}
      />

      {/* =====================================================
          DOCS
          ===================================================== */}

      <DocsSection
        onOpenConsole={onOpenConsole}
      />
    </div>
  );
}