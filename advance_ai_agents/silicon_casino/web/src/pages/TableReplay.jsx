import React, { useEffect, useMemo } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import ReplayEventFeed from '../components/ReplayEventFeed.jsx'
import ReplayTableStage from '../components/ReplayTableStage.jsx'
import { getTableReplay, getTableSnapshot, getTableTimeline } from '../services/api.js'
import { useReplayStore } from '../state/useReplayStore.js'

function toSeatMap(payload) {
  const seatMeta = new Map()
  for (const it of payload?.seat_map || []) {
    seatMeta.set(it.seat_id, {
      agent_id: it.agent_id,
      agent_name: it.agent_name
    })
  }
  const seats = []
  for (const s of payload?.stacks || []) {
    const m = seatMeta.get(s.seat_id) || {}
    seats.push({
      seat_id: s.seat_id,
      agent_id: m.agent_id || s.agent_id || `seat-${s.seat_id}`,
      agent_name: m.agent_name || s.agent_id || `Seat ${s.seat_id}`,
      stack: s.stack,
      hole_cards: null,
      last_action: s.last_action,
      last_action_amount: s.last_action_amount
    })
  }
  return seats
}

function normalizeEvent(raw) {
  return {
    id: raw.id,
    hand_id: raw.hand_id,
    global_seq: raw.global_seq,
    event_type: raw.event_type,
    actor_agent_id: raw.actor_agent_id,
    payload: raw.payload || {}
  }
}

function buildHoleCardsByHand(events) {
  const map = new Map()
  for (const ev of events) {
    if (ev.event_type !== 'showdown') continue
    const handID = ev.hand_id || ev.payload?.hand_id
    if (!handID) continue
    const handMap = map.get(handID) || new Map()
    for (const row of ev.payload?.showdown || []) {
      if (!row?.agent_id) continue
      handMap.set(row.agent_id, row.hole_cards || [])
    }
    map.set(handID, handMap)
  }
  return map
}

function buildStateFrames(events, holeByHand) {
  const frames = new Array(events.length)
  let current = null
  for (let i = 0; i < events.length; i += 1) {
    const ev = events[i]
    if (ev?.event_type === 'state_snapshot') {
      const payload = ev.payload || {}
      const seats = toSeatMap(payload)
      const handID = payload.hand_id || ev.hand_id
      const holes = holeByHand.get(handID) || new Map()
      for (const s of seats) s.hole_cards = holes.get(s.agent_id) || null
      current = {
        table_id: payload.table_id,
        hand_id: handID,
        global_seq: ev.global_seq,
        street: payload.street,
        pot_cc: payload.pot_cc ?? payload.pot ?? 0,
        board_cards: payload.board_cards || payload.community_cards || [],
        current_actor_seat: payload.current_actor_seat,
        seats
      }
    }
    frames[i] = current
  }
  return frames
}

function buildHandResultFrames(events) {
  const frames = new Array(events.length)
  let current = null
  for (let i = 0; i < events.length; i += 1) {
    const ev = events[i]
    if (ev?.event_type === 'hand_settled') {
      current = {
        hand_id: ev.payload?.hand_id || ev.hand_id || '',
        winner_agent_id: ev.payload?.winner || ev.actor_agent_id || '',
        pot_cc: ev.payload?.pot_cc ?? 0,
        global_seq: ev.global_seq
      }
    } else if (ev?.event_type === 'hand_started' && current && ev.global_seq > current.global_seq) {
      current = null
    }
    frames[i] = current
  }
  return frames
}

function buildAgentNameMap(events) {
  const out = new Map()
  for (const ev of events) {
    if (ev.event_type !== 'state_snapshot') continue
    for (const it of ev.payload?.seat_map || []) {
      if (!it?.agent_id) continue
      if (it.agent_name) out.set(it.agent_id, it.agent_name)
    }
  }
  return out
}

function shortID(v, max = 10) {
  if (!v) return '-'
  const s = String(v)
  if (s.length <= max) return s
  return `${s.slice(0, max)}...`
}

function handNoMap(timeline) {
  const out = new Map()
  for (let i = 0; i < (timeline || []).length; i += 1) {
    const h = timeline[i]
    if (h?.hand_id) out.set(h.hand_id, i + 1)
  }
  return out
}

