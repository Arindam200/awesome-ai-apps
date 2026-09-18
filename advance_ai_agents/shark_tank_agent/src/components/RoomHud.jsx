import { FileText, RotateCcw, Trophy } from "lucide-react";

export function RoomHud({
  stageTitle,
  simulation,
  isLoading,
  round,
  roundCount,
  activeRound,
  canGoBack,
  canGoNext,
  onPrev,
  onNext,
  onSelectRound,
  onOpenReports,
  onOpenReview,
  onReset,
}) {
  return (
    <>
      <header className="room-header">
        <div>
          <span className={`status-dot ${isLoading ? "busy" : ""}`} />
          Live room
          {stageTitle ? <small>{stageTitle}</small> : null}
        </div>
        <nav className="top-actions" aria-label="Simulation actions">
          <button onClick={onOpenReports} type="button">
            <FileText size={15} />
            Reports
          </button>
          {simulation?.reportUrl ? (
            <button onClick={onOpenReview} type="button">
              <Trophy size={15} />
              Review
            </button>
          ) : null}
          {simulation ? (
            <button onClick={onReset} type="button">
              <RotateCcw size={15} />
              New
            </button>
          ) : null}
        </nav>
      </header>

      {simulation ? (
        <div className="round-strip" aria-label="Round filmstrip">
          <button disabled={!canGoBack} onClick={onPrev} type="button" aria-label="Previous round">
            ‹
          </button>
          <div className="round-dots">
            {Array.from({ length: roundCount }, (_, index) => (
              <button
                key={index}
                className={index === activeRound ? "active" : ""}
                aria-label={`Open round ${index + 1}`}
                onClick={() => onSelectRound(index)}
                type="button"
              />
            ))}
          </div>
          <button disabled={!canGoNext} onClick={onNext} type="button" aria-label="Next round">
            ›
          </button>
          {round?.focus ? (
            <span>
              Round {activeRound + 1} · {round.askingSharkLabel ? `${round.askingSharkLabel} · ` : ""}
              {round.focus}
            </span>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
