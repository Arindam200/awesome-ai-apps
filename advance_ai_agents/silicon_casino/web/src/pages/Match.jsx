import React, { useEffect, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import ReplayActionTicker from '../components/ReplayActionTicker.jsx'
import ReplayTableStage from '../components/ReplayTableStage.jsx'
import ReplayThoughtTimeline from '../components/ReplayThoughtTimeline.jsx'
import { useSpectatorStore } from '../state/useSpectatorStore.jsx'

export default function Match() {
  const { roomId, tableId } = useParams()
  const { snapshot, lastEvent, eventLogs, thoughtLogs, showdown, status, connect, disconnect, timeLeftMs } =
    useSpectatorStore()

  useEffect(() => {
    if (roomId && tableId) {
      connect({ roomId, tableId })
    }
    return () => disconnect()
  }, [roomId, tableId])

  const liveState = useMemo(() => {
    if (!snapshot) return null
    const seats = (snapshot.seats || []).map((s) => ({
      seat_id: s.seat_id,
      agent_id: s.agent_id || '',
      agent_name: s.agent_name || s.agent_id || '',
      stack: s.stack,
      hole_cards: s.hole_cards || null
    }))
    return {
      table_id: '',
      hand_id: snapshot.hand_id || '',
      street: snapshot.street || '-',
      pot_cc: snapshot.pot ?? 0,
      board_cards: snapshot.community_cards || [],
      current_actor_seat: snapshot.current_actor_seat,
      seats
    }
  }, [snapshot])

  const currentEvent = useMemo(() => ({
    seat_id: lastEvent?.player_seat,
    thought_log: lastEvent?.thought_log || ''
  }), [lastEvent])

  const thoughtItems = useMemo(
    () =>
      thoughtLogs.map((it, i) => ({
        global_seq: thoughtLogs.length - i,
        seat_id: it.seat,
        thought_log: it.text
      })),
    [thoughtLogs]
  )

  const seatAgentLabelById = useMemo(() => {
    const out = {}
    for (const s of liveState?.seats || []) {
      const sid = String(s.seat_id)
      out[sid] = s.agent_name || s.agent_id || 'Unknown Agent'
    }
    return out
  }, [liveState])

  const agentNameById = useMemo(() => {
    const out = {}
    for (const s of liveState?.seats || []) {
      if (!s.agent_id) continue
      out[s.agent_id] = s.agent_name || s.agent_id
    }
    return out
  }, [liveState])

  const actionItems = useMemo(
    () =>
      eventLogs
        .map((it, i) => ({
          global_seq: eventLogs.length - i,
          seat_id: it.seat,
          action: it.action,
          amount_cc: it.amount
        })),
    [eventLogs]
  )

  return (
    <section className="page replay-page">
      <div className="replay-shell-clean">
        <header className="replay-controls-clean">
          <div className="match-title">
            <span>Room</span> <strong>{roomId}</strong>
            <span className="muted"> / Table </span>
            <strong>{tableId || '-'}</strong>
          </div>
          <span className="muted">action timeout: {timeLeftMs != null ? `${Math.ceil(timeLeftMs / 1000)}s` : '-'}</span>
          <div className={`status-pill ${status}`}>{status}</div>
        </header>
        {!tableId && (
          <div className="panel" style={{ marginTop: 10, borderColor: '#36517c' }}>
            <div className="panel-title">Table Required</div>
            <div className="muted">This page now requires a table id in route: /match/:roomId/:tableId</div>
          </div>
        )}
        {!snapshot && (
          <div className="panel" style={{ marginTop: 10, borderColor: '#36517c' }}>
            <div className="panel-title">Table Status</div>
            <div className="muted">No active table snapshot in this room. The match may have ended or both agents have left.</div>
          </div>
        )}

        <div className="replay-main-clean">
          <ReplayTableStage state={liveState} currentEvent={currentEvent} handResult={null} />
          <aside className="replay-side-clean">
            <ReplayThoughtTimeline
              items={thoughtItems}
              activeSeq={thoughtItems[0]?.global_seq}
              seatLabelById={seatAgentLabelById}
              agentNameById={agentNameById}
            />
            <ReplayActionTicker items={actionItems} activeSeq={actionItems[0]?.global_seq} />
            <div className="replay-panel replay-actions">
              <div className="replay-panel-title">Showdown</div>
              <div className="replay-panel-list">
                {showdown.length === 0 && <div className="muted">No showdown yet</div>}
                {showdown.map((s, i) => (
                  <div key={`${s.agent_id}-${i}`} className="replay-log-line">
                    <span className="replay-log-seat">{s.agent_id}</span>
                    <span className="replay-log-text">{(s.hole_cards || []).join(' ') || '-'}</span>
                  </div>
                ))}
              </div>
            </div>
          </aside>
        </div>
      </div>
    </section>
  )
}
