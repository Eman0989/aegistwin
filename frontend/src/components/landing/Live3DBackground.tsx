import {
  Canvas,
  useFrame,
  useThree,
} from "@react-three/fiber";

import {
  Float,
} from "@react-three/drei";

import {
  useMemo,
  useRef,
} from "react";

import * as THREE from "three";

/* =========================================================
   CINEMATIC AURORA BACKDROP
   ========================================================= */

const auroraVertex = `
  varying vec2 vUv;

  void main() {
    vUv = uv;

    gl_Position =
      projectionMatrix *
      modelViewMatrix *
      vec4(position, 1.0);
  }
`;

const auroraFragment = `
  varying vec2 vUv;

  uniform float uTime;
  uniform vec2 uMouse;

  float glowLine(
    vec2 uv,
    float y,
    float width
  ) {
    return smoothstep(
      width,
      0.0,
      abs(uv.y - y)
    );
  }

  void main() {
    vec2 uv = vUv;

    float t = uTime * 0.10;

    vec3 base =
      vec3(
        0.006,
        0.010,
        0.014
      );

    float goldWave =
      glowLine(
        uv,
        0.52 +
        sin(
          uv.x * 6.0 +
          t * 2.0
        ) * 0.055 +
        sin(
          uv.x * 2.0 -
          t
        ) * 0.035,
        0.18
      );

    float goldWave2 =
      glowLine(
        uv,
        0.69 +
        sin(
          uv.x * 4.0 -
          t * 1.4
        ) * 0.06,
        0.20
      );

    float blueWave =
      glowLine(
        uv,
        0.31 +
        sin(
          uv.x * 5.0 +
          t * 1.4
        ) * 0.07,
        0.22
      );

    float centerGold =
      exp(
        -10.0 *
        length(
          uv -
          vec2(
            0.72 +
            uMouse.x * 0.018,
            0.52 +
            uMouse.y * 0.018
          )
        )
      );

    float centerBlue =
      exp(
        -8.0 *
        length(
          uv -
          vec2(
            0.25,
            0.35
          )
        )
      );

    float verticalGlow =
      exp(
        -70.0 *
        abs(
          uv.x - 0.72
        )
      );

    vec3 gold =
      vec3(
        0.96,
        0.62,
        0.16
      );

    vec3 blue =
      vec3(
        0.10,
        0.47,
        0.68
      );

    vec3 color = base;

    color +=
      gold *
      goldWave *
      0.07;

    color +=
      gold *
      goldWave2 *
      0.035;

    color +=
      blue *
      blueWave *
      0.04;

    color +=
      gold *
      centerGold *
      0.11;

    color +=
      blue *
      centerBlue *
      0.055;

    color +=
      gold *
      verticalGlow *
      0.028;

    float vignette =
      smoothstep(
        0.96,
        0.25,
        distance(
          uv,
          vec2(0.5)
        )
      );

    color *=
      0.55 +
      vignette * 0.65;

    gl_FragColor =
      vec4(
        color,
        1.0
      );
  }
`;

function CinematicAurora() {
  const materialRef =
    useRef<THREE.ShaderMaterial>(
      null,
    );

  const uniforms =
    useMemo(
      () => ({
        uTime: {
          value: 0,
        },

        uMouse: {
          value:
            new THREE.Vector2(
              0,
              0,
            ),
        },
      }),
      [],
    );

  useFrame((state) => {
    if (
      !materialRef.current
    ) {
      return;
    }

    materialRef.current.uniforms.uTime.value =
      state.clock.elapsedTime;

    materialRef.current.uniforms.uMouse.value.set(
      state.pointer.x,
      state.pointer.y,
    );
  });

  return (
    <mesh
      position={[
        0,
        0,
        -14,
      ]}
      scale={[
        26,
        14,
        1,
      ]}
    >
      <planeGeometry
        args={[1, 1]}
      />

      <shaderMaterial
        ref={materialRef}
        uniforms={uniforms}
        vertexShader={
          auroraVertex
        }
        fragmentShader={
          auroraFragment
        }
        depthWrite={false}
      />
    </mesh>
  );
}

/* =========================================================
   PARTICLE DEPTH FIELD
   ========================================================= */

