import React, { useMemo, useRef, useState } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'

function typeLabel(t) {
  if (t === 'thought') return 'THOUGHT'
  if (t === 'action') return 'ACTION'
  if (t === 'settled') return 'SETTLED'
  if (t === 'street') return 'STREET'
  return 'EVENT'
}

function formatBody(item) {
  if (item.type === 'thought') return item.thought || ''
  if (item.type === 'action') {
    const amount = item.amount_cc ? ` ${item.amount_cc}` : ''
    return `${String(item.action || '').toUpperCase()}${amount}`
  }
  if (item.type === 'settled') {
    const winner = item.winner_name || item.who || '-'
    return `Winner: ${winner} • Pot: ${item.pot_cc ?? 0} CC`
  }
  if (item.type === 'street') return `Street advanced to ${item.street || '-'}`
  return item.text || ''
}

export default function ReplayEventFeed({ items, activeSeq, onJumpSeq }) {
  const [expanded, setExpanded] = useState({})
  const parentRef = useRef(null)

  const view = useMemo(() => items || [], [items])
  const virtualizer = useVirtualizer({
    count: view.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 72,
    overscan: 8
  })
  const virtualItems = virtualizer.getVirtualItems()

  return (
    <div className="replay-panel replay-event-feed">
      <div className="replay-panel-title">Unified Event Feed</div>
      <div ref={parentRef} className="replay-panel-list replay-event-list replay-event-list-virtual-parent">
        {view.length === 0 && <div className="muted">No replay events yet</div>}
        {view.length > 0 && <div className="replay-event-list-virtual-spacer" style={{ height: `${virtualizer.getTotalSize()}px` }} />}
        {virtualItems.map((vi) => {
          const it = view[vi.index]
          const key = `${it.seq}-${it.type}-${it.seat ?? '-'}`
          const active = it.seq === activeSeq
          const isExpanded = !!expanded[key]
          const body = formatBody(it)
          const showToggle = it.type === 'thought' && body.length > 72
          const text = showToggle && !isExpanded ? `${body.slice(0, 72)}...` : body
          return (
            <div
              key={key}
              ref={virtualizer.measureElement}
              data-index={vi.index}
              className={`replay-event-card replay-event-${it.type} ${active ? 'is-active' : ''}`}
              style={{ transform: `translateY(${vi.start}px)` }}
            >
              <div className="replay-event-head">
                <span className="replay-log-seq">#{it.seq}</span>
                <span className="replay-event-type">{typeLabel(it.type)}</span>
                <span className="replay-event-who">{it.who || 'Seat ?'}</span>
                <span className="replay-log-seat">{`S${it.seat ?? '?'}`}</span>
                <span className="replay-event-street">{it.street || '-'}</span>
                <span className="replay-event-hand">{`Hand ${it.hand_no || '-'}`}</span>
              </div>
              <div className="replay-event-body">{text}</div>
              <div className="replay-event-foot">
                {showToggle && (
                  <button
                    className="replay-event-link"
                    onClick={() => setExpanded((prev) => ({ ...prev, [key]: !prev[key] }))}
                  >
                    {isExpanded ? 'Collapse' : 'Expand'}
                  </button>
                )}
                {typeof onJumpSeq === 'function' && (
                  <button className="replay-event-link" onClick={() => onJumpSeq(it.seq)}>
                    Jump
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
