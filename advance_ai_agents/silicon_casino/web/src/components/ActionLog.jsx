import React from 'react'

export default function ActionLog({ items }) {
  return (
    <div className="log-panel">
      <div className="panel-title">Action Log</div>
      <div className="log-list">
        {items.length === 0 && <div className="muted">No events yet</div>}
        {items.map((e, idx) => (
          <div key={`${e.ts}-${idx}`} className="log-line">
            <span className="log-time">{e.ts}</span>
            <span className="log-action">
              Seat {e.seat} {e.action}
              {e.amount ? ` ${e.amount}` : ''}
            </span>
            {e.thought ? <span className="log-thought">"{e.thought}"</span> : null}
          </div>
        ))}
      </div>
    </div>
  )
}
