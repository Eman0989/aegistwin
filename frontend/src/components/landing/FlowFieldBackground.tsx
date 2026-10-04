import {
  useEffect,
  useRef,
} from "react";

type Particle = {
  x: number;
  y: number;

  previousX: number;
  previousY: number;

  speed: number;
  size: number;

  life: number;
  maxLife: number;

  depth: number;

  tone:
    | "gold"
    | "blue"
    | "silver";
};

export default function FlowFieldBackground() {
  const canvasRef =
    useRef<HTMLCanvasElement | null>(
      null,
    );

  useEffect(() => {
    const canvas =
      canvasRef.current;

    if (!canvas) return;

    const context =
      canvas.getContext("2d");

    if (!context) return;

    let frame = 0;

    let width =
      window.innerWidth;

    let height =
      window.innerHeight;

    let dpr = Math.min(
      window.devicePixelRatio || 1,
      2,
    );

    const mouse = {
      x: width / 2,
      y: height / 2,
      targetX: width / 2,
      targetY: height / 2,
    };

    let particles: Particle[] =
      [];

    const PARTICLE_COUNT =
      Math.min(
        115,
        Math.floor(
          (width * height) /
            12500,
        ),
      );

    /* ==============================================
       CREATE PARTICLE
       ============================================== */

    const createParticle = (
      randomPosition = true,
    ): Particle => {
      const toneRandom =
        Math.random();

      const tone:
        Particle["tone"] =
        toneRandom < 0.55
          ? "gold"
          : toneRandom < 0.78
            ? "blue"
            : "silver";

      const x = randomPosition
        ? Math.random() * width
        : -30;

      const y =
        Math.random() * height;

      const depth =
        Math.random();

      return {
        x,
        y,

        previousX: x,
        previousY: y,

        speed:
          0.35 +
          depth * 0.75,

        size:
          0.65 +
          depth * 1.4,

        life:
          Math.random() * 300,

        maxLife:
          280 +
          Math.random() * 260,

        depth,

        tone,
      };
    };

    /* ==============================================
       RESET
       ============================================== */

    const resetParticles = () => {
      particles =
        Array.from(
          {
            length:
              PARTICLE_COUNT,
          },
          () =>
            createParticle(),
        );
    };

    /* ==============================================
       RESIZE
       ============================================== */

    const resize = () => {
      width =
        window.innerWidth;

      height =
        window.innerHeight;

      dpr = Math.min(
        window.devicePixelRatio ||
          1,
        2,
      );

      canvas.width =
        width * dpr;

      canvas.height =
        height * dpr;

      canvas.style.width =
        `${width}px`;

      canvas.style.height =
        `${height}px`;

      context.setTransform(
        dpr,
        0,
        0,
        dpr,
        0,
        0,
      );

      resetParticles();
    };

    /* ==============================================
       POINTER PARALLAX
       ============================================== */

    const handlePointerMove = (
      event: PointerEvent,
    ) => {
      mouse.targetX =
        event.clientX;

      mouse.targetY =
        event.clientY;
    };

    /* ==============================================
       FLOW FIELD
       ============================================== */

    const getFlowAngle = (
      x: number,
      y: number,
      time: number,
    ) => {
      const nx =
        x * 0.0022;

      const ny =
        y * 0.002;

      const waveOne =
        Math.sin(
          nx +
            time * 0.00019,
        );

      const waveTwo =
        Math.cos(
          ny * 1.4 -
            time * 0.00016,
        );

      const waveThree =
        Math.sin(
          (nx + ny) *
            0.72 +
            time * 0.00011,
        );

      return (
        waveOne * 0.62 +
        waveTwo * 0.37 +
        waveThree * 0.3
      );
    };

    /* ==============================================
       QUIET AREA BEHIND HERO SYMBOL

       The hero visual is approximately on the
       right side of the viewport.
       ============================================== */

    const getQuietFactor = (
      x: number,
      y: number,
    ) => {
      const centerX =
        width * 0.74;

      const centerY =
        height * 0.53;

      const radiusX =
        Math.max(
          250,
          width * 0.19,
        );

      const radiusY =
        Math.max(
          250,
          height * 0.34,
        );

      const dx =
        (x - centerX) /
        radiusX;

      const dy =
        (y - centerY) /
        radiusY;

      const distance =
        Math.sqrt(
          dx * dx +
            dy * dy,
        );

      if (distance >= 1) {
        return 1;
      }

      return (
        0.15 +
        distance * 0.85
      );
    };

    /* ==============================================
       PARTICLE COLORS
       ============================================== */

    const particleColor = (
      particle: Particle,
      alpha: number,
    ) => {
      if (
        particle.tone ===
        "gold"
      ) {
        return `rgba(242,196,88,${alpha})`;
      }

      if (
        particle.tone ===
        "blue"
      ) {
        return `rgba(103,173,221,${alpha})`;
      }

      return `rgba(216,226,235,${alpha})`;
    };

    /* ==============================================
       AMBIENT BACKGROUND LIGHT
       ============================================== */

    const drawAmbientLight =
      () => {
        const leftGlow =
          context.createRadialGradient(
            width * 0.16,
            height * 0.44,
            0,
            width * 0.16,
            height * 0.44,
            width * 0.45,
          );

        leftGlow.addColorStop(
          0,
          "rgba(38,92,154,0.08)",
        );

        leftGlow.addColorStop(
          1,
          "rgba(38,92,154,0)",
        );

        context.fillStyle =
          leftGlow;

        context.fillRect(
          0,
          0,
          width,
          height,
        );

        const rightGlow =
          context.createRadialGradient(
            width * 0.79,
            height * 0.48,
            0,
            width * 0.79,
            height * 0.48,
            width * 0.42,
          );

        rightGlow.addColorStop(
          0,
          "rgba(225,175,56,0.085)",
        );

        rightGlow.addColorStop(
          1,
          "rgba(225,175,56,0)",
        );

        context.fillStyle =
          rightGlow;

        context.fillRect(
          0,
          0,
          width,
          height,
        );
      };

    /* ==============================================
       LARGE PREMIUM FLOW RIBBONS
       ============================================== */

    const drawFlowRibbons = (
      time: number,
    ) => {
      for (
        let ribbon = 0;
        ribbon < 5;
        ribbon += 1
      ) {
        context.beginPath();

        const verticalOffset =
          height *
          (0.16 +
            ribbon * 0.17);

        for (
          let x = -100;
          x <= width + 100;
          x += 16
        ) {
          const y =
            verticalOffset +
            Math.sin(
              x * 0.0032 +
                time *
                  0.00016 +
                ribbon * 0.8,
            ) *
              (32 +
                ribbon * 7) +
            Math.cos(
              x * 0.0017 -
                time *
                  0.0001,
            ) *
              18;

          if (x === -100) {
            context.moveTo(
              x,
              y,
            );
          } else {
            context.lineTo(
              x,
              y,
            );
          }
        }

        const alpha =
          ribbon % 2 === 0
            ? 0.055
            : 0.035;

        context.strokeStyle =
          ribbon % 3 === 0
            ? `rgba(235,187,72,${alpha})`
            : ribbon % 3 === 1
              ? `rgba(103,173,221,${alpha})`
              : `rgba(220,228,235,${alpha})`;

        context.lineWidth =
          1;

        context.stroke();
      }
    };

    /* ==============================================
       ANIMATE
       ============================================== */

    const animate = (
      time: number,
    ) => {
      /*
        Slight transparent fill instead of a total
        clear creates smooth, expensive-looking
        particle trails.
      */

      context.fillStyle =
        "rgba(3,5,8,0.16)";

      context.fillRect(
        0,
        0,
        width,
        height,
      );

      drawAmbientLight();
      drawFlowRibbons(time);

      mouse.x +=
        (mouse.targetX -
          mouse.x) *
        0.025;

      mouse.y +=
        (mouse.targetY -
          mouse.y) *
        0.025;

      for (
        let index = 0;
        index <
        particles.length;
        index += 1
      ) {
        let particle =
          particles[index];

        particle.previousX =
          particle.x;

        particle.previousY =
          particle.y;

        const angle =
          getFlowAngle(
            particle.x,
            particle.y,
            time,
          );

        /*
          Main flow moves mostly from left to right.
          Flow angle bends it into elegant waves.
        */

        particle.x +=
          (0.48 +
            Math.cos(angle) *
              0.72) *
          particle.speed;

        particle.y +=
          Math.sin(angle) *
          0.72 *
          particle.speed;

        /*
          Very subtle cursor parallax.
        */

        const mouseDX =
          mouse.x -
          width / 2;

        const mouseDY =
          mouse.y -
          height / 2;

        particle.x +=
          mouseDX *
          0.000035 *
          particle.depth;

        particle.y +=
          mouseDY *
          0.000025 *
          particle.depth;

        particle.life += 1;

        /*
          Reset once particle exits.
        */

        if (
          particle.x >
            width + 40 ||
          particle.y < -40 ||
          particle.y >
            height + 40 ||
          particle.life >
            particle.maxLife
        ) {
          particle =
            createParticle(false);

          particles[index] =
            particle;
        }

        const lifeProgress =
          particle.life /
          particle.maxLife;

        const fade =
          Math.sin(
            Math.min(
              1,
              lifeProgress,
            ) *
              Math.PI,
          );

        const quiet =
          getQuietFactor(
            particle.x,
            particle.y,
          );

        const depthAlpha =
          0.08 +
          particle.depth *
            0.32;

        const alpha =
          fade *
          depthAlpha *
          quiet;

        /*
          trail
        */

        context.beginPath();

        context.moveTo(
          particle.previousX,
          particle.previousY,
        );

        context.lineTo(
          particle.x,
          particle.y,
        );

        context.strokeStyle =
          particleColor(
            particle,
            alpha * 0.75,
          );

        context.lineWidth =
          0.45 +
          particle.depth *
            0.75;

        context.stroke();

        /*
          particle point
        */

        context.beginPath();

        context.arc(
          particle.x,
          particle.y,
          particle.size,
          0,
          Math.PI * 2,
        );

        context.fillStyle =
          particleColor(
            particle,
            alpha,
          );

        if (
          particle.depth >
          0.78
        ) {
          context.shadowBlur =
            11;

          context.shadowColor =
            particle.tone ===
            "blue"
              ? "rgba(103,173,221,0.35)"
              : "rgba(242,196,88,0.38)";
        }

        context.fill();

        context.shadowBlur = 0;
      }

      frame =
        requestAnimationFrame(
          animate,
        );
    };

    resize();

    /*
      Initial solid fill.
    */

    context.fillStyle =
      "#030508";

    context.fillRect(
      0,
      0,
      width,
      height,
    );

    frame =
      requestAnimationFrame(
        animate,
      );

    window.addEventListener(
      "resize",
      resize,
    );

    window.addEventListener(
      "pointermove",
      handlePointerMove,
    );

    return () => {
      cancelAnimationFrame(
        frame,
      );

      window.removeEventListener(
        "resize",
        resize,
      );

      window.removeEventListener(
        "pointermove",
        handlePointerMove,
      );
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="premium-flow-canvas"
      aria-hidden="true"
    />
  );
}