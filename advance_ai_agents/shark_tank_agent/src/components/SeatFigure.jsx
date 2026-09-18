import { useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import { DoubleSide } from "three";
import { seatLabel } from "../utils.js";

const SKIN = 0xf3c27a;

function LegoHand({ position, rotation }) {
  return (
    <group position={position} rotation={rotation}>
      <mesh castShadow>
        <cylinderGeometry args={[0.055, 0.055, 0.08, 10]} />
        <meshStandardMaterial color={SKIN} roughness={0.45} />
      </mesh>
      <mesh position={[0, 0, 0.07]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.055, 0.022, 8, 14, Math.PI * 1.2]} />
        <meshStandardMaterial color={SKIN} roughness={0.45} />
      </mesh>
    </group>
  );
}

function LegoChair({ accent, focused }) {
  return (
    <group position={[0, 0, -0.03]}>
      <mesh position={[0, 0.42, -0.17]} castShadow receiveShadow>
        <boxGeometry args={[0.86, 0.22, 0.72]} />
        <meshStandardMaterial color={0x0c1119} roughness={0.44} metalness={0.28} />
      </mesh>
      <mesh position={[0, 1.02, -0.42]} rotation={[-0.1, 0, 0]} castShadow receiveShadow>
        <boxGeometry args={[0.98, 1.18, 0.2]} />
        <meshStandardMaterial color={0x111925} roughness={0.38} metalness={0.24} />
      </mesh>
      <mesh position={[-0.57, 0.72, -0.06]} rotation={[0, 0, -0.14]} castShadow receiveShadow>
        <boxGeometry args={[0.16, 0.64, 0.22]} />
        <meshStandardMaterial color={0x101721} roughness={0.38} metalness={0.25} />
      </mesh>
      <mesh position={[0.57, 0.72, -0.06]} rotation={[0, 0, 0.14]} castShadow receiveShadow>
        <boxGeometry args={[0.16, 0.64, 0.22]} />
        <meshStandardMaterial color={0x101721} roughness={0.38} metalness={0.25} />
      </mesh>
      <mesh position={[0, 0.05, -0.02]} castShadow receiveShadow>
        <cylinderGeometry args={[0.56, 0.68, 0.1, 42]} />
        <meshStandardMaterial color={0x0b1018} roughness={0.36} metalness={0.36} />
      </mesh>
      <mesh position={[0, 0.74, -0.31]}>
        <boxGeometry args={[0.66, 0.055, 0.04]} />
        <meshStandardMaterial
          color={0xffffff}
          transparent
          opacity={focused ? 0.9 : 0.48}
          emissive={accent}
          emissiveIntensity={focused ? 0.52 : 0.2}
        />
      </mesh>
    </group>
  );
}

function LegoMinifig({ accent, coat, pants, seated, focused }) {
  const torso = useRef();
  const head = useRef();

  useFrame((state) => {
    const time = state.clock.elapsedTime;
    if (head.current) {
      head.current.rotation.y = Math.sin(time * 0.85) * 0.14;
    }
    if (torso.current) {
      torso.current.rotation.x += ((focused ? -0.1 : 0) - torso.current.rotation.x) * 0.08;
    }
  });

  const pantsColor = pants || coat;

  return (
    <group>
      {seated ? (
        <>
          <mesh position={[-0.13, 0.22, 0.02]} castShadow>
            <boxGeometry args={[0.2, 0.36, 0.2]} />
            <meshStandardMaterial color={pantsColor} roughness={0.55} metalness={0.08} />
          </mesh>
          <mesh position={[0.13, 0.22, 0.02]} castShadow>
            <boxGeometry args={[0.2, 0.36, 0.2]} />
            <meshStandardMaterial color={pantsColor} roughness={0.55} metalness={0.08} />
          </mesh>
          <mesh position={[-0.13, 0.38, 0.23]} rotation={[-Math.PI / 2.2, 0, 0]} castShadow>
            <boxGeometry args={[0.2, 0.38, 0.2]} />
            <meshStandardMaterial color={pantsColor} roughness={0.55} metalness={0.08} />
          </mesh>
          <mesh position={[0.13, 0.38, 0.23]} rotation={[-Math.PI / 2.2, 0, 0]} castShadow>
            <boxGeometry args={[0.2, 0.38, 0.2]} />
            <meshStandardMaterial color={pantsColor} roughness={0.55} metalness={0.08} />
          </mesh>
        </>
      ) : (
        <>
          <mesh position={[-0.13, 0.24, 0]} castShadow>
            <boxGeometry args={[0.22, 0.46, 0.22]} />
            <meshStandardMaterial color={pantsColor} roughness={0.55} metalness={0.08} />
          </mesh>
          <mesh position={[0.13, 0.24, 0]} castShadow>
            <boxGeometry args={[0.22, 0.46, 0.22]} />
            <meshStandardMaterial color={pantsColor} roughness={0.55} metalness={0.08} />
          </mesh>
        </>
      )}

      <mesh position={[0, seated ? 0.52 : 0.5, seated ? -0.02 : 0]} castShadow>
        <boxGeometry args={[0.48, 0.16, 0.28]} />
        <meshStandardMaterial color={pantsColor} roughness={0.5} metalness={0.1} />
      </mesh>

      <group ref={torso} position={[0, seated ? 0.86 : 0.86, seated ? -0.02 : 0]}>
        <mesh castShadow>
          <boxGeometry args={[0.56, 0.58, 0.3]} />
          <meshStandardMaterial color={coat} roughness={0.42} metalness={0.12} />
        </mesh>
        <mesh position={[0, 0.04, 0.16]} castShadow>
          <boxGeometry args={[0.34, 0.28, 0.04]} />
          <meshStandardMaterial color={accent} emissive={accent} emissiveIntensity={0.28} roughness={0.3} />
        </mesh>
        <mesh position={[-0.34, 0.08, 0]} rotation={[0.12, 0, 0.12]} castShadow>
          <boxGeometry args={[0.16, 0.5, 0.16]} />
          <meshStandardMaterial color={coat} roughness={0.42} metalness={0.12} />
        </mesh>
        <mesh position={[0.34, 0.08, 0]} rotation={[0.12, 0, -0.12]} castShadow>
          <boxGeometry args={[0.16, 0.5, 0.16]} />
          <meshStandardMaterial color={coat} roughness={0.42} metalness={0.12} />
        </mesh>
        <LegoHand position={[-0.34, -0.22, 0.08]} rotation={[0.4, 0, 0.2]} />
        <LegoHand position={[0.34, -0.22, 0.08]} rotation={[0.4, 0, -0.2]} />
      </group>

      <group ref={head} position={[0, seated ? 1.32 : 1.32, seated ? -0.02 : 0]}>
        <mesh castShadow>
          <cylinderGeometry args={[0.2, 0.2, 0.34, 20]} />
          <meshStandardMaterial color={SKIN} roughness={0.48} />
        </mesh>
        <mesh position={[0, 0.2, 0]} castShadow>
          <cylinderGeometry args={[0.08, 0.08, 0.08, 16]} />
          <meshStandardMaterial color={SKIN} roughness={0.48} />
        </mesh>
        <mesh position={[-0.07, 0.04, 0.17]}>
          <sphereGeometry args={[0.035, 10, 8]} />
          <meshStandardMaterial color={0x1a1a1a} />
        </mesh>
        <mesh position={[0.07, 0.04, 0.17]}>
          <sphereGeometry args={[0.035, 10, 8]} />
          <meshStandardMaterial color={0x1a1a1a} />
        </mesh>
      </group>
    </group>
  );
}

