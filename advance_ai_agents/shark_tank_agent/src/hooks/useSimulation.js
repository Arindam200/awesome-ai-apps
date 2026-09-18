import { useMemo, useState } from "react";
import { starterPrompt } from "../constants.js";

export function useSimulation() {
  const [prompt, setPrompt] = useState(starterPrompt);
  const [answer, setAnswer] = useState("");
  const [counterOffer, setCounterOffer] = useState("");
  const [counterLoading, setCounterLoading] = useState(false);
  const [stage, setStage] = useState("early");
  const [objective, setObjective] = useState("growth");
  const [length, setLength] = useState("full");
  const [simulation, setSimulation] = useState(null);
  const [prepBrief, setPrepBrief] = useState(null);
  const [prepOpen, setPrepOpen] = useState(false);
  const [prepLoading, setPrepLoading] = useState(false);
  const [activeRound, setActiveRound] = useState(0);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reportsOpen, setReportsOpen] = useState(false);
  const [reports, setReports] = useState([]);
  const [reportsSummary, setReportsSummary] = useState(null);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [reportsError, setReportsError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [error, setError] = useState("");
  const [streamBeat, setStreamBeat] = useState("idle");
  const [dockCollapsed, setDockCollapsed] = useState(false);

  const round = simulation?.rounds?.[activeRound] || null;
  const roundCount = simulation?.rounds?.length || 10;
  const canGoBack = activeRound > 0;
  const canGoNext = activeRound < roundCount - 1 && activeRound < (simulation?.currentRoundIndex ?? roundCount - 1);

  const stageTitle = useMemo(() => {
    if (isLoading) return "Preparing shark room";
    if (simulation) return simulation.businessTitle;
    return "AI Shark Tank";
  }, [isLoading, simulation]);

  async function runSimulation(event) {
    event.preventDefault();
    if (isLoading || prepLoading || counterLoading) return;
    const text = prompt.trim();
    if (!text) {
      setError("Describe the business first.");
      return;
    }

    setError("");
    setIsLoading(true);
    setPrepOpen(false);
    setReviewOpen(false);
    setDockCollapsed(false);
    setStreamBeat("loading");
    setStatusText("Sending your pitch to the sharks...");
    setSimulation(null);
    setAnswer("");
    setCounterOffer("");

    try {
      const response = await fetch("/api/room/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: text, stage, objective, length }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload?.error || "Could not start the shark room.");
      }
      setSimulation(payload.data);
      setActiveRound(payload.data.currentRoundIndex || 0);
      setStreamBeat("brief");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not start the shark room.");
      setStreamBeat("idle");
      setDockCollapsed(false);
    } finally {
      setIsLoading(false);
      setStatusText("");
    }
  }

  async function submitAnswer(event) {
    event.preventDefault();
    if (isLoading || prepLoading || counterLoading) return;
    const text = answer.trim();
    if (!simulation?.id) {
      setError("Start a room first.");
      return;
    }
    if (!text) {
      setError("Answer the sharks before advancing.");
      return;
    }

    setError("");
    setIsLoading(true);
    setStreamBeat("judge");
    setStatusText(`Sharks are scoring round ${activeRound + 1}...`);

    try {
      const response = await fetch(`/api/room/${simulation.id}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer: text }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || "Could not score your answer.");
      }
      setSimulation(payload.data);
      setActiveRound(payload.data.currentRoundIndex || 0);
      setAnswer("");
      setStreamBeat(payload.data.status === "complete" ? "final" : "brief");
      if (payload.data.status === "complete") {
        setReviewOpen(true);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not score your answer.");
      setStreamBeat("idle");
    } finally {
      setIsLoading(false);
      setStatusText("");
    }
  }

  async function submitCounterOffer(event) {
    event.preventDefault();
    if (isLoading || prepLoading || counterLoading) return;
    const text = counterOffer.trim();
    if (!simulation?.id || simulation.status !== "complete") {
      setError("Finish the room before countering.");
      return;
    }
    if (!text) {
      setError("Write your counter-offer first.");
      return;
    }

    setError("");
    setCounterLoading(true);
    setStatusText("Sharks are reviewing your counter-offer...");
    try {
      const response = await fetch(`/api/room/${simulation.id}/counter`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ counter: text }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || "Counter-offer failed.");
      }
      setSimulation(payload.data);
      setCounterOffer("");
      setReviewOpen(true);
      setStreamBeat("final");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Counter-offer failed.");
    } finally {
      setCounterLoading(false);
      setStatusText("");
    }
  }

  async function runPrep() {
    if (isLoading || prepLoading || counterLoading) return;
    const text = prompt.trim();
    if (!text) {
      setError("Describe the business first.");
      return;
    }

    setError("");
    setPrepLoading(true);
    setStreamBeat("brief");
    setStatusText("The lead shark is preparing a founder brief...");

    try {
      const response = await fetch("/api/prep", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: text, stage, objective, length }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || "Founder prep failed.");
      }
      setPrepBrief(payload.data);
      setPrepOpen(true);
      setStreamBeat("idle");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Founder prep failed.");
      setStreamBeat("idle");
    } finally {
      setPrepLoading(false);
      setStatusText("");
    }
  }

  function resetRoom() {
    setSimulation(null);
    setPrepBrief(null);
    setPrepOpen(false);
    setActiveRound(0);
    setReviewOpen(false);
    setError("");
    setStatusText("");
    setStreamBeat("idle");
    setDockCollapsed(false);
    setAnswer("");
    setCounterOffer("");
  }

  async function openReports() {
    setReportsOpen(true);
    setReportsLoading(true);
    setReportsError("");

    try {
      const response = await fetch("/api/reports");
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || "Could not load saved reports.");
      }
      setReports(payload.data || []);
      setReportsSummary(payload.summary || null);
    } catch (caught) {
      setReportsError(caught instanceof Error ? caught.message : "Could not load saved reports.");
    } finally {
      setReportsLoading(false);
    }
  }

  async function loadReport(reportId) {
    setReportsError("");
    try {
      const response = await fetch(`/api/reports/${reportId}`);
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || "Could not load report.");
      }
      const data = { ...payload.data, cached: true };
      setSimulation(data);
      setPrompt(data.prompt || prompt);
      setStage(data.practiceContext?.stage || "early");
      setObjective(data.practiceContext?.objective || "growth");
      setLength(data.practiceContext?.length || "full");
      setActiveRound(0);
      setReportsOpen(false);
      setReviewOpen(true);
      setStreamBeat("final");
      setDockCollapsed(true);
    } catch (caught) {
      setReportsError(caught instanceof Error ? caught.message : "Could not load report.");
    }
  }

  function practiceAgain(source) {
    const nextPrompt = [
      source.rewrittenPitch && `Updated investor pitch:\n${source.rewrittenPitch}`,
      source.recommendedAskFraming && `Ask framing to test:\n${source.recommendedAskFraming}`,
      source.prompt && `Original business facts:\n${source.prompt}`,
    ]
      .filter(Boolean)
      .join("\n\n")
      .slice(0, 5000);

    setPrompt(nextPrompt || source.prompt || starterPrompt);
    setStage(source.practiceContext?.stage || stage);
    setObjective(source.practiceContext?.objective || objective);
    setLength(source.practiceContext?.length || length);
    setSimulation(null);
    setPrepOpen(false);
    setActiveRound(0);
    setReviewOpen(false);
    setReportsOpen(false);
    setError("");
    setStatusText("");
    setStreamBeat("idle");
    setDockCollapsed(false);
    setAnswer("");
    setCounterOffer("");
  }

  function usePrepPitch(source) {
    const nextPrompt = [
      source.rewrittenPitch && `Founder pitch to test:\n${source.rewrittenPitch}`,
      source.askFraming && `Ask framing:\n${source.askFraming}`,
      source.promptSummary && `Business summary:\n${source.promptSummary}`,
      prompt && `Original facts:\n${prompt}`,
    ]
      .filter(Boolean)
      .join("\n\n")
      .slice(0, 5000);

    setPrompt(nextPrompt || prompt);
    setPrepOpen(false);
  }

  function useRecommendedSetup(setup) {
    setStage(setup.stage || "early");
    setObjective(setup.objective || "growth");
    setLength(setup.length || "quick");
    setReportsOpen(false);
    setError("");
    setStatusText("Recommended room loaded.");
  }

  function useTrainingPlan(setup) {
    setStage(setup.stage || "early");
    setObjective(setup.objective || "growth");
    setLength(setup.length || "quick");
    if (setup.prompt) {
      setPrompt(setup.prompt);
    }
    setSimulation(null);
    setActiveRound(0);
    setReviewOpen(false);
    setReportsOpen(false);
    setError("");
    setStatusText("Training plan loaded.");
    setStreamBeat("idle");
    setDockCollapsed(false);
  }

  return {
    prompt,
    setPrompt,
    answer,
    setAnswer,
    counterOffer,
    setCounterOffer,
    counterLoading,
    stage,
    setStage,
    objective,
    setObjective,
    length,
    setLength,
    simulation,
    prepBrief,
    prepOpen,
    setPrepOpen,
    prepLoading,
    activeRound,
    setActiveRound,
    reviewOpen,
    setReviewOpen,
    reportsOpen,
    setReportsOpen,
    reports,
    reportsSummary,
    reportsLoading,
    reportsError,
    isLoading,
    statusText,
    error,
    streamBeat,
    dockCollapsed,
    setDockCollapsed,
    round,
    roundCount,
    canGoBack,
    canGoNext,
    stageTitle,
    runSimulation,
    submitAnswer,
    submitCounterOffer,
    runPrep,
    resetRoom,
    openReports,
    loadReport,
    practiceAgain,
    usePrepPitch,
    useRecommendedSetup,
    useTrainingPlan,
  };
}
