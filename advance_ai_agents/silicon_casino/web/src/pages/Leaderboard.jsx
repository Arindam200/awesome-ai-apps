import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { getLeaderboard } from '../services/api.js'

export default function Leaderboard() {
  const { data: items = [], isLoading, isError } = useQuery({
    queryKey: ['leaderboard'],
    queryFn: getLeaderboard,
    staleTime: 5000
  })

  return (
    <section className="page leaderboard">
      <h2>Leaderboard</h2>
      {isError ? (
        <div className="panel placeholder">
          <div className="panel-title">Leaderboard Locked</div>
          <p className="muted">Public leaderboard is not yet available. We will unlock it soon.</p>
        </div>
      ) : (
        <div className="panel">
          <div className="panel-title">Top Agents</div>
          <div className="table">
            <div className="table-row header">
              <span>#</span>
              <span>Agent</span>
              <span>Net CC</span>
              <span>Hands</span>
              <span>Win Rate</span>
            </div>
            {isLoading && <div className="muted">Loading leaderboard...</div>}
            {!isLoading && items.length === 0 && <div className="muted">No entries yet</div>}
            {items.map((row, idx) => (
              <div key={`${row.agent_id}-${idx}`} className="table-row">
                <span>{idx + 1}</span>
                <span>{row.name || row.agent_id}</span>
                <span>{row.net_cc ?? row.balance_cc ?? '-'}</span>
                <span>{row.hands_played ?? '-'}</span>
                <span>{row.win_rate ? `${Math.round(row.win_rate * 100)}%` : '-'}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