export function SeatFigure({
  seat,
  accent,
  coat,
  pants,
  position,
  rotation = 0,
  scale = 1,
  seated = false,
  focused,
  hovered,
  winning,
  portal,
  onFocus,
  onHover,
  onHoverEnd,
}) {
  const group = useRef();
  const ring = useRef();
  const beam = useRef();
  const [localHover, setLocalHover] = useState(false);
  const lit = focused || hovered || localHover || winning;

  useFrame((state) => {
    const time = state.clock.elapsedTime;
    if (group.current) {
      group.current.rotation.y = rotation;
    }
    if (ring.current) {
      ring.current.material.opacity = (lit ? 0.88 : 0.22) * (0.9 + Math.sin(time * 1.4) * 0.08);
      ring.current.material.emissiveIntensity = lit ? 0.7 : 0.16;
    }
    if (beam.current) {
      beam.current.material.opacity = lit ? 0.16 : 0.03;
    }
  });

  function handleHover(event) {
    event.stopPropagation();
    document.body.style.cursor = "pointer";
    setLocalHover(true);
    onHover?.(seat);
  }

  function handleHoverEnd(event) {
    event.stopPropagation();
    document.body.style.cursor = "auto";
    setLocalHover(false);
    onHoverEnd?.();
  }

  return (
    <group position={position} scale={scale}>
      <LegoChair accent={accent} focused={lit} />
      <group
        ref={group}
        onClick={(event) => {
          event.stopPropagation();
          onFocus(seat);
        }}
        onPointerOver={handleHover}
        onPointerOut={handleHoverEnd}
      >
        <LegoMinifig accent={accent} coat={coat} pants={pants} seated={seated} focused={focused} />
        <mesh position={[0, 0.85, 0]} visible={false}>
          <cylinderGeometry args={[0.55, 0.55, 1.9, 12]} />
          <meshBasicMaterial transparent opacity={0} />
        </mesh>
      </group>

      <mesh ref={ring} position={[0, 0.04, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.48, 0.58, 48]} />
        <meshStandardMaterial
          color={accent}
          transparent
          opacity={0.28}
          emissive={accent}
          emissiveIntensity={0.2}
          roughness={0.32}
          side={DoubleSide}
        />
      </mesh>
      <mesh ref={beam} position={[0, 1.7, -0.08]}>
        <cylinderGeometry args={[0.42, 0.2, 2.8, 24, 1, true]} />
        <meshStandardMaterial
          color={accent}
          transparent
          opacity={0.06}
          emissive={accent}
          emissiveIntensity={0.14}
          side={DoubleSide}
        />
      </mesh>

      <Html position={[0, seated ? 0.86 : 1.16, 0.72]} center zIndexRange={[20, 0]} portal={portal} occlude={false}>
        <button
          className={`seat-hotspot table-plate ${seat} ${focused ? "active" : ""} ${hovered || localHover ? "hovered" : ""}`}
          onMouseEnter={() => onHover?.(seat)}
          onMouseLeave={() => onHoverEnd?.()}
          onClick={() => onFocus(seat)}
          type="button"
        >
          <span>{seatLabel(seat)}</span>
        </button>
      </Html>
    </group>
  );
}
