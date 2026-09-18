import { Html } from "@react-three/drei";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { ScorePill } from "./ui.jsx";
import { winnerText } from "../utils.js";

function compactText(value, maxLength = 260) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= maxLength) return text;
  const cut = text.slice(0, maxLength);
  return `${cut.slice(0, Math.max(0, cut.lastIndexOf(" ")))}...`;
}

export function FounderSpeechCard({
  side,
  title,
  model,
  position,
  round,
  activeWinner,
  focusSeat,
  onFocusSeat,
  onHoverSeat,
  onHoverEnd,
  portal,
  htmlPosition,
}) {
  const answer = round?.sharkReactions?.[side] || round?.[side];
  const score = round?.scores?.[side];
  const interest = round?.interest?.[side];
  const loud = focusSeat === side;
  const reactionLimit = loud ? 320 : 220;
  const pressureLimit = loud ? 260 : 180;

  return (
    <Html position={htmlPosition} center zIndexRange={[30, 10]} portal={portal} occlude={false}>
      <section
        className={`founder-panel speech-card ${side} ${activeWinner === side ? "winner" : ""} ${focusSeat === side ? "focused" : ""} ${loud ? "loud" : "dim"}`}
        onMouseEnter={() => onHoverSeat?.(side)}
        onMouseLeave={() => onHoverEnd?.()}
        onClick={() => onFocusSeat(side)}
        tabIndex={0}
        aria-label={`Focus ${title}`}
      >
        <div className="panel-topline">
          <span>{title}</span>
          {loud ? <b className="on-air">On air</b> : <small>{model}</small>}
        </div>
        {round && answer ? (
          <>
            <div className="answer-block">
              <p>{compactText(answer.reaction || answer.answer, reactionLimit)}</p>
            </div>
            {loud ? (
              <div className="move-block">
                <span>{answer.dealSignal ? "Deal signal" : "Pressure"}</span>
                <p>{compactText(answer.dealSignal || answer.pressure || answer.boldMove, pressureLimit)}</p>
              </div>
            ) : null}
            {score != null ? (
              <ScorePill label={interest != null ? `Interest ${interest}` : "Round score"} value={score} active={activeWinner === side || loud} />
            ) : null}
          </>
        ) : (
          <>
            <p className="opening-position">{position}</p>
            <div className="empty-answer">Waiting for this shark.</div>
          </>
        )}
      </section>
    </Html>
  );
}

export function JudgeSpeechCard({
  round,
  roundCount,
  activeRound,
  isLoading,
  statusText,
  focusSeat,
  onFocusSeat,
  onHoverSeat,
  onHoverEnd,
  canGoBack,
  canGoNext,
  onPrev,
  onNext,
  onSelectRound,
  simulation,
}) {
  const leadReaction = round?.sharkReactions?.judge || round?.judge;
  const leadScore = round?.scores?.judge;
  const leadInterest = round?.interest?.judge;
  const leadLabel = simulation?.sharks?.judge?.label?.replace(" Lightning Shark", "").replace(" Shark", "") || "Nemotron";
  const leadFocused = focusSeat === "judge";
  const answered = Boolean(round?.userAnswer);

  return (
    <div className="question-hud">
      <div
        className={`judge-console speech-card ${focusSeat === "judge" ? "focused" : ""} ${answered ? "answered" : ""}`}
        onMouseEnter={() => onHoverSeat?.("judge")}
        onMouseLeave={() => onHoverEnd?.()}
        onClick={() => onFocusSeat("judge")}
        tabIndex={0}
        aria-label="Focus lead shark"
      >
        <div className="judge-label">{round?.askingSharkLabel ? `${round.askingSharkLabel} asks` : "Shark Panel"}</div>
        {round ? (
          <>
            <span className="round-kicker">
              Round {activeRound + 1} / {roundCount} · {round.focus}
            </span>
            <h2>
              {compactText(round.panelQuestion || round.question, answered ? 220 : 280)}
            </h2>
            {round.userAnswer && leadReaction ? (
              <div className="lead-shark-response">
                <div className="panel-topline center">
                  <span>{leadLabel}</span>
                  <small>{leadFocused ? "On air" : "Lead shark"}</small>
                </div>
                <div className="answer-block">
                  <p>{compactText(leadReaction.reaction, leadFocused ? 250 : 210)}</p>
                </div>
                {leadFocused ? (
                  <div className="move-block">
                    <span>{leadReaction.dealSignal ? "Deal signal" : "Pressure"}</span>
                    <p>{compactText(leadReaction.dealSignal || leadReaction.pressure, 180)}</p>
                  </div>
                ) : null}
                {leadScore != null ? (
                  <ScorePill
                    label={leadInterest != null ? `Interest ${leadInterest}` : "Round score"}
                    value={leadScore}
                    active={leadFocused}
                  />
                ) : null}
              </div>
            ) : round.userAnswer ? (
              <p className="judge-comment">Your answer is in. Click a shark seat to hear the pressure, score, and interest.</p>
            ) : (
              <p className="judge-comment">Your turn.</p>
            )}
            {simulation?.status === "complete" && simulation?.finalDeal ? (
              <div className="round-winner">{simulation.finalDeal.outcome || winnerText(simulation.winner)}</div>
            ) : round.winner ? <div className="round-winner">{winnerText(round.winner)}</div> : null}
            <div className="round-controls">
              <button
                disabled={!canGoBack}
                onClick={(event) => {
                  event.stopPropagation();
                  onPrev();
                }}
                type="button"
                aria-label="Previous round"
              >
                <ChevronLeft size={17} aria-hidden="true" />
              </button>
              <div className="round-dots">
                {Array.from({ length: roundCount }, (_, index) => (
                  <button
                    key={index}
                    className={index === activeRound ? "active" : ""}
                    aria-label={`Open round ${index + 1}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelectRound(index);
                    }}
                    type="button"
                  />
                ))}
              </div>
              <button
                disabled={!canGoNext}
                onClick={(event) => {
                  event.stopPropagation();
                  onNext();
                }}
                type="button"
                aria-label="Next round"
              >
                <ChevronRight size={17} aria-hidden="true" />
              </button>
            </div>
            {isLoading && statusText ? <p className="stream-status">{statusText}</p> : null}
          </>
        ) : isLoading ? (
          <div className="loading-room">
            <Loader2 className="spin" size={28} aria-hidden="true" />
            <p>{statusText || "Asking the sharks to enter the room."}</p>
          </div>
        ) : (
          <>
            <span className="round-kicker">Ready</span>
            <h2>The sharks will ask. You answer.</h2>
          </>
        )}
      </div>
    </div>
  );
}
