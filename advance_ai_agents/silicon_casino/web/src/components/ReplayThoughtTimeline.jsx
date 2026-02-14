import React from 'react'

function seatTag(seatID) {
  if (seatID === null || seatID === undefined || seatID === '?') return 'Seat ?'
  return `Seat ${seatID}`
}

function whoLabel(item, seatLabelById, agentNameById) {
  if (item.seat_id !== null && item.seat_id !== undefined) {
    const label = seatLabelById?.[String(item.seat_id)]
    if (label) return label
  }
  if (item.actor_agent_id && agentNameById?.[item.actor_agent_id]) {
    return agentNameById[item.actor_agent_id]
  }
  if (item.actor_agent_id) return item.actor_agent_id
  return 'Unknown Agent'
}

export default function ReplayThoughtTimeline({ items, activeSeq, seatLabelById = {}, agentNameById = {} }) {
  return (
    <div className="replay-panel replay-thoughts">
      <div className="replay-panel-title">Thought Timeline</div>
      <div className="replay-panel-list">
        {items.length === 0 && <div className="muted">No thought logs yet</div>}
        {items.map((it) => {
          const cls = it.global_seq === activeSeq ? 'replay-thought-line is-active' : 'replay-thought-line'
          const who = whoLabel(it, seatLabelById, agentNameById)
          return (
            <div className={cls} key={`${it.global_seq}-${it.seat_id}-${it.thought_log.slice(0, 20)}`}>
              <div className="replay-thought-head">
                <span className="replay-log-seq">#{it.global_seq}</span>
                <span className="replay-thought-who">{who}</span>
                <span className="replay-log-seat">{seatTag(it.seat_id)}</span>
              </div>
              <div className="replay-log-text">{it.thought_log}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