function ParticleField({
  count,
  radius,
  color,
  size,
  opacity,
  speed,
}: {
  count: number;
  radius: number;
  color: string;
  size: number;
  opacity: number;
  speed: number;
}) {
  const pointsRef =
    useRef<THREE.Points>(
      null,
    );

  const positions =
    useMemo(() => {
      const array =
        new Float32Array(
          count * 3,
        );

      for (
        let index = 0;
        index < count;
        index++
      ) {
        const angle =
          Math.random() *
          Math.PI *
          2;

        const distance =
          Math.pow(
            Math.random(),
            0.7,
          ) * radius;

        array[
          index * 3
        ] =
          Math.cos(angle) *
          distance;

        array[
          index * 3 + 1
        ] =
          (Math.random() -
            0.5) *
          10;

        array[
          index * 3 + 2
        ] =
          Math.sin(angle) *
            distance -
          5;
      }

      return array;
    }, [
      count,
      radius,
    ]);

  useFrame(
    (
      state,
      delta,
    ) => {
      if (
        !pointsRef.current
      ) {
        return;
      }

      pointsRef.current.rotation.y +=
        delta * speed;

      pointsRef.current.rotation.z =
        Math.sin(
          state.clock
            .elapsedTime *
            0.05,
        ) * 0.025;
    },
  );

  return (
    <points
      ref={pointsRef}
    >
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[
            positions,
            3,
          ]}
        />
      </bufferGeometry>

      <pointsMaterial
        color={color}
        size={size}
        transparent
        opacity={opacity}
        sizeAttenuation
        depthWrite={false}
        blending={
          THREE.AdditiveBlending
        }
      />
    </points>
  );
}

/* =========================================================
   ORBITING INTELLIGENCE NODE
   ========================================================= */

function OrbitNode({
  radius,
  speed,
  phase,
  vertical,
  color,
  size = 0.055,
}: {
  radius: number;
  speed: number;
  phase: number;
  vertical: number;
  color: string;
  size?: number;
}) {
  const nodeRef =
    useRef<THREE.Mesh>(
      null,
    );

  useFrame((state) => {
    if (
      !nodeRef.current
    ) {
      return;
    }

    const t =
      state.clock.elapsedTime *
        speed +
      phase;

    nodeRef.current.position.set(
      Math.cos(t) * radius,
      Math.sin(
        t * 1.4,
      ) *
        vertical,
      Math.sin(t) *
        radius *
        0.7,
    );
  });

  return (
    <mesh ref={nodeRef}>
      <sphereGeometry
        args={[
          size,
          18,
          18,
        ]}
      />

      <meshBasicMaterial
        color={color}
        transparent
        opacity={0.95}
        toneMapped={false}
      />
    </mesh>
  );
}

/* =========================================================
   DATA ARC
   ========================================================= */

function DataArc({
  start,
  middle,
  end,
  color,
  speed,
  delay,
}: {
  start:
    [
      number,
      number,
      number,
    ];

  middle:
    [
      number,
      number,
      number,
    ];

  end:
    [
      number,
      number,
      number,
    ];

  color: string;
  speed: number;
  delay: number;
}) {
  const packetRef =
    useRef<THREE.Mesh>(
      null,
    );

  const curve =
    useMemo(() => {
      return new THREE
        .QuadraticBezierCurve3(
          new THREE.Vector3(
            ...start,
          ),
          new THREE.Vector3(
            ...middle,
          ),
          new THREE.Vector3(
            ...end,
          ),
        );
    }, [
      start,
      middle,
      end,
    ]);

  const lineObject =
    useMemo(() => {
      const points =
        curve.getPoints(70);

      const geometry =
        new THREE.BufferGeometry()
          .setFromPoints(
            points,
          );

      const material =
        new THREE.LineBasicMaterial({
          color,
          transparent:
            true,
          opacity: 0.14,
          blending:
            THREE.AdditiveBlending,
        });

      return new THREE.Line(
        geometry,
        material,
      );
    }, [
      curve,
      color,
    ]);

  useFrame((state) => {
    if (
      !packetRef.current
    ) {
      return;
    }

    const raw =
      state.clock.elapsedTime *
        speed +
      delay;

    const progress =
      raw -
      Math.floor(raw);

    const point =
      curve.getPoint(
        progress,
      );

    packetRef.current.position.copy(
      point,
    );
  });

  return (
    <>
      <primitive
        object={lineObject}
      />

      <mesh ref={packetRef}>
        <sphereGeometry
          args={[
            0.045,
            18,
            18,
          ]}
        />

        <meshBasicMaterial
          color={color}
          transparent
          opacity={0.95}
          toneMapped={false}
        />
      </mesh>
    </>
  );
}

