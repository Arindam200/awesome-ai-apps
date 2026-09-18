import { Play, X } from "lucide-react";
import { ScorePill } from "./ui.jsx";

export function PrepModal({ prep, open, onClose, onUsePitch }) {
  if (!open || !prep) {
    return null;
  }

  return (
    <div className="modal-shell" role="dialog" aria-modal="true" aria-label="Founder prep brief">
      <button className="modal-backdrop" onClick={onClose} type="button" aria-label="Close prep brief" />
      <section className="report-modal prep-modal">
        <header className="modal-header">
          <div>
            <span>Founder Prep</span>
            <h2>{prep.businessTitle}</h2>
          </div>
          <button className="icon-button" onClick={onClose} type="button" aria-label="Close prep brief">
            <X size={18} aria-hidden="true" />
          </button>
        </header>

        <div className="modal-summary prep-summary">
          <ScorePill label="Readiness" value={prep.readinessScore ?? "-"} active />
          <div className="review-note prep-compact">
            <span>Stage fit</span>
            <p>{prep.stageFit}</p>
          </div>
        </div>

        <div className="review-note">
          <span>Best pitch angle</span>
          <p>{prep.pitchAngle}</p>
        </div>

        <div className="review-grid">
          <div className="review-note">
            <span>Strongest signal</span>
            <p>{prep.strongestSignal}</p>
          </div>
          <div className="review-note">
            <span>Next move</span>
            <p>{prep.nextMove}</p>
          </div>
        </div>

        <div className="practice-columns">
          {prep.missingFacts?.length ? (
            <div className="practice-list">
              <span>Missing proof</span>
              {prep.missingFacts.map((item) => (
                <p key={item}>{item}</p>
              ))}
            </div>
          ) : null}
          {prep.scaleLevers?.length ? (
            <div className="practice-list">
              <span>Scale levers</span>
              {prep.scaleLevers.map((item) => (
                <p key={item}>{item}</p>
              ))}
            </div>
          ) : null}
          {prep.riskWatch?.length ? (
            <div className="practice-list">
              <span>Risk watch</span>
              {prep.riskWatch.map((item) => (
                <p key={item}>{item}</p>
              ))}
            </div>
          ) : null}
        </div>

        <div className="review-note pitch-note">
          <span>Rehearse this</span>
          <p>{prep.rewrittenPitch}</p>
          <button className="practice-again-button" onClick={() => onUsePitch(prep)} type="button">
            <Play size={16} aria-hidden="true" />
            Use Pitch
          </button>
        </div>

        {prep.askFraming ? (
          <div className="review-note">
            <span>Ask framing</span>
            <p>{prep.askFraming}</p>
          </div>
        ) : null}

        {prep.likelyFirstQuestions?.length ? (
          <div className="practice-list">
            <span>Likely first questions</span>
            {prep.likelyFirstQuestions.map((item) => (
              <p key={item}>{item}</p>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}
