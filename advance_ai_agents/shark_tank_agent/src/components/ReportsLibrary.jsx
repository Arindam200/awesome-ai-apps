import { Loader2, X } from "lucide-react";
import { founderName } from "../utils.js";

export function ReportsLibrary({
  open,
  reports,
  summary,
  isLoading,
  error,
  onClose,
  onLoad,
  onUseSetup,
  onUsePlan,
}) {
  if (!open) {
    return null;
  }
  const weakest = summary?.latestWeakestSkill;
  const dashboard = summary?.dashboard;
  const recommendedSetup = dashboard?.recommendedSetup;
  const skillAverages = dashboard?.skillAverages || [];
  const topStages = dashboard?.stageMix?.slice(0, 3) || [];
  const topFocus = dashboard?.focusMix?.slice(0, 3) || [];
  const latestDrill = dashboard?.latestDrill;
  const drillProgress = dashboard?.drillProgress;
  const recentAttempts = drillProgress?.recent || [];
  const trainingPlan = dashboard?.trainingPlan || [];
  const planSetup = dashboard?.planSetup;

  return (
    <div className="modal-shell" role="dialog" aria-modal="true" aria-label="Saved reports">
      <button className="modal-backdrop" onClick={onClose} type="button" aria-label="Close saved reports" />
      <section className="report-modal library-modal">
        <header className="modal-header">
          <div>
            <span>Practice Library</span>
            <h2>Saved Reports</h2>
          </div>
          <button className="icon-button" onClick={onClose} type="button" aria-label="Close saved reports">
            <X size={18} aria-hidden="true" />
          </button>
        </header>

        {summary ? (
          <div className="library-stats">
            <div>
              <span>Sessions</span>
              <strong>{summary.sessionCount}</strong>
            </div>
            <div>
              <span>Avg readiness</span>
              <strong>{summary.averageReadiness ?? "-"}</strong>
            </div>
            <div>
              <span>Best readiness</span>
              <strong>{summary.bestReadiness ?? "-"}</strong>
            </div>
            <div>
              <span>Latest weak skill</span>
              <strong>{weakest ? `${weakest.label} ${weakest.score}` : "-"}</strong>
            </div>
          </div>
        ) : null}

        {dashboard ? (
          <section className="practice-dashboard">
            <div className="dashboard-head">
              <div>
                <span>Practice dashboard</span>
                <h3>Next best room</h3>
                <p>{recommendedSetup?.reason}</p>
              </div>
              {recommendedSetup ? (
                <div className="dashboard-actions">
                  {planSetup ? (
                    <button onClick={() => onUsePlan(planSetup)} type="button">
                      Use Plan
                    </button>
                  ) : null}
                  <button onClick={() => onUseSetup(recommendedSetup)} type="button">
                    Use Setup
                  </button>
                </div>
              ) : null}
            </div>
            {recommendedSetup ? (
              <div className="context-strip">
                <span>{recommendedSetup.stageLabel}</span>
                <span>{recommendedSetup.objectiveLabel}</span>
                <span>{recommendedSetup.lengthLabel}</span>
              </div>
            ) : null}

            {drillProgress ? (
              <div className="human-progress">
                <div>
                  <span>Human attempts</span>
                  <strong>{drillProgress.attemptCount}</strong>
                </div>
                <div>
                  <span>Avg drill score</span>
                  <strong>{drillProgress.averageScore ?? "-"}</strong>
                </div>
                <div>
                  <span>Best drill score</span>
                  <strong>{drillProgress.bestScore ?? "-"}</strong>
                </div>
                <div>
                  <span>Latest drill score</span>
                  <strong>{drillProgress.latestScore ?? "-"}</strong>
                </div>
              </div>
            ) : null}

            {skillAverages.length ? (
              <div className="dashboard-skills">
                {skillAverages.slice(0, 6).map((skill) => (
                  <div className="dashboard-skill" key={skill.key}>
                    <div>
                      <strong>{skill.label}</strong>
                      <span>{skill.score}</span>
                    </div>
                    <meter min="0" max="100" value={skill.score} />
                  </div>
                ))}
              </div>
            ) : null}

            {trainingPlan.length ? (
              <div className="training-plan">
                <span>Training plan</span>
                {trainingPlan.map((item, index) => (
                  <article key={`${item.title}-${index}`}>
                    <b>{index + 1}</b>
                    <div>
                      <strong>{item.title}</strong>
                      <p>{item.action}</p>
                      <small>{item.detail}</small>
                    </div>
                  </article>
                ))}
              </div>
            ) : null}

            <div className="dashboard-meta">
              {topStages.length ? (
                <div>
                  <span>Stage mix</span>
                  <p>{topStages.map((item) => `${item.label} ${item.count}`).join(" · ")}</p>
                </div>
              ) : null}
              {topFocus.length ? (
                <div>
                  <span>Focus mix</span>
                  <p>{topFocus.map((item) => `${item.label} ${item.count}`).join(" · ")}</p>
                </div>
              ) : null}
              {latestDrill ? (
                <div>
                  <span>Last drill</span>
                  <p>
                    {latestDrill.name}: {latestDrill.prompt}
                  </p>
                </div>
              ) : null}
            </div>

            {recentAttempts.length ? (
              <div className="attempt-list">
                <span>Recent human practice</span>
                {recentAttempts.slice(0, 3).map((attempt) => (
                  <article key={attempt.id}>
                    <div>
                      <strong>{attempt.drillName}</strong>
                      <p>{attempt.verdict || attempt.nextPracticeMove || attempt.drillPrompt}</p>
                    </div>
                    <b>{attempt.score}</b>
                  </article>
                ))}
              </div>
            ) : null}
          </section>
        ) : null}

        {isLoading ? (
          <div className="library-empty">
            <Loader2 className="spin" size={22} aria-hidden="true" />
            <p>Loading saved pitch rooms.</p>
          </div>
        ) : error ? (
          <div className="library-empty">
            <p>{error}</p>
          </div>
        ) : reports.length ? (
          <div className="session-list">
            {reports.map((report) => (
              <article className="session-card" key={report.id}>
                <div>
                  <span>
                    {report.stageLabel} · {report.objectiveLabel} · {report.lengthLabel} ·{" "}
                    {new Date(report.createdAt).toLocaleDateString()}
                  </span>
                  <h3>{report.title}</h3>
                  <p>{report.promptSummary}</p>
                  <small>
                    {report.kind === "user-shark-room" ? "Outcome" : "Winner"}:{" "}
                    {report.dealOutcome || founderName(report.winner)}
                    {report.readinessScore != null ? ` · Readiness ${report.readinessScore}` : ""}
                    {report.weakestSkill ? ` · Work on ${report.weakestSkill.label}` : ""}
                  </small>
                </div>
                <div className="session-actions">
                  <button onClick={() => onLoad(report.id)} type="button">
                    Load
                  </button>
                  <a href={report.reportUrl} target="_blank" rel="noreferrer">
                    Doc
                  </a>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="library-empty">
            <p>No saved pitch reports yet.</p>
          </div>
        )}
      </section>
    </div>
  );
}
