import React from 'react'

export default function ThoughtLog({ items }) {
  return (
    <div className="thought-panel">
      <div className="panel-title">Thought Log</div>
      <div className="thought-list">
        {items.length === 0 && <div className="muted">Awaiting thoughts</div>}
        {items.map((t, idx) => (
          <div key={`${t.t}-${idx}`} className="thought-line">
            <span className="thought-time">{t.t}</span>
            <span className="thought-seat">Seat {t.seat}</span>
            <span className="thought-text">{t.text}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
