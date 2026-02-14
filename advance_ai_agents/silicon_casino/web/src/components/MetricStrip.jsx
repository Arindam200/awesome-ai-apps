import React from 'react'

const ServerIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
    <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
    <line x1="6" y1="6" x2="6.01" y2="6"></line>
    <line x1="6" y1="18" x2="6.01" y2="18"></line>
  </svg>
)

const CrosshairIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"></circle>
    <line x1="22" y1="12" x2="18" y2="12"></line>
    <line x1="6" y1="12" x2="2" y2="12"></line>
    <line x1="12" y1="6" x2="12" y2="2"></line>
    <line x1="12" y1="22" x2="12" y2="18"></line>
  </svg>
)

const CoinsIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="8" cy="8" r="6"></circle>
    <path d="M18.09 10.37A6 6 0 1 1 10.34 18"></path>
    <path d="M7 6h1v4"></path>
    <path d="m16.71 13.88.7.71-2.82 2.82"></path>
  </svg>
)

function MetricCard({ label, value, icon: Icon, status, statusColor }) {
  return (
    <div className="metric cyber-border">
      <div className="metric-bg-icon">
        <Icon />
      </div>
      <div className="metric-label">{label}</div>
      <div className="metric-value">
        <span className="metric-accent">{value}</span>
        <span className={`metric-badge metric-badge-${statusColor}`}>{status}</span>
      </div>
    </div>
  )
}

export default function MetricStrip({ roomsCount }) {
  return (
    <div className="metric-strip">
      <MetricCard
        label="Rooms"
        value={roomsCount ?? '—'}
        icon={ServerIcon}
        status={roomsCount != null ? 'LIVE' : 'OFFLINE'}
        statusColor={roomsCount != null ? 'green' : 'gray'}
      />
      <MetricCard
        label="Active Matches"
        value="—"
        icon={CrosshairIcon}
        status="PENDING"
        statusColor="amber"
      />
      <MetricCard
        label="Total CC Exchange"
        value="—"
        icon={CoinsIcon}
        status="PENDING"
        statusColor="amber"
      />
    </div>
  )
}
