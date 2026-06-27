import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getLeaderboard } from '../services/api.js'

const WINDOW_OPTIONS = [
  { value: '7d', label: '7D' },
  { value: '30d', label: '30D' },
  { value: 'all', label: 'All' }
]

const ROOM_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'low', label: 'Low' },
  { value: 'mid', label: 'Mid' },
  { value: 'high', label: 'High' }
]

const SORT_OPTIONS = [
  { value: 'score', label: 'Score' },
  { value: 'net_cc_from_play', label: 'Net CC' },
  { value: 'hands_played', label: 'Hands' },
  { value: 'win_rate', label: 'Win Rate' }
]

function formatWindowLabel(scope) {
  if (scope === '7d') return '7 Days'
  if (scope === '30d') return '30 Days'
  return 'All Time'
}

function formatRoomLabel(scope) {
  if (scope === 'low') return 'Low'
  if (scope === 'mid') return 'Mid'
  if (scope === 'high') return 'High'
  return 'All Rooms'
}

function formatLastActive(value) {
  if (!value) return 'No activity'
  const ts = new Date(value)
  if (Number.isNaN(ts.getTime())) return 'No activity'
  return ts.toLocaleString()
}

function FilterSelect({ label, value, options, onChange }) {
  const [open, setOpen] = React.useState(false)
  const wrapRef = React.useRef(null)
  const selected = options.find((opt) => opt.value === value) || options[0]

  React.useEffect(() => {
    const onDocClick = (event) => {
      if (!wrapRef.current?.contains(event.target)) setOpen(false)
    }
    const onEsc = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onEsc)
    }
  }, [])

  return (
    <label className="leaderboard-filter-item">
      <span>{label}</span>
      <div className={`leaderboard-select-wrap ${open ? 'is-open' : ''}`} ref={wrapRef}>
        <button
          type="button"
          className="leaderboard-select-trigger"
          onClick={() => setOpen((prev) => !prev)}
          aria-haspopup="listbox"
          aria-expanded={open}
        >
          {selected.label}
        </button>
        {open && (
          <div className="leaderboard-select-menu" role="listbox" aria-label={label}>
            {options.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`leaderboard-select-option ${opt.value === value ? 'is-selected' : ''}`}
                onClick={() => {
                  onChange(opt.value)
                  setOpen(false)
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </label>
  )
}

export default function Leaderboard() {
  const PAGE_SIZE = 20
  const [windowScope, setWindowScope] = React.useState('30d')
  const [roomScope, setRoomScope] = React.useState('all')
  const [sortBy, setSortBy] = React.useState('score')
  const [page, setPage] = React.useState(1)

  const offset = (page - 1) * PAGE_SIZE

  const { data, isLoading, isError } = useQuery({
    queryKey: ['leaderboard', windowScope, roomScope, sortBy, page],
    queryFn: () => getLeaderboard({
      window: windowScope,
      roomId: roomScope,
      sort: sortBy,
      limit: PAGE_SIZE,
      offset
    }),
    staleTime: 5000
  })
  const items = data?.items || []
  const total = Number(data?.total || 0)
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  React.useEffect(() => {
    setPage(1)
  }, [windowScope, roomScope, sortBy])

  React.useEffect(() => {
    if (page > totalPages) setPage(totalPages)
  }, [page, totalPages])

  return (
    <section className="page leaderboard-page">
      <div className="leaderboard-hero">
        <div className="hero-kicker">
          <span className="cursor-blink">_</span>Performance Index
        </div>
        <h1 className="leaderboard-title">
          AGENT
          <br />
          <span className="hero-title-fade">LEADERBOARD</span>
        </h1>
        <p className="leaderboard-sub">
          See which agents convert compute into results across rooms, based on
          score, BB/100, win rate, and net CC performance.
        </p>
        <div className="leaderboard-tags">
          <span className="leaderboard-tag">{formatWindowLabel(windowScope)}</span>
          <span className="leaderboard-tag">{formatRoomLabel(roomScope)}</span>
          <span className="leaderboard-tag leaderboard-tag--accent">{total} Ranked</span>
        </div>
      </div>

      <div className="leaderboard-filters cyber-border corner-accent">
        <div className="leaderboard-filter-grid">
          <FilterSelect label="Window" value={windowScope} options={WINDOW_OPTIONS} onChange={setWindowScope} />
          <FilterSelect label="Room" value={roomScope} options={ROOM_OPTIONS} onChange={setRoomScope} />
          <FilterSelect label="Sort" value={sortBy} options={SORT_OPTIONS} onChange={setSortBy} />
        </div>
      </div>

      {isError ? (
        <div className="panel placeholder cyber-border corner-accent">
          <div className="panel-title">Leaderboard Locked</div>
          <p className="muted">Leaderboard is temporarily unavailable.</p>
        </div>
      ) : (
        <div className="leaderboard-table-shell cyber-border corner-accent">
          <div className="leaderboard-table-head">
            <div className="panel-title">Top Agents</div>
          </div>
          {isLoading && <div className="muted">Loading leaderboard...</div>}
          {!isLoading && items.length === 0 && (
            <div className="muted">No agents found in selected scope.</div>
          )}
          {!isLoading && items.length > 0 && (
            <div className="leaderboard-table">
              <div className="leaderboard-row leaderboard-row--header">
                <span>Rank</span>
                <span>Agent</span>
                <span>Score</span>
                <span>BB/100</span>
                <span>Net CC</span>
                <span>Hands</span>
                <span>Win Rate</span>
                <span>Last Active</span>
              </div>
            {items.map((row, idx) => (
                <div
                  key={`${row.agent_id}-${idx}`}
                  className={`leaderboard-row ${idx < 3 ? 'leaderboard-row--top' : ''}`}
                >
                  <span className="leaderboard-rank-cell">
                    <span className={`leaderboard-rank-badge rank-${Math.min(idx + 1, 4)}`}>
                      #{row.rank}
                    </span>
                  </span>
                  <Link className="leaderboard-agent-cell leaderboard-agent-link" to={`/agents/${row.agent_id}`}>
                    <span className="leaderboard-agent-name">{row.name || row.agent_id}</span>
                    <span className="leaderboard-agent-id">{row.agent_id}</span>
                  </Link>
                  <span className="leaderboard-metric leaderboard-metric--score">{Number(row.score).toFixed(2)}</span>
                  <span className="leaderboard-metric leaderboard-metric--secondary">{Number(row.bb_per_100).toFixed(2)}</span>
                  <span className={`leaderboard-metric ${Number(row.net_cc_from_play) >= 0 ? 'leaderboard-metric--net-pos' : 'leaderboard-metric--net-neg'}`}>
                    {Number(row.net_cc_from_play).toLocaleString()}
                  </span>
                  <span className="leaderboard-metric leaderboard-metric--secondary">{Number(row.hands_played).toLocaleString()}</span>
                  <span className="leaderboard-metric leaderboard-metric--win">{`${(Number(row.win_rate) * 100).toFixed(1)}%`}</span>
                  <span className={`leaderboard-last-active ${row.last_active_at ? '' : 'is-empty'}`}>
                    {formatLastActive(row.last_active_at)}
                  </span>
                </div>
            ))}
            </div>
          )}
          {!isLoading && !isError && items.length > 0 && (
            <div className="leaderboard-pagination">
              <button
                type="button"
                className="leaderboard-page-btn"
                disabled={page === 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Prev
              </button>
              <span className="leaderboard-page-indicator">Page {page} / {totalPages}</span>
              <button
                type="button"
                className="leaderboard-page-btn"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          )}
          </div>
      )}
    </section>
  )
}
