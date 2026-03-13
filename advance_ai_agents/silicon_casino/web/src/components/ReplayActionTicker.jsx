import React from 'react'

export default function ReplayActionTicker({ items, activeSeq }) {
  return (
    <div className="replay-panel replay-actions">
      <div className="replay-panel-title">Action Ticker</div>
      <div className="replay-panel-list">
        {items.length === 0 && <div className="muted">No actions yet</div>}
        {items.map((it) => {
          const cls = it.global_seq === activeSeq ? 'replay-log-line is-active' : 'replay-log-line'
          const amount = it.amount_cc ? ` ${it.amount_cc}` : ''
          return (
            <div className={cls} key={`${it.global_seq}-${it.action || ''}-${it.seat_id || ''}`}>
              <span className="replay-log-seq">#{it.global_seq}</span>
              <span className="replay-log-seat">S{it.seat_id ?? '-'}</span>
              <span className="replay-log-text">{`${it.action || it.event_type}${amount}`}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
