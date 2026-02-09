import React from 'react'

export default function MetricStrip({ roomsCount }) {
  return (
    <div className="metric-strip">
      <div className="metric">
        <div className="metric-label">Rooms</div>
        <div className="metric-value">{roomsCount ?? '-'}</div>
      </div>
      <div className="metric">
        <div className="metric-label">Active Matches</div>
        <div className="metric-value muted">Data locked</div>
      </div>
      <div className="metric">
        <div className="metric-label">Total CC Exchange</div>
        <div className="metric-value muted">Data locked</div>
      </div>
    </div>
  )
}
