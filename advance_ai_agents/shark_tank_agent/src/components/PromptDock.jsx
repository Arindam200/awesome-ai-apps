import { useState } from "react";
import { ChevronDown, ClipboardCheck, Loader2, Play, Send, HandCoins, Plus } from "lucide-react";
import { lengths, objectives, stages } from "../constants.js";
import { SegmentedControl } from "./ui.jsx";

const pitchHints = [
  { key: "sell", label: "Offer", insert: "We sell " },
  { key: "customer", label: "Customer", insert: "Our customer is " },
  { key: "revenue", label: "Revenue", insert: "Last month we made " },
  { key: "ask", label: "Ask", insert: "We are raising " },
  { key: "team", label: "Team", insert: "The team is " },
];

const runShortcut =
  typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘ Enter" : "Ctrl+Enter";

export function PromptDock({
  prompt,
  onPromptChange,
  answer,
  onAnswerChange,
  counterOffer,
  onCounterOfferChange,
  stage,
  onStageChange,
  objective,
  onObjectiveChange,
  length,
  onLengthChange,
  collapsed,
  onToggleCollapsed,
  error,
  statusText,
  prepLoading,
  isLoading,
  counterLoading,
  hasSimulation,
  simulation,
  onPrep,
  onSubmit,
  onAnswer,
  onCounter,
}) {
  const [setupOpen, setSetupOpen] = useState(false);
  const hasCounterResponses = Boolean(simulation?.finalDeal?.counterOffers?.length);
  const mode =
    simulation?.status === "awaiting-answer"
      ? "answer"
      : simulation?.status === "complete" && !hasCounterResponses
        ? "counter"
        : simulation?.status === "complete"
          ? "done"
          : "pitch";
  const currentRound = simulation?.rounds?.[simulation?.currentRoundIndex || 0] || null;
  const stageLabel = stages.find((item) => item.key === stage)?.label || stage;
  const focusLabel = objectives.find((item) => item.key === objective)?.label || objective;
  const roomLabel = lengths.find((item) => item.key === length)?.label || length;
  const kicker = mode === "answer" ? "Your answer" : mode === "counter" ? "Your counter" : mode === "done" ? "Your pitch" : "Your pitch";

  function addHint(insert) {
    if (mode !== "pitch") return;
    if (prompt.toLowerCase().includes(insert.trim().toLowerCase())) return;
    const next = prompt.trim() ? `${prompt.trim()}\n${insert}` : insert;
    onPromptChange(next);
  }

  function handleKeyDown(event) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      if (mode === "answer") {
        onAnswer(event);
      } else if (mode === "counter") {
        onCounter(event);
      } else if (mode === "pitch") {
        onSubmit(event);
      }
    }
  }

  const formSubmit =
    mode === "answer" ? onAnswer : mode === "counter" ? onCounter : mode === "pitch" ? onSubmit : (event) => event.preventDefault();
  const value = mode === "answer" ? answer : mode === "counter" ? counterOffer : prompt;
  const onChange = mode === "answer" ? onAnswerChange : mode === "counter" ? onCounterOfferChange : onPromptChange;
  const disabled = isLoading || prepLoading || counterLoading;
  const mainLabel = mode === "answer" ? "Submit answer" : mode === "counter" ? "Send counter" : "Enter the tank";
  const MainIcon = mode === "answer" ? Send : mode === "counter" ? HandCoins : Play;
  const fieldChars = String(value || "").trim().length;

  return (
    <form className={`prompt-dock ${collapsed ? "collapsed" : ""} mode-${mode}`} onSubmit={formSubmit}>
      {collapsed ? (
        <div className="dock-collapsed-row">
          <div>
            <span>{kicker}</span>
            <p>{error || statusText || (isLoading ? "Sharks are thinking." : "Room ready. Expand to continue.")}</p>
          </div>
          <button className="prep-button" onClick={onToggleCollapsed} type="button">
            Open
          </button>
        </div>
      ) : (
        <>
          <div className="dock-top">
            <div>
              <span className="dock-kicker">{kicker}</span>
              <strong>
                {mode === "answer"
                  ? `Round ${(simulation?.currentRoundIndex || 0) + 1}`
                  : mode === "counter"
                    ? "Counter the deal"
                    : mode === "done"
                      ? "Negotiation complete"
                      : "Pitch the sharks"}
              </strong>
            </div>
            {mode === "pitch" ? (
              <button
                className={`dock-setup-toggle ${setupOpen ? "open" : ""}`}
                type="button"
                onClick={() => setSetupOpen((open) => !open)}
                aria-expanded={setupOpen}
              >
                <span>Room setup</span>
                <small>
                  {stageLabel} · {focusLabel} · {roomLabel}
                </small>
                <ChevronDown size={14} aria-hidden="true" />
              </button>
            ) : null}
          </div>
          {mode === "pitch" && setupOpen ? (
            <div className="dock-config-panel" aria-label="Room settings">
              <SegmentedControl label="Stage" value={stage} options={stages} onChange={onStageChange} />
              <SegmentedControl label="Focus" value={objective} options={objectives} onChange={onObjectiveChange} />
              <SegmentedControl label="Room" value={length} options={lengths} onChange={onLengthChange} />
            </div>
          ) : null}
          {mode === "done" ? (
            <div className="dock-complete-note">
              <strong>{simulation?.finalDeal?.outcome || "Final decision logged"}</strong>
              <p>Open Review in the top bar to read the deal slip.</p>
            </div>
          ) : (
            <label className="dock-field">
              <span>
                {mode === "answer" ? "Your answer" : mode === "counter" ? "Your counter-offer" : "Your business"}
                <small>
                  {fieldChars} chars · {runShortcut}
                </small>
              </span>
              <textarea
                value={value}
                onChange={(event) => onChange(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  mode === "answer"
                    ? "Answer the current panel question with proof, numbers, risk, and the next milestone."
                    : mode === "counter"
                      ? "Counter like a founder: amount, equity, why the terms are fair, and what milestone you commit to."
                      : "What you sell, who buys, revenue, the ask, and the team."
                }
                rows={3}
              />
            </label>
          )}
          {mode === "counter" && simulation?.finalDeal?.bestOffer?.terms ? (
            <div className="dock-context-line">
              Best offer: {simulation.finalDeal.bestOffer.label} · {simulation.finalDeal.bestOffer.terms}
            </div>
          ) : null}
          <div className="dock-actions">
            {error ? (
              <p className="error-text">{error}</p>
            ) : mode === "pitch" ? (
              <div className="dock-hints" aria-label="Add pitch details">
                {pitchHints.map((hint) => (
                  <button key={hint.key} type="button" onClick={() => addHint(hint.insert)} title={`Insert "${hint.insert.trim()}"`}>
                    <Plus size={13} aria-hidden="true" />
                    {hint.label}
                  </button>
                ))}
              </div>
            ) : (
              <p>
                {statusText ||
                  (mode === "answer"
                    ? `${currentRound?.askingSharkLabel || "This shark"} asked. Your answer goes to all three sharks.`
                    : mode === "counter"
                      ? "All sharks respond independently to your counter."
                      : "Final report is ready in Review.")}
              </p>
            )}
            <div className="dock-buttons">
              {hasSimulation && !disabled ? (
                <button className="prep-button" onClick={onToggleCollapsed} type="button">
                  Hide
                </button>
              ) : null}
              {mode === "pitch" ? (
                <button className="prep-button" disabled={disabled} onClick={onPrep} type="button">
                  {prepLoading ? <Loader2 className="spin" size={18} /> : <ClipboardCheck size={18} />}
                  Prep
                </button>
              ) : null}
              {mode !== "done" ? (
                <button className="run-button" disabled={disabled} type="submit">
                  {disabled ? <Loader2 className="spin" size={18} /> : <MainIcon size={18} />}
                  {mainLabel}
                </button>
              ) : null}
            </div>
          </div>
        </>
      )}
    </form>
  );
}
