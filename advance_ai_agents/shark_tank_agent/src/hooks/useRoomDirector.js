import { useEffect, useMemo, useRef, useState } from "react";

const SHARK_BEAT_MS = 3600;
const sharkBeatOrder = ["nemotron", "judge", "deepseek"];

function directorSpeaker({ simulation, isLoading, prepLoading, streamBeat, founderBeat, round }) {
  if (prepLoading) return { speaker: "judge", cameraShot: "judge", lightCue: "judge" };
  if (!simulation && !isLoading) return { speaker: "judge", cameraShot: "wide", lightCue: "judge" };
  if (streamBeat === "loading" || streamBeat === "brief") {
    return { speaker: "judge", cameraShot: "judge", lightCue: "judge" };
  }
  if (streamBeat === "founder" || (isLoading && round?.sharkReactions && !round?.userAnswer)) {
    return { speaker: founderBeat, cameraShot: founderBeat, lightCue: founderBeat };
  }
  if (streamBeat === "final" && simulation?.finalDeal) {
    return { speaker: "judge", cameraShot: "push", lightCue: "judge" };
  }
  if (round?.interest) {
    const top = Object.entries(round.interest).sort((a, b) => Number(b[1]) - Number(a[1]))[0]?.[0];
    if (top) return { speaker: top, cameraShot: top, lightCue: top };
  }
  if (round?.winner) {
    if (round.winner === "tie") return { speaker: "judge", cameraShot: "tie", lightCue: "tie" };
    return { speaker: round.winner, cameraShot: round.winner, lightCue: round.winner };
  }
  if (round?.panelQuestion || round?.question) return { speaker: "judge", cameraShot: "judge", lightCue: "judge" };
  if (isLoading) return { speaker: "judge", cameraShot: "judge", lightCue: "judge" };
  return { speaker: "judge", cameraShot: "wide", lightCue: "judge" };
}

export function useRoomDirector({
  simulation,
  isLoading,
  prepLoading,
  activeRound,
  streamBeat,
}) {
  const [overrideSeat, setOverrideSeat] = useState(null);
  const [hoveredSeat, setHoveredSeat] = useState(null);
  const [founderBeat, setFounderBeat] = useState("nemotron");
  const prevBeat = useRef(streamBeat);
  const round = simulation?.rounds?.[activeRound] || null;

  useEffect(() => {
    if (prevBeat.current === streamBeat) return;
    prevBeat.current = streamBeat;
    setOverrideSeat(null);
    if (streamBeat === "founder") {
      setFounderBeat("nemotron");
    }
  }, [streamBeat]);

  useEffect(() => {
    if (streamBeat !== "founder" || overrideSeat) return undefined;
    const timer = window.setTimeout(() => {
      setFounderBeat((seat) => sharkBeatOrder[(sharkBeatOrder.indexOf(seat) + 1) % sharkBeatOrder.length]);
    }, SHARK_BEAT_MS);
    return () => window.clearTimeout(timer);
  }, [streamBeat, founderBeat, overrideSeat, activeRound]);

  const directed = useMemo(
    () => directorSpeaker({ simulation, isLoading, prepLoading, streamBeat, founderBeat, round }),
    [simulation, isLoading, prepLoading, streamBeat, founderBeat, round],
  );

  const speaker = overrideSeat || directed.speaker;
  const cameraShot = overrideSeat || directed.cameraShot;
  const focusSeat = speaker;
  const lightCue = hoveredSeat || (overrideSeat ? overrideSeat : directed.lightCue);

  function focusStageSeat(seat) {
    setOverrideSeat(seat);
  }

  function hoverStageSeat(seat) {
    setHoveredSeat(seat);
  }

  function clearHoverSeat() {
    setHoveredSeat(null);
  }

  return {
    speaker,
    cameraShot,
    lightCue,
    focusSeat,
    hoveredSeat,
    overrideSeat,
    focusStageSeat,
    hoverStageSeat,
    clearHoverSeat,
  };
}