/* =========================================================
   PREMIUM SECURITY CORE
   ========================================================= */

function SecurityCore() {
  const groupRef =
    useRef<THREE.Group>(
      null,
    );

  const outerRef =
    useRef<THREE.Mesh>(
      null,
    );

  const innerRef =
    useRef<THREE.Mesh>(
      null,
    );

  const ringA =
    useRef<THREE.Mesh>(
      null,
    );

  const ringB =
    useRef<THREE.Mesh>(
      null,
    );

  const ringC =
    useRef<THREE.Mesh>(
      null,
    );

  useFrame(
    (
      state,
      delta,
    ) => {
      const time =
        state.clock.elapsedTime;

      if (
        groupRef.current
      ) {
        groupRef.current.rotation.y =
          Math.sin(
            time * 0.13,
          ) * 0.11;

        groupRef.current.rotation.x =
          Math.sin(
            time * 0.09,
          ) * 0.045;
      }

      if (
        outerRef.current
      ) {
        outerRef.current.rotation.x +=
          delta * 0.045;

        outerRef.current.rotation.y +=
          delta * 0.07;
      }

      if (
        innerRef.current
      ) {
        innerRef.current.rotation.x -=
          delta * 0.12;

        innerRef.current.rotation.y +=
          delta * 0.16;

        const pulse =
          1 +
          Math.sin(
            time * 1.3,
          ) *
            0.035;

        innerRef.current.scale.setScalar(
          pulse,
        );
      }

      if (ringA.current) {
        ringA.current.rotation.z +=
          delta * 0.09;
      }

      if (ringB.current) {
        ringB.current.rotation.y -=
          delta * 0.07;
      }

      if (ringC.current) {
        ringC.current.rotation.x +=
          delta * 0.05;
      }
    },
  );

  return (
    <group
      ref={groupRef}
      position={[
        4.2,
        0.15,
        -3.7,
      ]}
    >
      {/* atmospheric halo */}

      <mesh scale={3.8}>
        <sphereGeometry
          args={[
            1,
            36,
            36,
          ]}
        />

        <meshBasicMaterial
          color="#DDAE43"
          transparent
          opacity={0.012}
          side={
            THREE.BackSide
          }
          depthWrite={false}
        />
      </mesh>

      {/* large holographic shell */}

      <Float
        speed={0.7}
        rotationIntensity={
          0.08
        }
        floatIntensity={
          0.15
        }
      >
        <mesh
          ref={outerRef}
          scale={2.35}
        >
          <icosahedronGeometry
            args={[1, 3]}
          />

          <meshBasicMaterial
            color="#AFC4CE"
            wireframe
            transparent
            opacity={0.055}
            depthWrite={false}
          />
        </mesh>
      </Float>

      {/* gold intelligence geometry */}

      <mesh
        ref={innerRef}
        scale={1.45}
      >
        <icosahedronGeometry
          args={[1, 2]}
        />

        <meshBasicMaterial
          color="#E5B747"
          wireframe
          transparent
          opacity={0.15}
          depthWrite={false}
        />
      </mesh>

      {/* shield surface */}

      <mesh scale={2.7}>
        <sphereGeometry
          args={[
            1,
            24,
            18,
          ]}
        />

        <meshBasicMaterial
          color="#73B8D3"
          wireframe
          transparent
          opacity={0.018}
          depthWrite={false}
        />
      </mesh>

      {/* orbit A */}

      <mesh
        ref={ringA}
        rotation={[
          Math.PI / 2.3,
          0,
          Math.PI / 8,
        ]}
      >
        <torusGeometry
          args={[
            2.9,
            0.014,
            8,
            180,
          ]}
        />

        <meshBasicMaterial
          color="#E8BB50"
          transparent
          opacity={0.27}
          depthWrite={false}
          blending={
            THREE.AdditiveBlending
          }
        />
      </mesh>

      {/* orbit B */}

      <mesh
        ref={ringB}
        rotation={[
          Math.PI / 2.8,
          Math.PI / 2.4,
          0,
        ]}
      >
        <torusGeometry
          args={[
            3.35,
            0.01,
            8,
            180,
          ]}
        />

        <meshBasicMaterial
          color="#73B8D3"
          transparent
          opacity={0.16}
          depthWrite={false}
        />
      </mesh>

      {/* orbit C */}

      <mesh
        ref={ringC}
        rotation={[
          Math.PI / 3.1,
          Math.PI / 4,
          Math.PI / 3,
        ]}
      >
        <torusGeometry
          args={[
            3.7,
            0.007,
            8,
            180,
          ]}
        />

        <meshBasicMaterial
          color="#D5A541"
          transparent
          opacity={0.09}
          depthWrite={false}
        />
      </mesh>

      {/* protected intelligence core */}

      <mesh>
        <sphereGeometry
          args={[
            0.22,
            32,
            32,
          ]}
        />

        <meshBasicMaterial
          color="#FFF0A6"
          toneMapped={false}
        />
      </mesh>

      <mesh scale={2}>
        <sphereGeometry
          args={[
            0.22,
            24,
            24,
          ]}
        />

        <meshBasicMaterial
          color="#E2A93C"
          transparent
          opacity={0.12}
          depthWrite={false}
          toneMapped={false}
        />
      </mesh>

      <mesh scale={3.1}>
        <sphereGeometry
          args={[
            0.22,
            24,
            24,
          ]}
        />

        <meshBasicMaterial
          color="#E2A93C"
          transparent
          opacity={0.035}
          depthWrite={false}
        />
      </mesh>

      {/* orbiting intelligence nodes */}

      <OrbitNode
        radius={2.9}
        vertical={1.2}
        speed={0.32}
        phase={0}
        color="#F4CB67"
      />

      <OrbitNode
        radius={3.3}
        vertical={1.8}
        speed={0.21}
        phase={2}
        color="#7DC4DF"
      />

      <OrbitNode
        radius={2.5}
        vertical={2}
        speed={0.27}
        phase={4}
        color="#E7B548"
        size={0.07}
      />
    </group>
  );
}

