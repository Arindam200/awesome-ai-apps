import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { getAgentProfile } from '../services/api.js'

const PAGE_SIZE = 20

function formatTime(value) {
  if (!value) return 'N/A'
  const ts = new Date(value)
  if (Number.isNaN(ts.getTime())) return 'N/A'
  return ts.toLocaleString()
}

function shortID(v, n = 16) {
  if (!v) return '-'
  return v.length <= n ? v : `${v.slice(0, n)}...`
}

function StatCard({ label, value, className = '' }) {
  return (
    <div className={`agent-profile-stat-card ${className}`}>
      <div className="agent-profile-stat-label">{label}</div>
      <div className="agent-profile-stat-value">{value}</div>
    </div>
  )
}

function ParticipantLinks({ participants }) {
  if (!participants || participants.length === 0) return <span>No seats recorded</span>
  return (
    <>
      {participants.map((p, idx) => (
        <React.Fragment key={`${p.agent_id}-${idx}`}>
          {idx > 0 && <span className="agent-profile-vs">vs</span>}
          <Link to={`/agents/${p.agent_id}`} className="agent-profile-participant-link">
            {p.agent_name || shortID(p.agent_id, 10)}
          </Link>
        </React.Fragment>
      ))}
    </>
  )
}

export default function AgentProfile() {
  const { agentId = '' } = useParams()
  const [page, setPage] = React.useState(1)

  const offset = (page - 1) * PAGE_SIZE
  const query = useQuery({
    queryKey: ['agentProfile', agentId, page],
    queryFn: () => getAgentProfile(agentId, { limit: PAGE_SIZE, offset }),
    enabled: !!agentId,
    staleTime: 5000
  })

  React.useEffect(() => {
    setPage(1)
  }, [agentId])

  const data = query.data
  const agent = data?.agent || {}
  const stats30d = data?.stats_30d || {}
  const statsAll = data?.stats_all || {}
  const tables = data?.tables || {}
  const items = tables.items || []
  const total = Number(tables.total || 0)
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  React.useEffect(() => {
    if (page > totalPages) setPage(totalPages)
  }, [page, totalPages])

  return (
    <section className="page agent-profile-page">
      <div className="agent-profile-hero">
        <div className="hero-kicker">
          <span className="cursor-blink">_</span>Agent Intelligence
        </div>
        <h1 className="agent-profile-title">
          AGENT
          <br />
          <span className="hero-title-fade">PROFILE</span>
        </h1>
        <p className="agent-profile-sub">
          Deep dive into a single agent with recent and all-time performance,
          plus replay-ready table history.
        </p>
      </div>

      {query.isError && (
        <div className="panel placeholder cyber-border corner-accent">
          <div className="panel-title">Profile Unavailable</div>
          <p className="muted">{query.error?.message || 'agent_profile_unavailable'}</p>
        </div>
      )}

      {query.isLoading && (
        <div className="agent-profile-loading-grid">
          <div className="agent-profile-skeleton cyber-border corner-accent" />
          <div className="agent-profile-skeleton cyber-border corner-accent" />
          <div className="agent-profile-skeleton cyber-border corner-accent" />
        </div>
      )}

      {!query.isLoading && !query.isError && (
        <>
          <div className="agent-profile-identity cyber-border corner-accent">
            <div className="panel-title">Identity</div>
            <div className="agent-profile-identity-row">
              <div className="agent-profile-agent-name">{agent.name || shortID(agent.agent_id, 18)}</div>
              <div className="agent-profile-agent-id">{agent.agent_id || '-'}</div>
            </div>
            <div className="agent-profile-meta-row">
              <span className="agent-profile-chip">Joined {formatTime(agent.created_at)}</span>
              <span className="agent-profile-chip">{total} Tables</span>
            </div>
          </div>

          <div className="agent-profile-stats-grid">
            <div className="agent-profile-stats-section cyber-border corner-accent">
              <div className="panel-title">30D Snapshot</div>
              <div className="agent-profile-stat-grid">
                <StatCard label="Score" value={Number(stats30d.score || 0).toFixed(2)} className="is-emphasis" />
                <StatCard label="BB/100" value={Number(stats30d.bb_per_100 || 0).toFixed(2)} />
                <StatCard label="Net CC" value={Number(stats30d.net_cc_from_play || 0).toLocaleString()} className={Number(stats30d.net_cc_from_play || 0) >= 0 ? 'is-pos' : 'is-neg'} />
                <StatCard label="Hands" value={Number(stats30d.hands_played || 0).toLocaleString()} />
                <StatCard label="Win Rate" value={`${(Number(stats30d.win_rate || 0) * 100).toFixed(1)}%`} />
                <StatCard label="Last Active" value={formatTime(stats30d.last_active_at)} />
              </div>
            </div>

            <div className="agent-profile-stats-section cyber-border corner-accent">
              <div className="panel-title">All-Time Snapshot</div>
              <div className="agent-profile-stat-grid">
                <StatCard label="Score" value={Number(statsAll.score || 0).toFixed(2)} className="is-emphasis" />
                <StatCard label="BB/100" value={Number(statsAll.bb_per_100 || 0).toFixed(2)} />
                <StatCard label="Net CC" value={Number(statsAll.net_cc_from_play || 0).toLocaleString()} className={Number(statsAll.net_cc_from_play || 0) >= 0 ? 'is-pos' : 'is-neg'} />
                <StatCard label="Hands" value={Number(statsAll.hands_played || 0).toLocaleString()} />
                <StatCard label="Win Rate" value={`${(Number(statsAll.win_rate || 0) * 100).toFixed(1)}%`} />
                <StatCard label="Last Active" value={formatTime(statsAll.last_active_at)} />
              </div>
            </div>
          </div>

          <div className="agent-profile-tables cyber-border corner-accent">
            <div className="agent-profile-tables-head">
              <div className="panel-title">Recent Tables</div>
              <div className="muted">{total} total</div>
            </div>

            {items.length === 0 && <div className="muted">No table history for this agent.</div>}

            {items.map((it) => (
              <article key={it.table_id} className="agent-profile-table-row">
                <div className="agent-profile-table-main">
                  <div className="agent-profile-table-top">
                    <span className="agent-profile-room-chip">{it.room_name || it.room_id || 'Unknown Room'}</span>
                    <span className="agent-profile-status">{it.status || 'unknown'}</span>
                  </div>
                  <div className="agent-profile-participants">
                    <ParticipantLinks participants={it.participants} />
                  </div>
                  <div className="agent-profile-table-meta">
                    <span className="agent-profile-chip">Blinds {it.small_blind_cc}/{it.big_blind_cc}</span>
                    <span className="agent-profile-chip">Hands {Number(it.hands_played || 0)}</span>
                    <span className="agent-profile-chip">Table {shortID(it.table_id, 18)}</span>
                    <span className="agent-profile-chip">Last End {formatTime(it.last_hand_ended_at)}</span>
                  </div>
                </div>
                <div className="agent-profile-table-cta">
                  <Link className="btn btn-ghost" to={`/replay/${it.table_id}`}>Replay</Link>
                </div>
              </article>
            ))}

            {total > 0 && (
              <div className="agent-profile-pagination">
                <button
                  type="button"
                  className="agent-profile-page-btn"
                  disabled={page === 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Prev
                </button>
                <span className="agent-profile-page-indicator">Page {page} / {totalPages}</span>
                <button
                  type="button"
                  className="agent-profile-page-btn"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  )
}
