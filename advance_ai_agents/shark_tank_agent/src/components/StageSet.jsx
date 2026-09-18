import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { ContactShadows } from "@react-three/drei";
import { deskLayout, podiumLayout, stageColors } from "../constants.js";

function LedPanel({ position, index }) {
  const mesh = useRef();
  useFrame((state) => {
    if (!mesh.current) return;
    const pulse = 0.12 + Math.sin(state.clock.elapsedTime * 0.55 + index * 0.4) * 0.04;
    mesh.current.material.emissiveIntensity = pulse;
  });
  return (
    <mesh ref={mesh} position={position} castShadow>
      <boxGeometry args={[1.12, 3.1, 0.09]} />
      <meshStandardMaterial
        color={0x172033}
        roughness={0.52}
        metalness={0.2}
        emissive={0x14335c}
        emissiveIntensity={0.14}
      />
    </mesh>
  );
}

export function StageSet() {
  const seatKeys = ["nemotron", "judge", "deepseek"];

  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, -1.2]} receiveShadow>
        <planeGeometry args={[18, 16]} />
        <meshStandardMaterial
          color={0x10131a}
          roughness={0.34}
          metalness={0.22}
          emissive={0x070b12}
          emissiveIntensity={0.18}
        />
      </mesh>

      <mesh position={[0, 2.1, -5.2]} receiveShadow>
        <boxGeometry args={[14, 4.2, 0.18]} />
        <meshStandardMaterial
          color={0x10141d}
          roughness={0.68}
          metalness={0.14}
          emissive={0x080f1d}
          emissiveIntensity={0.24}
        />
      </mesh>

      {[-3, -2, -1, 0, 1, 2, 3].map((index) => (
        <LedPanel key={index} index={index} position={[index * 1.75, 2.05, -5.06]} />
      ))}

      <mesh position={[0, 0.04, -1.05]} receiveShadow>
        <boxGeometry args={[3.2, 0.03, 5.4]} />
        <meshStandardMaterial
          color={0x141b26}
          roughness={0.32}
          metalness={0.28}
          emissive={0x101820}
          emissiveIntensity={0.1}
        />
      </mesh>

      {seatKeys.map((key) => (
        <mesh key={key} position={podiumLayout[key]} receiveShadow>
          <cylinderGeometry args={[0.42, 0.5, 0.08, 32]} />
          <meshStandardMaterial color={0x111820} roughness={0.4} metalness={0.28} />
        </mesh>
      ))}

      <group position={deskLayout.position}>
        <mesh position={[0, 0.46, 0]} castShadow receiveShadow>
          <boxGeometry args={[5.85, 0.78, 0.78]} />
          <meshStandardMaterial color={0x121820} roughness={0.44} metalness={0.22} />
        </mesh>
        <mesh position={[0, 0.86, 0.02]} castShadow receiveShadow>
          <boxGeometry args={[6.05, 0.05, 0.86]} />
          <meshStandardMaterial color={0x0f151f} roughness={0.28} metalness={0.38} />
        </mesh>
        <mesh position={[0, 0.9, 0.38]}>
          <boxGeometry args={[5.95, 0.03, 0.06]} />
          <meshStandardMaterial
            color={0xffffff}
            transparent
            opacity={0.42}
            emissive={0xbfd8ff}
            emissiveIntensity={0.14}
            roughness={0.22}
            metalness={0.12}
          />
        </mesh>
      </group>

      <mesh position={[-8.4, 1.8, -1.2]}>
        <boxGeometry args={[4.2, 3.6, 8]} />
        <meshStandardMaterial color={stageColors.room} roughness={1} metalness={0} />
      </mesh>
      <mesh position={[8.4, 1.8, -1.2]}>
        <boxGeometry args={[4.2, 3.6, 8]} />
        <meshStandardMaterial color={stageColors.room} roughness={1} metalness={0} />
      </mesh>

      <ContactShadows position={[0, 0.01, -1.2]} opacity={0.38} scale={16} blur={2.6} far={8} />
    </group>
  );
}
