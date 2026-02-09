import React, { useMemo } from 'react'

export default function TableHUD({ snapshot, timeLeftMs }) {
  const community = useMemo(() => (snapshot?.community_cards || []).join(' '), [snapshot])
  const opp = snapshot?.opponents?.[0]
  const timeLeft = timeLeftMs != null ? Math.ceil(timeLeftMs / 1000) : null

  return (
    <div className="hud">
      <div className="hud-section">
        <div className="hud-title">Table</div>
        <div className="hud-line">Game: {snapshot?.game_id || '-'}</div>
        <div className="hud-line">Hand: {snapshot?.hand_id || '-'}</div>
        <div className="hud-line">Street: {snapshot?.street || '-'}</div>
        <div className="hud-line">Pot: {snapshot?.pot ?? '-'}</div>
        <div className="hud-line">Community: {community || '-'}</div>
        <div className="hud-line">Min Raise: {snapshot?.min_raise ?? '-'}</div>
        <div className="hud-line">Current Bet: {snapshot?.current_bet ?? '-'}</div>
        <div className="hud-line">Call Amount: {snapshot?.call_amount ?? '-'}</div>
        <div className="hud-line">Actor Seat: {snapshot?.current_actor_seat ?? '-'}</div>
        <div className="hud-line">Action Timeout: {timeLeft != null ? `${timeLeft}s` : '-'}</div>
      </div>
      <div className="hud-section">
        <div className="hud-title">Players</div>
        <div className="hud-line">Me Balance: {snapshot?.my_balance ?? '-'}</div>
        <div className="hud-line">Opponent: {opp?.name || '-'}</div>
        <div className="hud-line">Seat: {opp?.seat ?? '-'}</div>
        <div className="hud-line">Stack: {opp?.stack ?? '-'}</div>
        <div className="hud-line">Last Action: {opp?.action ?? '-'}</div>
      </div>
    </div>
  )
}
