import { useEffect, useLayoutEffect, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { EffectComposer, Bloom, Vignette, Noise } from "@react-three/postprocessing";
import * as THREE from "three";
import { cameraShots, seatLayout, stageColors } from "../constants.js";
import { StageSet } from "./StageSet.jsx";
import { SeatFigure } from "./SeatFigure.jsx";
import { FounderSpeechCard } from "./SpeechCard.jsx";
import { seatLabel } from "../utils.js";

function AimedSpot({ color, position, target, intensity, angle, penumbra, distance, decay }) {
  const lightRef = useRef();
  const targetRef = useRef();

  useLayoutEffect(() => {
    if (lightRef.current && targetRef.current) {
      lightRef.current.target = targetRef.current;
    }
  }, []);

  return (
    <>
      <spotLight
        ref={lightRef}
        color={color}
        position={position}
        intensity={intensity}
        angle={angle}
        penumbra={penumbra}
        distance={distance}
        decay={decay}
      />
      <object3D ref={targetRef} position={[target[0], target[1] + 1.2, target[2]]} />
    </>
  );
}

function FrameCounter() {
  useFrame(() => {
    if (typeof window !== "undefined") {
      window.__aiSharkTank3dFrames = (window.__aiSharkTank3dFrames || 0) + 1;
    }
  });
  return null;
}

function CameraRig({ shot }) {
  const { camera, size } = useThree();

  useEffect(() => {
    const mobile = size.width < 760;
    camera.fov = mobile ? 52 : 38;
    camera.updateProjectionMatrix();
  }, [camera, size.width]);

  useFrame(() => {
    const target = cameraShots[shot] || cameraShots.wide;
    const mobile = size.width < 760;
    const goalZ = mobile ? target.z + 4 : target.z;
    const goalY = mobile ? target.y + 0.45 : target.y;
    camera.position.x += (target.x - camera.position.x) * 0.055;
    camera.position.y += (goalY - camera.position.y) * 0.055;
    camera.position.z += (goalZ - camera.position.z) * 0.055;
    camera.lookAt(target.lookX, target.lookY, target.lookZ);
  });

  return null;
}

function StageLights({ lightCue, hoveredSeat }) {
  const cue = hoveredSeat || lightCue;
  const speaking = cue === "nemotron" || cue === "deepseek" || cue === "judge" || cue === "tie";
  const target =
    cue === "nemotron"
      ? seatLayout.nemotron.position
      : cue === "deepseek"
        ? seatLayout.deepseek.position
        : seatLayout.judge.position;
  const color = cue === "nemotron" ? stageColors.left : cue === "deepseek" ? stageColors.right : 0xf4efe4;

  return (
    <>
      <hemisphereLight args={[0x8eb0d8, 0x090a0d, 1.12]} />
      <directionalLight position={[0, 5.8, 3.4]} intensity={1.35} castShadow />
      <directionalLight position={[0, 2.2, -5.2]} intensity={0.38} color={0x7aa0c8} />
      <AimedSpot
        color={color}
        position={[target[0] * 0.35, 5.4, 2.2]}
        target={target}
        intensity={speaking ? 38 : 20}
        angle={Math.PI / 5.2}
        penumbra={0.58}
        distance={14}
        decay={1.25}
      />
    </>
  );
}

function RoomScene({
  cameraShot,
  lightCue,
  focusSeat,
  hoveredSeat,
  round,
  roundCount,
  activeRound,
  isLoading,
  statusText,
  simulation,
  canGoBack,
  canGoNext,
  onPrev,
  onNext,
  onSelectRound,
  onFocusSeat,
  onHoverSeat,
  onHoverEnd,
  htmlLayer,
  hasSimulation,
}) {
  const showFounders = Boolean(hasSimulation || isLoading);
  const topInterest = round?.interest
    ? Object.entries(round.interest).sort((a, b) => Number(b[1]) - Number(a[1]))[0]?.[0]
    : null;

  return (
    <>
      <color attach="background" args={[stageColors.room]} />
      <fog attach="fog" args={[stageColors.room, 14, 32]} />
      <CameraRig shot={cameraShot} />
      <StageLights lightCue={lightCue} hoveredSeat={hoveredSeat} />
      <StageSet />
      <SeatFigure
        seat="nemotron"
        accent={stageColors.left}
        coat={0x3a6ea8}
        pants={0x24344a}
        position={seatLayout.nemotron.position}
        rotation={seatLayout.nemotron.rotation}
        scale={seatLayout.nemotron.scale}
        seated={seatLayout.nemotron.seated}
        focused={focusSeat === "nemotron"}
        hovered={hoveredSeat === "nemotron"}
        winning={topInterest === "nemotron"}
        portal={htmlLayer}
        onFocus={onFocusSeat}
        onHover={onHoverSeat}
        onHoverEnd={onHoverEnd}
      />
      <SeatFigure
        seat="deepseek"
        accent={stageColors.right}
        coat={0xd8dce3}
        pants={0x2a2e36}
        position={seatLayout.deepseek.position}
        rotation={seatLayout.deepseek.rotation}
        scale={seatLayout.deepseek.scale}
        seated={seatLayout.deepseek.seated}
        focused={focusSeat === "deepseek"}
        hovered={hoveredSeat === "deepseek"}
        winning={topInterest === "deepseek"}
        portal={htmlLayer}
        onFocus={onFocusSeat}
        onHover={onHoverSeat}
        onHoverEnd={onHoverEnd}
      />
      <SeatFigure
        seat="judge"
        accent={stageColors.judge}
        coat={0x2c3948}
        pants={0x1a222c}
        position={seatLayout.judge.position}
        rotation={seatLayout.judge.rotation}
        scale={seatLayout.judge.scale}
        seated={seatLayout.judge.seated}
        focused={focusSeat === "judge"}
        hovered={hoveredSeat === "judge"}
        winning={topInterest === "judge"}
        portal={htmlLayer}
        onFocus={onFocusSeat}
        onHover={onHoverSeat}
        onHoverEnd={onHoverEnd}
      />
      {showFounders ? (
        <FounderSpeechCard
          side="nemotron"
          title={seatLabel("nemotron")}
          model={simulation?.sharks?.nemotron?.model || "MiniMaxAI/MiniMax-M3"}
          position={simulation?.sharks?.nemotron?.thesis || "Execution-heavy operator investor."}
          round={round}
          activeWinner={topInterest}
          focusSeat={focusSeat}
          onFocusSeat={onFocusSeat}
          onHoverSeat={onHoverSeat}
          onHoverEnd={onHoverEnd}
          portal={htmlLayer}
          htmlPosition={[-2.55, 2.42, -2.35]}
        />
      ) : null}
      {showFounders ? (
        <FounderSpeechCard
          side="deepseek"
          title={seatLabel("deepseek")}
          model={simulation?.sharks?.deepseek?.model || "deepseek-ai/DeepSeek-V4-Flash"}
          position={simulation?.sharks?.deepseek?.thesis || "Growth-heavy category investor."}
          round={round}
          activeWinner={topInterest}
          focusSeat={focusSeat}
          onFocusSeat={onFocusSeat}
          onHoverSeat={onHoverSeat}
          onHoverEnd={onHoverEnd}
          portal={htmlLayer}
          htmlPosition={[2.55, 2.42, -2.35]}
        />
      ) : null}
      <FrameCounter />
      <EffectComposer disableNormalPass>
        <Bloom intensity={0.42} luminanceThreshold={0.72} luminanceSmoothing={0.28} mipmapBlur />
        <Vignette eskil={false} offset={0.18} darkness={0.72} />
        <Noise opacity={0.035} />
      </EffectComposer>
    </>
  );
}

export function PitchRoom(props) {
  return (
    <div className="digital-stage" aria-hidden="true">
      <Canvas
        className="digital-stage-root"
        shadows
        dpr={[1, 1.75]}
        gl={{
          antialias: true,
          alpha: true,
          preserveDrawingBuffer: true,
          toneMapping: THREE.ACESFilmicToneMapping,
          outputColorSpace: THREE.SRGBColorSpace,
        }}
        camera={{ fov: 38, position: [0, 1.22, 5.55], near: 0.1, far: 100 }}
        onCreated={({ gl }) => {
          gl.domElement.classList.add("digital-stage-canvas");
        }}
      >
        <RoomScene {...props} />
      </Canvas>
    </div>
  );
}
