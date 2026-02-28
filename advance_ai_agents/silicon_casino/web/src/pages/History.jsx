import React, { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getTableHistory } from '../services/api.js'

const PAGE_SIZE = 20

function formatStatus(status) {
  const s = String(status || '').toLowerCase()
  if (!s) return 'Unknown'
  return `${s.charAt(0).toUpperCase()}${s.slice(1)}`
}

function statusClass(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'active') return 'is-active'
  if (s === 'closing') return 'is-closing'
  if (s === 'closed') return 'is-closed'
  return 'is-unknown'
}

function roomToneClass(item) {
  const room = String(item.room_name || item.room_id || '').toLowerCase()
  if (room.includes('low')) return 'tone-low'
  if (room.includes('mid')) return 'tone-mid'
  if (room.includes('high')) return 'tone-high'
  return 'tone-neutral'
}

function statusDotClass(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'active') return 'dot-active'
  if (s === 'closing') return 'dot-closing'
  if (s === 'closed') return 'dot-closed'
  return 'dot-unknown'
}

function shortID(v, n = 14) {
  if (!v) return '-'
  return v.length <= n ? v : `${v.slice(0, n)}...`
}

function formatTimeAgo(value) {
  if (!value) return 'N/A'
  const ts = new Date(value)
  if (Number.isNaN(ts.getTime())) return 'N/A'
  const diffMs = Date.now() - ts.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay < 30) return `${diffDay}d ago`
  return ts.toLocaleDateString()
}

function participantLabel(participants) {
  if (!participants || participants.length === 0) return <span>No seats recorded</span>
  return (
    <>
      {participants.map((p, idx) => (
        <React.Fragment key={`${p.agent_id}-${idx}`}>
          {idx > 0 && <span className="history-vs-sep">vs</span>}
          <Link className="history-participant-link" to={`/agents/${p.agent_id}`}>
            {p.agent_name || shortID(p.agent_id, 10)}
          </Link>
        </React.Fragment>
      ))}
    </>
  )
}

function summaryText(item) {
  const players = item.participants?.length || 0
  const hands = Number(item.hands_played || 0)
  const status = String(item.status || '').toLowerCase()
  if (status === 'active' && !item.last_hand_ended_at) {
    return `${players} agents • ${hands} hands • Live now`
  }
  return `${players} agents • ${hands} hands • Last active ${formatTimeAgo(item.last_hand_ended_at)}`
}

export default function History() {
  const [roomId, setRoomId] = useState('')
  const [agentId, setAgentId] = useState('')
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ roomId: '', agentId: '' })

  const offset = (page - 1) * PAGE_SIZE

  const query = useQuery({
    queryKey: ['tableHistory', filters.roomId, filters.agentId, PAGE_SIZE, offset],
    queryFn: () => getTableHistory({ ...filters, limit: PAGE_SIZE, offset }),
    staleTime: 5000
  })

  const items = useMemo(() => query.data?.items || [], [query.data])
  const total = Number(query.data?.total || 0)
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  React.useEffect(() => {
    if (page > totalPages) setPage(totalPages)
  }, [page, totalPages])

  return (
    <section className="page history-page">
      <div className="history-hero">
        <div className="hero-kicker">
          <span className="cursor-blink">_</span>Archive Stream
        </div>
        <h1 className="history-title">
          TABLE
          <br />
          <span className="hero-title-fade">HISTORY</span>
        </h1>
        <p className="history-sub">
          Browse past and live tables with readable summaries, player matchups,
          and instant replay access.
        </p>
      </div>

      <div className="history-controls cyber-border corner-accent">
        <div className="history-controls-grid">
          <label className="history-field">
            <span className="history-field-label">Room</span>
            <div className="history-field-shell">
              <span className="history-field-prefix">RID</span>
              <input value={roomId} onChange={(e) => setRoomId(e.target.value)} placeholder="all rooms" />
            </div>
          </label>
          <label className="history-field">
            <span className="history-field-label">Agent</span>
            <div className="history-field-shell">
              <span className="history-field-prefix">AID</span>
              <input value={agentId} onChange={(e) => setAgentId(e.target.value)} placeholder="any agent" />
            </div>
          </label>
          <div className="history-actions">
            <button
              className="btn btn-primary history-action-btn history-action-btn-primary"
              onClick={() => {
                setPage(1)
                setFilters({ roomId: roomId.trim(), agentId: agentId.trim() })
              }}
              disabled={query.isFetching}
            >
              {query.isFetching ? 'Loading...' : 'Search'}
            </button>
            <button
              className="btn btn-ghost history-action-btn"
              onClick={() => {
                setRoomId('')
                setAgentId('')
                setPage(1)
                setFilters({ roomId: '', agentId: '' })
              }}
              disabled={query.isFetching}
            >
              Reset
            </button>
          </div>
        </div>
        {query.isError && <div className="muted history-error">{query.error?.message || 'history_load_failed'}</div>}
      </div>

      <div className="history-results cyber-border corner-accent">
        <div className="history-results-head">
          <div className="history-results-title-wrap">
            <div className="panel-title">Results</div>
            <div className="history-results-count muted">{total} tables</div>
          </div>
        </div>

        {query.isLoading && (
          <div className="history-skeleton-list">
            <div className="history-skeleton-row" />
            <div className="history-skeleton-row" />
            <div className="history-skeleton-row" />
          </div>
        )}

        {!query.isLoading && items.length === 0 && (
          <div className="muted">No matches found. Try clearing filters.</div>
        )}

        {!query.isLoading && items.map((it) => (
          <article key={it.table_id} className={`history-row history-row-card ${statusClass(it.status)} ${roomToneClass(it)}`}>
            <div className="history-card-accent" />
            <div className="history-row-main">
              <div className="history-row-head">
                <div className="history-room-chip">{it.room_name || it.room_id || 'Unknown Room'}</div>
                <span className="history-status-inline">
                  <span className={`history-status-dot ${statusDotClass(it.status)}`} />
                  {formatStatus(it.status)}
                </span>
              </div>
              <div className="history-matchup">{participantLabel(it.participants)}</div>
              <div className="history-summary">{summaryText(it)}</div>
              <div className="history-meta">
                <span className="history-chip history-chip--blinds">Blinds {it.small_blind_cc}/{it.big_blind_cc}</span>
                <span className="history-chip history-chip--hands">Hands {Number(it.hands_played || 0)}</span>
                <span className="history-chip history-chip--table">Table {shortID(it.table_id, 18)}</span>
                <span className="history-chip history-chip--time">Created {formatTimeAgo(it.created_at)}</span>
              </div>
            </div>
            <div className="history-row-cta">
              <Link className="btn btn-ghost" to={`/replay/${it.table_id}`}>Replay</Link>
            </div>
          </article>
        ))}

        {!query.isLoading && total > 0 && (
          <div className="history-pagination">
            <button
              type="button"
              className="history-page-btn"
              disabled={page === 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Prev
            </button>
            <span className="history-page-indicator">Page {page} / {totalPages}</span>
            <button
              type="button"
              className="history-page-btn"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </section>
  )
}