/* =========================================================
   DATA NETWORK
   ========================================================= */

function DataNetwork() {
  return (
    <group>
      <DataArc
        start={[
          -6,
          2.5,
          -5,
        ]}
        middle={[
          -1,
          4,
          -7,
        ]}
        end={[
          4.2,
          0.2,
          -3.7,
        ]}
        color="#77BAD5"
        speed={0.065}
        delay={0}
      />

      <DataArc
        start={[
          -5.2,
          -2.2,
          -5,
        ]}
        middle={[
          -0.5,
          -3,
          -8,
        ]}
        end={[
          4.2,
          0.1,
          -3.7,
        ]}
        color="#DCAE42"
        speed={0.055}
        delay={0.33}
      />

      <DataArc
        start={[
          7,
          3.5,
          -8,
        ]}
        middle={[
          6,
          1.8,
          -6,
        ]}
        end={[
          4.2,
          0.1,
          -3.7,
        ]}
        color="#DCAE42"
        speed={0.075}
        delay={0.67}
      />
    </group>
  );
}

/* =========================================================
   DATA FLOOR
   ========================================================= */

function DataFloor() {
  const floorRef =
    useRef<THREE.Mesh>(
      null,
    );

  useFrame((state) => {
    if (
      !floorRef.current
    ) {
      return;
    }

    floorRef.current.position.z =
      -6 +
      Math.sin(
        state.clock
          .elapsedTime *
          0.12,
      ) *
        0.15;
  });

  return (
    <mesh
      ref={floorRef}
      position={[
        0,
        -3.8,
        -6,
      ]}
      rotation={[
        -Math.PI / 2.55,
        0,
        0,
      ]}
    >
      <planeGeometry
        args={[
          28,
          18,
          44,
          30,
        ]}
      />

      <meshBasicMaterial
        color="#527B8D"
        wireframe
        transparent
        opacity={0.027}
        depthWrite={false}
      />
    </mesh>
  );
}

/* =========================================================
   FLOATING TECH RINGS
   ========================================================= */

