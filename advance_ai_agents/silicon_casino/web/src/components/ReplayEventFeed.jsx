import React, { useEffect, useMemo, useRef, useState } from 'react'

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
  const [autoFollow, setAutoFollow] = useState(true)
  const parentRef = useRef(null)
  const userInteractedRef = useRef(false)
  const programmaticScrollRef = useRef(false)

  const view = useMemo(() => items || [], [items])
  const annotated = useMemo(() => {
    const seqTotal = new Map()
    for (const it of view) seqTotal.set(it.seq, (seqTotal.get(it.seq) || 0) + 1)
    const seqSeen = new Map()
    return view.map((it, rowIndex) => {
      const order = (seqSeen.get(it.seq) || 0) + 1
      seqSeen.set(it.seq, order)
      return { ...it, _seqOrder: order, _seqTotal: seqTotal.get(it.seq) || 1, _rowIndex: rowIndex }
    })
  }, [view])
  const grouped = useMemo(() => {
    const bySeq = new Map()
    for (const it of annotated) {
      const key = String(it.seq)
      if (!bySeq.has(key)) bySeq.set(key, { seq: it.seq, items: [] })
      bySeq.get(key).items.push(it)
    }
    return Array.from(bySeq.values()).sort((a, b) => Number(a.seq) - Number(b.seq))
  }, [annotated])
  const activeIndex = useMemo(() => annotated.findIndex((it) => it.seq === activeSeq), [annotated, activeSeq])

  useEffect(() => {
    const el = parentRef.current
    if (!el) return undefined
    const onUserIntent = () => {
      userInteractedRef.current = true
    }
    const onScroll = () => {
      if (programmaticScrollRef.current) {
        programmaticScrollRef.current = false
        return
      }
      if (!userInteractedRef.current) return
      const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight
      setAutoFollow(distanceToBottom <= 24)
    }
    el.addEventListener('wheel', onUserIntent, { passive: true })
    el.addEventListener('touchmove', onUserIntent, { passive: true })
    el.addEventListener('mousedown', onUserIntent)
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      el.removeEventListener('wheel', onUserIntent)
      el.removeEventListener('touchmove', onUserIntent)
      el.removeEventListener('mousedown', onUserIntent)
      el.removeEventListener('scroll', onScroll)
    }
  }, [])

  useEffect(() => {
    if (!autoFollow) return
    if (activeIndex < 0) return
    const el = parentRef.current
    if (!el) return
    const row = el.querySelector(`[data-log-index="${activeIndex}"]`)
    if (row) {
      programmaticScrollRef.current = true
      row.scrollIntoView({ block: 'end' })
    }
  }, [autoFollow, activeIndex])

  return (
    <div className="replay-event-feed">
      <div className="replay-panel-title">AI LOG</div>
      <div ref={parentRef} className="replay-panel-list replay-event-list replay-event-list-virtual-parent">
        {annotated.length === 0 && <div className="muted">No replay events yet</div>}
        {grouped.map((group) => (
          <div key={`grp-${group.seq}`} className={`replay-event-group ${group.seq === activeSeq ? 'is-active' : ''}`}>
            <div className="replay-event-group-head">
              <span className="replay-log-seq">{`#${group.seq}`}</span>
              <span className="replay-event-group-count">{`${group.items.length} item${group.items.length > 1 ? 's' : ''}`}</span>
            </div>
            {group.items.map((it) => {
              const key = `${it.seq}-${it.type}-${it.seat ?? '-'}-${it._rowIndex}`
              const active = it.seq === activeSeq
              const isExpanded = !!expanded[key]
              const body = formatBody(it)
              const showToggle = it.type === 'thought' && body.length > 72
              const text = showToggle && !isExpanded ? `${body.slice(0, 72)}...` : body
              return (
                <div
                  key={key}
                  data-log-index={it._rowIndex}
                  className={`replay-event-card replay-event-${it.type} ${active ? 'is-active' : ''}`}
                >
                  <div className="replay-event-head">
                    <span className="replay-log-seq">{`#${it.seq}.${it._seqOrder}`}</span>
                    <span className="replay-event-type">{typeLabel(it.type)}</span>
                    <span className="replay-event-who">{it.who || 'Seat ?'}</span>
                  </div>
                  <div className="replay-event-body">{text}</div>
                  <div className="replay-event-detail">
                    <span className="replay-log-seat">{`S${it.seat ?? '?'}`}</span>
                    <span className="replay-event-street">{it.street || '-'}</span>
                    <span className="replay-event-hand">{`Hand ${it.hand_no || '-'}`}</span>
                    {it._seqTotal > 1 && <span className="replay-event-flow">{`step ${it._seqOrder}/${it._seqTotal}`}</span>}
                  </div>
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
        ))}
      </div>
    </div>
  )
}