function buildUnifiedFeed(events, index, seatLabelById, agentNameMap, handIndexMap) {
  const seenThought = new Set()
  const merged = []
  const max = Math.min(events.length - 1, index + 8)
  const min = Math.max(0, index - 200)
  for (let i = min; i <= max; i += 1) {
    const ev = events[i]
    if (!ev) continue
    const p = ev.payload || {}
    const seat = p.seat_id ?? null
    const who =
      (seat !== null && seat !== undefined ? seatLabelById[String(seat)] : '') ||
      (ev.actor_agent_id ? agentNameMap.get(ev.actor_agent_id) || ev.actor_agent_id : '') ||
      (seat !== null && seat !== undefined ? `Seat ${seat}` : 'Seat ?')
    const handID = p.hand_id || ev.hand_id || ''
    const base = {
      seq: ev.global_seq,
      hand_id: handID,
      hand_no: handIndexMap.get(handID) || '-',
      street: p.street || '-',
      seat,
      who
    }
    if (ev.event_type === 'action_applied') {
      merged.push({ ...base, type: 'action', action: p.action || ev.event_type, amount_cc: p.amount_cc || 0 })
      if (p.thought_log) {
        const tk = `${ev.global_seq}-${seat ?? '?'}-${p.thought_log}`
        if (!seenThought.has(tk)) {
          seenThought.add(tk)
          merged.push({ ...base, type: 'thought', thought: p.thought_log })
        }
      }
      continue
    }
    if (ev.event_type === 'thought_log' && p.thought_log) {
      const tk = `${ev.global_seq}-${seat ?? '?'}-${p.thought_log}`
      if (!seenThought.has(tk)) {
        seenThought.add(tk)
        merged.push({ ...base, type: 'thought', thought: p.thought_log })
      }
      continue
    }
    if (ev.event_type === 'hand_settled') {
      const winnerAgent = p.winner || ev.actor_agent_id || ''
      merged.push({ ...base, type: 'settled', pot_cc: p.pot_cc || 0, winner_name: agentNameMap.get(winnerAgent) || winnerAgent || '-' })
      continue
    }
    if (ev.event_type === 'street_advanced') merged.push({ ...base, type: 'street', street: p.street || '-' })
  }
  merged.sort((a, b) => b.seq - a.seq)
  return merged.slice(0, 150)
}

async function fetchAllReplay(tableId) {
  const all = []
  let fromSeq = 1
  for (;;) {
    const res = await getTableReplay(tableId, { fromSeq, limit: 500 })
    all.push(...(res.items || []).map(normalizeEvent))
    if (!res.has_more || !res.items?.length) break
    fromSeq = res.next_from_seq || fromSeq + 500
    if (all.length > 10000) break
  }
  return all
}

