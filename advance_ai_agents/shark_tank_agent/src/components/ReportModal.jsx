import { useEffect, useState } from "react";
import { BarChart3, Dumbbell, List, Loader2, Play, Scale, Send, Trophy, X } from "lucide-react";
import { ScorePill } from "./ui.jsx";
import { winnerText } from "../utils.js";

const tabs = [
  { key: "verdict", label: "Verdict", hint: "Deal", icon: Scale },
  { key: "skills", label: "Skills", hint: "Map", icon: BarChart3 },
  { key: "drills", label: "Drills", hint: "Practice", icon: Dumbbell },
  { key: "transcript", label: "Transcript", hint: "Rounds", icon: List },
];

export function ReportModal({ simulation, open, onClose, onPracticeAgain }) {
  const [activeDrill, setActiveDrill] = useState(null);
  const [drillAnswer, setDrillAnswer] = useState("");
  const [drillFeedback, setDrillFeedback] = useState(null);
  const [drillLoading, setDrillLoading] = useState(false);
  const [drillError, setDrillError] = useState("");
  const [reportAttempts, setReportAttempts] = useState([]);
  const [reportTab, setReportTab] = useState("verdict");

  useEffect(() => {
    setReportAttempts(simulation?.drillAttempts || []);
    setReportTab("verdict");
  }, [simulation?.reportId, open]);

  if (!simulation) return null;
  const isSharkRoom = simulation.kind === "user-shark-room" || Boolean(simulation.finalDeal);
  if (!open || (!isSharkRoom && (!simulation.verdict || !simulation.totals))) {
    return null;
  }

  const diagnostics = simulation.promptDiagnostics;
  const missingFacts = diagnostics?.missingFacts || [];
  const skillScores = simulation.skillScores || [];
  const practiceDrills = simulation.practiceDrills || [];

  function chooseDrill(drill) {
    setActiveDrill(drill);
    setDrillAnswer("");
    setDrillFeedback(null);
    setDrillError("");
    setReportTab("drills");
  }

  async function submitDrill(event) {
    event.preventDefault();
    const answer = drillAnswer.trim();
    if (!answer) {
      setDrillError("Write your answer first.");
      return;
    }

    setDrillError("");
    setDrillLoading(true);
    setDrillFeedback(null);

    try {
      const response = await fetch("/api/drill-feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reportId: simulation.reportId,
          prompt: simulation.prompt,
          practiceContext: simulation.practiceContext,
          drill: activeDrill,
          answer,
        }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || "Drill feedback failed.");
      }
      setDrillFeedback(payload.data);
      if (payload.data?.attempt) {
        setReportAttempts((attempts) =>
          [payload.data.attempt, ...attempts.filter((attempt) => attempt.id !== payload.data.attempt.id)].slice(0, 8),
        );
      }
    } catch (caught) {
      setDrillError(caught instanceof Error ? caught.message : "Drill feedback failed.");
    } finally {
      setDrillLoading(false);
    }
  }

  function closeReport() {
    setActiveDrill(null);
    setDrillAnswer("");
    setDrillFeedback(null);
    setDrillError("");
    onClose();
  }

  if (isSharkRoom) {
    const finalDeal = simulation.finalDeal || {};
    const offers = finalDeal.offers || [];
    const counterOffers = finalDeal.counterOffers || [];
    const rounds = simulation.rounds || [];

    return (
      <div className="modal-shell" role="dialog" aria-modal="true" aria-label="Deal report">
        <button className="modal-backdrop" onClick={closeReport} type="button" aria-label="Close report" />
        <section className="report-modal">
          <div className="modal-chrome">
            <header className="modal-header">
              <div>
                <span>Deal memo</span>
                <h2>{simulation.businessTitle}</h2>
              </div>
              <button className="icon-button" onClick={closeReport} type="button" aria-label="Close report">
                <X size={18} aria-hidden="true" />
              </button>
            </header>

            <div className="report-tabs" role="tablist" aria-label="Report sections">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.key}
                    className={reportTab === tab.key ? "active" : ""}
                    onClick={() => setReportTab(tab.key)}
                    type="button"
                    role="tab"
                    aria-selected={reportTab === tab.key}
                  >
                    <Icon size={15} aria-hidden="true" />
                    <span>{tab.label}</span>
                    <small>{tab.hint}</small>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="report-body">
            {reportTab === "verdict" ? (
              <div className="report-panel deal-slip">
                <div className="modal-summary">
                  <div className="winner-banner">
                    <Trophy size={18} aria-hidden="true" />
                    <div>
                      <span>Outcome</span>
                      <strong>{finalDeal.outcome || winnerText(simulation.winner)}</strong>
                    </div>
                  </div>
                  {finalDeal.bestOffer ? (
                    <div className="review-note decision-note">
                      <span>Best terms</span>
                      <strong>{finalDeal.bestOffer.label || "No lead shark"}</strong>
                      <p>{finalDeal.bestOffer.terms || "No formal offer."}</p>
                    </div>
                  ) : null}
                </div>

                {offers.length ? (
                  <div className="offer-grid">
                    {offers.map((offer) => (
                      <article className="offer-card" key={offer.shark}>
                        <span>{offer.label}</span>
                        <h3>{offer.decision}</h3>
                        <p>
                          <strong>{offer.amount || "No check"}</strong>
                          {offer.equity ? ` for ${offer.equity}` : ""}
                        </p>
                      </article>
                    ))}
                  </div>
                ) : null}

                <div className="review-grid deal-fixes">
                  <div className="review-note">
                    <span>Keep</span>
                    <p>{finalDeal.strongestAnswer || "Your strongest round still needs a named proof point."}</p>
                  </div>
                  <div className="review-note">
                    <span>Fix</span>
                    <p>{finalDeal.weakestAnswer || "Tighten the weakest answer with a number and a next milestone."}</p>
                  </div>
                  <div className="review-note">
                    <span>Next</span>
                    <p>{(finalDeal.nextPractice && finalDeal.nextPractice[0]) || "Practice the live question again with a shorter ask."}</p>
                  </div>
                </div>

                <div className="deal-slip-actions">
                  <button className="prep-button" onClick={() => setReportTab("drills")} type="button">
                    <Dumbbell size={16} aria-hidden="true" />
                    Practice this
                  </button>
                  <button className="practice-again-button" onClick={() => onPracticeAgain(simulation)} type="button">
                    <Play size={16} aria-hidden="true" />
                    Practice again
                  </button>
                </div>
              </div>
            ) : null}

            {reportTab === "skills" ? (
              <div className="report-panel">
                {diagnostics ? (
                  <div className="review-note readiness-brief">
                    <span>Founder readiness</span>
                    <p>{diagnostics.stageFit}</p>
                    <div className="brief-grid">
                      <div>
                        <strong>Strongest signal</strong>
                        <p>{diagnostics.strongestSignal}</p>
                      </div>
                      <div>
                        <strong>First move</strong>
                        <p>{diagnostics.firstPracticeMove}</p>
                      </div>
                    </div>
                    {missingFacts.length ? (
                      <div className="missing-list">
                        <strong>Missing proof</strong>
                        {missingFacts.map((item) => (
                          <p key={item}>{item}</p>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : null}

            {reportTab === "drills" ? (
              <div className="report-panel">
                <div className="review-note">
                  <span>Practice next</span>
                  {(finalDeal.nextPractice || []).map((item) => (
                    <p key={item}>{item}</p>
                  ))}
                </div>
                {practiceDrills.length ? (
                  <div className="drill-list">
                    {practiceDrills.map((drill) => (
                      <article className="drill-card" key={drill.name}>
                        <h3>{drill.name}</h3>
                        <p>{drill.goal}</p>
                        <strong>{drill.prompt}</strong>
                      </article>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}

            {reportTab === "transcript" ? (
              <div className="report-panel round-report-list">
                <span>Live transcript</span>
                <h3>Founder answers</h3>
                {rounds.map((round, index) => (
                  <article className="round-report" key={round.id}>
                    <div>
                      <span>Round {index + 1} · {round.focus}</span>
                      <h4>{round.panelQuestion}</h4>
                      <p>{round.userAnswer}</p>
                    </div>
                    {["nemotron", "deepseek", "judge"].map((key) => {
                      const reaction = round.sharkReactions?.[key];
                      if (!reaction) return null;
                      return (
                        <p key={key}>
                          <strong>{reaction.label}</strong> · score {round.scores?.[key] ?? "-"} · interest{" "}
                          {round.interest?.[key] ?? "-"}: {reaction.reaction}
                        </p>
                      );
                    })}
                  </article>
                ))}
                {counterOffers.length ? (
                  <div className="review-note">
                    <span>Counter-offer responses</span>
                    <div className="offer-grid">
                      {counterOffers.map((counter) => (
                        <article className="offer-card" key={counter.shark}>
                          <span>{counter.label}</span>
                          <h3>{counter.decision}</h3>
                          <p>{counter.message}</p>
                          <p>
                            <strong>{counter.revisedAmount}</strong>
                            {counter.revisedEquity ? ` for ${counter.revisedEquity}` : ""}
                          </p>
                          <p>{counter.finalAdvice}</p>
                        </article>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="modal-shell" role="dialog" aria-modal="true" aria-label="Pitch report">
      <button className="modal-backdrop" onClick={closeReport} type="button" aria-label="Close report" />
      <section className="report-modal">
        <div className="modal-chrome">
          <header className="modal-header">
            <div>
              <span>Deal memo</span>
              <h2>{simulation.businessTitle}</h2>
            </div>
            <button className="icon-button" onClick={closeReport} type="button" aria-label="Close report">
              <X size={18} aria-hidden="true" />
            </button>
          </header>

          <div className="report-tabs" role="tablist" aria-label="Report sections">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.key}
                  className={reportTab === tab.key ? "active" : ""}
                  onClick={() => setReportTab(tab.key)}
                  type="button"
                  role="tab"
                  aria-selected={reportTab === tab.key}
                >
                  <Icon size={15} aria-hidden="true" />
                  <span>{tab.label}</span>
                  <small>{tab.hint}</small>
                </button>
              );
            })}
          </div>
        </div>

        <div className="report-body">

        {reportTab === "verdict" ? (
          <div className="report-panel">
            <div className="modal-summary">
              <div className="winner-banner">
                <Trophy size={18} aria-hidden="true" />
                <div>
                  <span>Final winner</span>
                  <strong>{winnerText(simulation.winner)}</strong>
                </div>
              </div>
              <div className="total-grid">
                <ScorePill
                  label={simulation.nemotron?.label?.replace(" Founder", "") || "MiniMax"}
                  value={simulation.totals.nemotron}
                  active={simulation.winner === "nemotron"}
                />
                <ScorePill
                  label="DeepSeek"
                  value={simulation.totals.deepseek}
                  active={simulation.winner === "deepseek"}
                />
              </div>
              {simulation.readinessScore != null ? (
                <ScorePill label="Readiness" value={simulation.readinessScore} active />
              ) : null}
            </div>

            <p className="judge-verdict">{simulation.verdict}</p>

            {simulation.practiceContext ? (
              <div className="context-strip">
                <span>{simulation.practiceContext.stageLabel}</span>
                <span>{simulation.practiceContext.objectiveLabel}</span>
              </div>
            ) : null}

            {simulation.rewrittenPitch ? (
              <div className="review-note pitch-note">
                <span>Practice pitch</span>
                <p>{simulation.rewrittenPitch}</p>
                <button className="practice-again-button" onClick={() => onPracticeAgain(simulation)} type="button">
                  <Play size={16} aria-hidden="true" />
                  Practice Again
                </button>
              </div>
            ) : null}

            {simulation.negotiation ? (
              <div className="review-note decision-note">
                <span>Final negotiation</span>
                <strong>{simulation.negotiation.decision}</strong>
                <p>{simulation.negotiation.offer}</p>
                <p>{simulation.negotiation.reason}</p>
              </div>
            ) : null}

            <div className="review-grid">
              <div className="review-note">
                <span>Strongest moment</span>
                <p>{simulation.strongestMoment}</p>
              </div>
              <div className="review-note">
                <span>Weakest moment</span>
                <p>{simulation.weakestMoment}</p>
              </div>
            </div>

            <div className="practice-list">
              <span>Practice next</span>
              {simulation.nextPractice.map((item) => (
                <p key={item}>{item}</p>
              ))}
            </div>

            <div className="practice-columns">
              {simulation.investorHooks?.length ? (
                <div className="practice-list">
                  <span>Hooks</span>
                  {simulation.investorHooks.map((item) => (
                    <p key={item}>{item}</p>
                  ))}
                </div>
              ) : null}
              {simulation.investorObjections?.length ? (
                <div className="practice-list">
                  <span>Objections</span>
                  {simulation.investorObjections.map((item) => (
                    <p key={item}>{item}</p>
                  ))}
                </div>
              ) : null}
              {simulation.nextDataToCollect?.length ? (
                <div className="practice-list">
                  <span>Data</span>
                  {simulation.nextDataToCollect.map((item) => (
                    <p key={item}>{item}</p>
                  ))}
                </div>
              ) : null}
            </div>

            {simulation.recommendedAskFraming ? (
              <div className="review-note">
                <span>Ask framing</span>
                <p>{simulation.recommendedAskFraming}</p>
              </div>
            ) : null}
          </div>
        ) : null}

        {reportTab === "skills" ? (
          <div className="report-panel">
            {diagnostics ? (
              <div className="review-note readiness-brief">
                <span>Founder readiness</span>
                <p>{diagnostics.stageFit}</p>
                <div className="brief-grid">
                  <div>
                    <strong>Strongest signal</strong>
                    <p>{diagnostics.strongestSignal}</p>
                  </div>
                  <div>
                    <strong>First move</strong>
                    <p>{diagnostics.firstPracticeMove}</p>
                  </div>
                </div>
                {missingFacts.length ? (
                  <div className="missing-list">
                    <strong>Missing proof</strong>
                    {missingFacts.map((item) => (
                      <p key={item}>{item}</p>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}

            {skillScores.length ? (
              <div className="review-note">
                <span>Skill map</span>
                <div className="skill-map">
                  {skillScores.map((skill) => (
                    <div className="skill-row" key={skill.key || skill.label}>
                      <div>
                        <strong>{skill.label}</strong>
                        <p>{skill.note}</p>
                      </div>
                      <b>{skill.score}</b>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="judge-comment">No skill map on this report.</p>
            )}
          </div>
        ) : null}

        {reportTab === "drills" ? (
          <div className="report-panel">
            {practiceDrills.length ? (
              <div className="review-note">
                <span>Practice drills</span>
                <div className="drill-list">
                  {practiceDrills.map((drill) => (
                    <article className="drill-card" key={drill.name}>
                      <h3>{drill.name}</h3>
                      <p>{drill.goal}</p>
                      <strong>{drill.prompt}</strong>
                      <button onClick={() => chooseDrill(drill)} type="button">
                        Practice
                      </button>
                    </article>
                  ))}
                </div>

                {activeDrill ? (
                  <form className="drill-coach" onSubmit={submitDrill}>
                    <div className="drill-coach-head">
                      <div>
                        <span>Live drill</span>
                        <h3>{activeDrill.name}</h3>
                        <p>{activeDrill.prompt}</p>
                      </div>
                      <button onClick={() => setActiveDrill(null)} type="button" aria-label="Close drill coach">
                        <X size={16} aria-hidden="true" />
                      </button>
                    </div>
                    <textarea
                      value={drillAnswer}
                      onChange={(event) => setDrillAnswer(event.target.value)}
                      placeholder="Type your answer like you are speaking to the investor..."
                      rows={4}
                    />
                    <div className="drill-actions">
                      {drillError ? (
                        <p className="error-text">{drillError}</p>
                      ) : (
                        <p>The sharks score your answer as investors.</p>
                      )}
                      <button disabled={drillLoading} type="submit">
                        {drillLoading ? <Loader2 className="spin" size={17} /> : <Send size={17} />}
                        Score Answer
                      </button>
                    </div>
                    {drillFeedback ? (
                      <div className="drill-feedback">
                        <ScorePill label="Your score" value={drillFeedback.score} active />
                        <p>{drillFeedback.verdict}</p>
                        <div className="review-grid">
                          <div>
                            <span>Strongest line</span>
                            <p>{drillFeedback.strongestLine}</p>
                          </div>
                          <div>
                            <span>Follow-up</span>
                            <p>{drillFeedback.investorFollowUp}</p>
                          </div>
                        </div>
                        {drillFeedback.missingProof?.length ? (
                          <div className="practice-list">
                            <span>Missing proof</span>
                            {drillFeedback.missingProof.map((item) => (
                              <p key={item}>{item}</p>
                            ))}
                          </div>
                        ) : null}
                        <div className="review-note pitch-note">
                          <span>Sharper answer</span>
                          <p>{drillFeedback.sharperAnswer}</p>
                        </div>
                        <div className="review-note">
                          <span>Next move</span>
                          <p>{drillFeedback.nextPracticeMove}</p>
                        </div>
                        {drillFeedback.attemptId ? <div className="saved-attempt">Saved to this report.</div> : null}
                      </div>
                    ) : null}
                  </form>
                ) : null}
              </div>
            ) : (
              <p className="judge-comment">No drills on this report.</p>
            )}

            {reportAttempts.length ? (
              <div className="review-note">
                <span>Your attempts</span>
                <div className="report-attempt-list">
                  {reportAttempts.slice(0, 5).map((attempt) => (
                    <article key={attempt.id}>
                      <div>
                        <strong>{attempt.drillName}</strong>
                        <p>{attempt.verdict || attempt.nextPracticeMove || attempt.drillPrompt}</p>
                      </div>
                      <b>{attempt.score}</b>
                    </article>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        {reportTab === "transcript" ? (
          <div className="report-panel round-report-list">
            <span>Live transcript</span>
            <h3>Round by round</h3>
            {simulation.rounds.map((round, index) => (
              <article className="round-report" key={round.id}>
                <div>
                  <span>Round {index + 1}</span>
                  <h4>{round.question}</h4>
                  <p>
                    {winnerText(round.winner)} · {simulation.nemotron?.label?.replace(" Founder", "") || "MiniMax"}{" "}
                    {round.scores?.nemotron ?? "-"} / DeepSeek {round.scores?.deepseek ?? "-"}
                  </p>
                </div>
                <p>{round.judgeComment}</p>
              </article>
            ))}
          </div>
        ) : null}
        </div>
      </section>
    </div>
  );
}