function FloatingTechRing({
  position,
  scale,
  color,
  speed,
  rotation,
}: {
  position:
    [
      number,
      number,
      number,
    ];

  scale: number;
  color: string;
  speed: number;

  rotation:
    [
      number,
      number,
      number,
    ];
}) {
  const ref =
    useRef<THREE.Mesh>(
      null,
    );

  useFrame(
    (
      state,
      delta,
    ) => {
      if (!ref.current) {
        return;
      }

      ref.current.rotation.x +=
        delta *
        speed *
        0.28;

      ref.current.rotation.y +=
        delta * speed;

      ref.current.position.y =
        position[1] +
        Math.sin(
          state.clock
            .elapsedTime *
            speed *
            0.7,
        ) *
          0.15;
    },
  );

  return (
    <mesh
      ref={ref}
      position={
        position
      }
      scale={scale}
      rotation={
        rotation
      }
    >
      <torusGeometry
        args={[
          1,
          0.009,
          6,
          120,
        ]}
      />

      <meshBasicMaterial
        color={color}
        transparent
        opacity={0.12}
        depthWrite={false}
        blending={
          THREE.AdditiveBlending
        }
      />
    </mesh>
  );
}

/* =========================================================
   CAMERA MOTION
   ========================================================= */

function CinematicCamera() {
  const { camera } =
    useThree();

  useFrame((state) => {
    const t =
      state.clock.elapsedTime;

    const targetX =
      state.pointer.x *
        0.32 +
      Math.sin(
        t * 0.08,
      ) *
        0.09;

    const targetY =
      state.pointer.y *
        0.18 +
      Math.sin(
        t * 0.11,
      ) *
        0.06;

    camera.position.x =
      THREE.MathUtils.lerp(
        camera.position.x,
        targetX,
        0.025,
      );

    camera.position.y =
      THREE.MathUtils.lerp(
        camera.position.y,
        targetY,
        0.025,
      );

    camera.lookAt(
      0,
      0,
      -4,
    );
  });

  return null;
}

/* =========================================================
   COMPLETE CINEMATIC SCENE
   ========================================================= */

function PremiumScene() {
  return (
    <>
      <fog
        attach="fog"
        args={[
          "#030507",
          10,
          30,
        ]}
      />

      <CinematicAurora />

      <CinematicCamera />

      <SecurityCore />

      <DataNetwork />

      <DataFloor />

      <ParticleField
        count={360}
        radius={11}
        color="#E5B64B"
        size={0.028}
        opacity={0.17}
        speed={0.006}
      />

      <ParticleField
        count={260}
        radius={10}
        color="#75BAD6"
        size={0.022}
        opacity={0.11}
        speed={-0.004}
      />

      <ParticleField
        count={100}
        radius={7}
        color="#FFFFFF"
        size={0.015}
        opacity={0.08}
        speed={0.002}
      />

      <FloatingTechRing
        position={[
          -5.8,
          2.4,
          -7,
        ]}
        scale={0.9}
        color="#79BCD6"
        speed={0.14}
        rotation={[
          0.7,
          0.2,
          0.3,
        ]}
      />

      <FloatingTechRing
        position={[
          -4.5,
          -1.7,
          -6,
        ]}
        scale={1.3}
        color="#DCAA42"
        speed={0.09}
        rotation={[
          0.3,
          0.6,
          0.2,
        ]}
      />

      <FloatingTechRing
        position={[
          7.2,
          -2.2,
          -8,
        ]}
        scale={1.05}
        color="#72B8D4"
        speed={0.11}
        rotation={[
          1,
          0.2,
          0.5,
        ]}
      />

      <FloatingTechRing
        position={[
          1.5,
          3.7,
          -10,
        ]}
        scale={1.5}
        color="#DCAA42"
        speed={0.05}
        rotation={[
          0.4,
          0.8,
          0.7,
        ]}
      />
    </>
  );
}

/* =========================================================
   MAIN
   ========================================================= */

export default function Live3DBackground() {
  return (
    <div className="landing-3d-background premium-live-bg">
      <Canvas
        camera={{
          position: [
            0,
            0,
            8,
          ],
          fov: 54,
          near: 0.1,
          far: 100,
        }}
        dpr={[1, 1.5]}
        gl={{
          antialias: true,
          alpha: true,
          powerPreference:
            "high-performance",
          toneMapping:
            THREE.ACESFilmicToneMapping,
        }}
      >
        <PremiumScene />
      </Canvas>

      <div className="landing-live-beam" />

      <div className="landing-3d-contrast" />

      <div className="landing-3d-vignette" />

      <div className="landing-live-scanlines" />

      <div className="landing-live-film" />
    </div>
  );
}