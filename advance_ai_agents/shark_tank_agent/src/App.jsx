import { useState } from "react";
import { PitchRoom } from "./components/PitchRoom.jsx";
import { RoomHud } from "./components/RoomHud.jsx";
import { PromptDock } from "./components/PromptDock.jsx";
import { ReportModal } from "./components/ReportModal.jsx";
import { PrepModal } from "./components/PrepModal.jsx";
import { ReportsLibrary } from "./components/ReportsLibrary.jsx";
import { JudgeSpeechCard } from "./components/SpeechCard.jsx";
import { useSimulation } from "./hooks/useSimulation.js";
import { useRoomDirector } from "./hooks/useRoomDirector.js";

export default function App() {
  const sim = useSimulation();
  const director = useRoomDirector({
    simulation: sim.simulation,
    isLoading: sim.isLoading,
    prepLoading: sim.prepLoading,
    activeRound: sim.activeRound,
    streamBeat: sim.streamBeat,
  });
  const [htmlNode, setHtmlNode] = useState(null);
  const htmlLayer = htmlNode ? { current: htmlNode } : undefined;

  return (
    <main
      className={`duel-room focus-${director.focusSeat} ${sim.simulation ? "has-simulation" : ""} ${sim.dockCollapsed ? "dock-collapsed" : ""}`}
    >
      <div className="stage-html-layer" ref={setHtmlNode} />
      {htmlNode ? (
        <PitchRoom
          cameraShot={director.cameraShot}
          lightCue={director.lightCue}
          focusSeat={director.focusSeat}
          hoveredSeat={director.hoveredSeat}
          round={sim.round}
          roundCount={sim.roundCount}
          activeRound={sim.activeRound}
          isLoading={sim.isLoading || sim.prepLoading}
          statusText={sim.statusText}
          simulation={sim.simulation}
          canGoBack={sim.canGoBack}
          canGoNext={sim.canGoNext}
          onPrev={() => sim.setActiveRound((value) => value - 1)}
          onNext={() => sim.setActiveRound((value) => value + 1)}
          onSelectRound={sim.setActiveRound}
          onFocusSeat={director.focusStageSeat}
          onHoverSeat={director.hoverStageSeat}
          onHoverEnd={director.clearHoverSeat}
          htmlLayer={htmlLayer}
          hasSimulation={Boolean(sim.simulation)}
        />
      ) : null}

      <RoomHud
        stageTitle={sim.stageTitle}
        simulation={sim.simulation}
        isLoading={sim.isLoading || sim.prepLoading}
        round={sim.round}
        roundCount={sim.roundCount}
        activeRound={sim.activeRound}
        canGoBack={sim.canGoBack}
        canGoNext={sim.canGoNext}
        onPrev={() => sim.setActiveRound((value) => value - 1)}
        onNext={() => sim.setActiveRound((value) => value + 1)}
        onSelectRound={sim.setActiveRound}
        onOpenReports={sim.openReports}
        onOpenReview={() => sim.setReviewOpen(true)}
        onReset={sim.resetRoom}
      />

      <JudgeSpeechCard
        round={sim.round}
        roundCount={sim.roundCount}
        activeRound={sim.activeRound}
        isLoading={sim.isLoading || sim.prepLoading}
        statusText={sim.statusText}
        focusSeat={director.focusSeat}
        onFocusSeat={director.focusStageSeat}
        onHoverSeat={director.hoverStageSeat}
        onHoverEnd={director.clearHoverSeat}
        canGoBack={sim.canGoBack}
        canGoNext={sim.canGoNext}
        onPrev={() => sim.setActiveRound((value) => value - 1)}
        onNext={() => sim.setActiveRound((value) => value + 1)}
        onSelectRound={sim.setActiveRound}
        simulation={sim.simulation}
      />

      <ReportModal
        simulation={sim.simulation}
        open={sim.reviewOpen}
        onClose={() => sim.setReviewOpen(false)}
        onPracticeAgain={sim.practiceAgain}
      />
      <ReportsLibrary
        open={sim.reportsOpen}
        reports={sim.reports}
        summary={sim.reportsSummary}
        isLoading={sim.reportsLoading}
        error={sim.reportsError}
        onClose={() => sim.setReportsOpen(false)}
        onLoad={sim.loadReport}
        onUseSetup={sim.useRecommendedSetup}
        onUsePlan={sim.useTrainingPlan}
      />
      <PrepModal
        prep={sim.prepBrief}
        open={sim.prepOpen}
        onClose={() => sim.setPrepOpen(false)}
        onUsePitch={sim.usePrepPitch}
      />

      <PromptDock
        prompt={sim.prompt}
        onPromptChange={sim.setPrompt}
        answer={sim.answer}
        onAnswerChange={sim.setAnswer}
        counterOffer={sim.counterOffer}
        onCounterOfferChange={sim.setCounterOffer}
        stage={sim.stage}
        onStageChange={sim.setStage}
        objective={sim.objective}
        onObjectiveChange={sim.setObjective}
        length={sim.length}
        onLengthChange={sim.setLength}
        collapsed={sim.dockCollapsed}
        onToggleCollapsed={() => sim.setDockCollapsed((value) => !value)}
        error={sim.error}
        statusText={sim.statusText}
        prepLoading={sim.prepLoading}
        isLoading={sim.isLoading}
        counterLoading={sim.counterLoading}
        hasSimulation={Boolean(sim.simulation)}
        simulation={sim.simulation}
        onPrep={sim.runPrep}
        onSubmit={sim.runSimulation}
        onAnswer={sim.submitAnswer}
        onCounter={sim.submitCounterOffer}
      />
    </main>
  );
}