export default function TableReplay() {
  const { tableId } = useParams()
  const queryClient = useQueryClient()
  const {
    index, playing, speed, handNavOpen, selectedHandId, stateOverride,
    setIndex, togglePlay, setSpeed, toggleHandNav, setSelectedHand, setStateOverride, resetReplayState, pause
  } = useReplayStore()

  useEffect(() => {
    resetReplayState()
  }, [tableId, resetReplayState])

  const replayQuery = useQuery({
    queryKey: ['tableReplay', tableId],
    queryFn: () => fetchAllReplay(tableId),
    enabled: !!tableId,
    staleTime: 1000
  })
  const timelineQuery = useQuery({
    queryKey: ['tableTimeline', tableId],
    queryFn: () => getTableTimeline(tableId),
    enabled: !!tableId,
    staleTime: 1000
  })

  const events = replayQuery.data || []
  const timeline = timelineQuery.data?.items || []

  useEffect(() => {
    if (!playing) return
    const interval = Math.max(80, 550 / speed)
    const id = setInterval(() => {
      setIndex((prev) => {
        if (prev >= events.length - 1) {
          pause()
          return prev
        }
        return prev + 1
      })
    }, interval)
    return () => clearInterval(id)
  }, [playing, speed, events.length, setIndex, pause])

  useEffect(() => {
    if (index > events.length - 1) setIndex(Math.max(0, events.length - 1))
  }, [events.length, index, setIndex])

  const holeByHand = useMemo(() => buildHoleCardsByHand(events), [events])
  const currentEvent = events[index] || null
  const stateFrames = useMemo(() => buildStateFrames(events, holeByHand), [events, holeByHand])
  const handResultFrames = useMemo(() => buildHandResultFrames(events), [events])
  const replayState = useMemo(() => stateOverride || stateFrames[index] || null, [stateOverride, stateFrames, index])
  const handResult = useMemo(() => handResultFrames[index] || null, [handResultFrames, index])
  const agentNameMap = useMemo(() => buildAgentNameMap(events), [events])
  const handIndexMap = useMemo(() => handNoMap(timeline), [timeline])
  const seatLabelById = useMemo(() => {
    const out = {}
    for (const s of replayState?.seats || []) out[String(s.seat_id)] = s.agent_name || s.agent_id || `Seat ${s.seat_id}`
    return out
  }, [replayState])
  const activeHandID = replayState?.hand_id || selectedHandId || ''
  const unifiedFeed = useMemo(
    () => buildUnifiedFeed(events, index, seatLabelById, agentNameMap, handIndexMap),
    [events, index, seatLabelById, agentNameMap, handIndexMap]
  )
  const activeHandIndex = useMemo(() => timeline.findIndex((h) => h.hand_id === activeHandID), [timeline, activeHandID])
  const potRange = useMemo(() => {
    if (!timeline.length) return { min: 0, max: 0 }
    let min = Number.MAX_SAFE_INTEGER
    let max = 0
    for (const h of timeline) {
      const pot = Number(h.pot_cc || 0)
      if (pot < min) min = pot
      if (pot > max) max = pot
    }
    return { min: min === Number.MAX_SAFE_INTEGER ? 0 : min, max }
  }, [timeline])

  const jumpToSeq = async (seq) => {
    try {
      const snap = await queryClient.fetchQuery({
        queryKey: ['tableSnapshot', tableId, seq],
        queryFn: () => getTableSnapshot(tableId, seq),
        staleTime: 1000
      })
      const idx = events.findIndex((ev) => ev.global_seq >= seq)
      const snapshotState = {
        table_id: snap.state?.table_id,
        hand_id: snap.state?.hand_id,
        global_seq: seq,
        street: snap.state?.street,
        pot_cc: snap.state?.pot_cc ?? 0,
        board_cards: snap.state?.board_cards || [],
        current_actor_seat: snap.state?.current_actor_seat,
        seats: toSeatMap(snap.state || {})
      }
      const holes = holeByHand.get(snapshotState.hand_id) || new Map()
      for (const s of snapshotState.seats) s.hole_cards = holes.get(s.agent_id) || null
      setStateOverride(snapshotState)
      setSelectedHand(snapshotState.hand_id || '')
      setIndex(idx >= 0 ? idx : Math.max(0, events.length - 1))
      pause()
    } catch {}
  }

  const statusText = replayQuery.isLoading ? 'Loading replay...' : `event ${Math.min(index + 1, events.length)}/${events.length}`
  const jumpByHandOffset = (offset) => {
    if (!timeline.length) return
    const base = activeHandIndex >= 0 ? activeHandIndex : 0
    const next = Math.max(0, Math.min(timeline.length - 1, base + offset))
    const t = timeline[next]
    if (t?.start_seq) jumpToSeq(t.start_seq)
  }

  return (
    <section className="page replay-page">
      <div className="replay-shell-clean">
        <header className="replay-controls-clean">
          <button className="btn btn-primary" onClick={togglePlay} disabled={!events.length}>{playing ? 'Pause' : 'Play'}</button>
          <button className="btn btn-ghost" onClick={() => setIndex(Math.max(0, index - 1))} disabled={index <= 0}>Prev</button>
          <button className="btn btn-ghost" onClick={() => setIndex(Math.min(events.length - 1, index + 1))} disabled={index >= events.length - 1}>Next</button>
          <label className="replay-speed-label">
            Speed
            <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
              <option value={0.5}>0.5x</option>
              <option value={1}>1x</option>
              <option value={2}>2x</option>
              <option value={4}>4x</option>
            </select>
          </label>
          <span className="replay-status muted">{statusText}</span>
          <span className="replay-table muted">table={tableId}</span>
          <Link className="btn btn-ghost" to="/history">Back to History</Link>
        </header>

        {(replayQuery.isError || timelineQuery.isError) && <div className="replay-error muted">{replayQuery.error?.message || timelineQuery.error?.message || 'replay_load_failed'}</div>}

        <section className="replay-hand-nav">
          <div className="replay-hand-nav-head">
            <div className="replay-timeline-title">Hand Segments</div>
            <div className="replay-hand-stats">
              <span>{`Total ${timeline.length}`}</span>
              <span>{`Current ${activeHandIndex >= 0 ? activeHandIndex + 1 : '-'}`}</span>
              <span>{`Pot ${potRange.min}~${potRange.max}`}</span>
            </div>
            <button className="btn btn-ghost replay-hand-toggle" onClick={toggleHandNav}>{handNavOpen ? 'Collapse' : 'Expand'}</button>
          </div>
          {handNavOpen && (
            <div className="replay-hand-segments">
              {timeline.map((h, i) => (
                <button
                  key={h.hand_id}
                  className={`replay-hand-chip ${activeHandID && activeHandID === h.hand_id ? 'is-active' : ''}`}
                  onClick={() => jumpToSeq(h.start_seq || 1)}
                  title={`Winner: ${agentNameMap.get(h.winner_agent_id) || shortID(h.winner_agent_id, 12)} | Pot: ${h.pot_cc ?? 0} | Street: ${h.street_end || '-'}`}
                >
                  {`H${i + 1}`}
                </button>
              ))}
            </div>
          )}
        </section>

        <div className="replay-main-clean">
          <ReplayTableStage state={replayState} currentEvent={currentEvent?.payload || {}} handResult={handResult} />
          <aside className="replay-side-clean">
            <ReplayEventFeed items={unifiedFeed} activeSeq={currentEvent?.global_seq} onJumpSeq={jumpToSeq} />
          </aside>
        </div>

        <div className="replay-jump-bar">
          <button className="btn btn-ghost" onClick={() => jumpByHandOffset(-1)} disabled={!timeline.length}>Prev Hand</button>
          <button className="btn btn-ghost" onClick={() => jumpByHandOffset(1)} disabled={!timeline.length}>Next Hand</button>
          <span className="muted">{activeHandIndex >= 0 ? `Hand ${activeHandIndex + 1}/${timeline.length}` : `Hand -/${timeline.length}`}</span>
          <button className="btn btn-ghost" onClick={() => jumpToSeq(currentEvent?.global_seq || 1)} disabled={!currentEvent}>Sync To Current Event</button>
        </div>

        <div className="replay-timeline-clean replay-timeline-clean-compact">
          <div className="replay-timeline-title">Hand Details</div>
          <div className="replay-timeline-list replay-timeline-list-compact">
            {timeline.length === 0 && <div className="muted">No timeline</div>}
            {timeline
              .slice(Math.max(0, (activeHandIndex >= 0 ? activeHandIndex : 0) - 3), (activeHandIndex >= 0 ? activeHandIndex : 0) + 4)
              .map((h, i) => (
                <div key={h.hand_id} className={`replay-hand-node replay-hand-node-compact ${activeHandID === h.hand_id ? 'is-active' : ''}`}>
                  <span className="replay-hand-row">
                    <span className="replay-hand-no">{`Hand ${handIndexMap.get(h.hand_id) || i + 1}`}</span>
                    <span className="replay-hand-pot">{`${h.pot_cc ?? 0} CC`}</span>
                  </span>
                  <span className="replay-hand-meta">
                    <span className="replay-hand-winner-name">{`Winner: ${agentNameMap.get(h.winner_agent_id) || shortID(h.winner_agent_id, 12)}`}</span>
                    <span className="replay-hand-street">{`Street: ${h.street_end || '-'}`}</span>
                  </span>
                </div>
              ))}
          </div>
        </div>
      </div>
    </section>
  )
}
