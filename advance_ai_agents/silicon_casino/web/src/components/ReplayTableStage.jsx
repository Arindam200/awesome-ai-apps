import React, { useMemo } from 'react'
import { avatarBySeat, chipByName } from '../assets/replay-pixel/index.js'
import { cardBack, cardImageUrl } from '../lib/cards.js'

const BACK_CARD = cardBack(1)
const LEFT_SEAT_CHIPS = [['red', 1], ['red', 5], ['red', 25], ['red', 100]]
const RIGHT_SEAT_CHIPS = [['blue', 1], ['blue', 5], ['blue', 25], ['blue', 100]]
const POT_CHIPS = [['white', 100], ['purple', 100], ['green', 25], ['pink', 25], ['black', 5], ['gold', 5], ['white', 1], ['purple', 1]]

function boardCards(cards) {
  const arr = [...(cards || [])]
  while (arr.length < 5) arr.push(null)
  return arr.slice(0, 5)
}

function pickSeatCards(seat) {
  const cards = seat?.hole_cards || []
  if (cards.length >= 2) {
    return [cardImageUrl(cards[0]), cardImageUrl(cards[1])]
  }
  return [BACK_CARD, BACK_CARD]
}

const ChipPile = React.memo(function ChipPile({ chips, className }) {
  return (
    <div className={className}>
      {chips.map(([colorName, unitValue], i) => (
        <img
          key={`${colorName}-${unitValue}-${i}`}
          src={chipByName(colorName, unitValue)}
          alt="chip"
          className="replay-chip-sprite"
        />
      ))}
    </div>
  )
})

function ReplayTableStage({ state, currentEvent, handResult, compact = false }) {
  const seats = useMemo(() => {
    const items = [...(state?.seats || [])]
    items.sort((a, b) => (a.seat_id ?? 0) - (b.seat_id ?? 0))
    return items.slice(0, 2)
  }, [state])

  const left = seats[0] || { seat_id: 0 }
  const right = seats[1] || { seat_id: 1 }
  const activeSeat = state?.current_actor_seat
  const board = boardCards(state?.board_cards)
  const leftCards = pickSeatCards(left)
  const rightCards = pickSeatCards(right)
  const winnerAgentID = handResult?.winner_agent_id || ''
  const leftWon = !!winnerAgentID && left.agent_id === winnerAgentID
  const rightWon = !!winnerAgentID && right.agent_id === winnerAgentID

  const thoughtSeat = currentEvent?.seat_id
  const thoughtText = currentEvent?.thought_log || ''
  const leftOccupied = !!left.agent_id
  const rightOccupied = !!right.agent_id
  const leftName = leftOccupied ? (left.agent_name || `Seat ${left.seat_id}`) : `Seat ${left.seat_id} (waiting)`
  const rightName = rightOccupied ? (right.agent_name || `Seat ${right.seat_id}`) : `Seat ${right.seat_id} (waiting)`
  const leftID = leftOccupied ? left.agent_id : '-'
  const rightID = rightOccupied ? right.agent_id : '-'

  return (
    <div className={`replay-stage ${compact ? 'replay-stage-compact' : ''}`}>
      <div className="replay-felt" />

      <div className={`replay-seat replay-seat-left ${activeSeat === left.seat_id ? 'is-active' : ''}`}>
        <img className="replay-avatar" src={avatarBySeat(left.seat_id)} alt="left avatar" />
        {leftWon && (
          <div className="replay-seat-win-toast" key={`winner-left-${handResult?.global_seq || handResult?.hand_id || winnerAgentID}`}>
            <span className="replay-seat-win-crown" aria-hidden="true">♛</span>
            <span>{`Winner +${handResult?.pot_cc ?? 0}`}</span>
          </div>
        )}
        <div className="replay-seat-meta">
          <div className="replay-seat-name">{leftName}</div>
          <div className="replay-seat-id">{leftID}</div>
          <div className="replay-seat-stack">Stack: {leftOccupied ? (left.stack ?? '-') : '-'}</div>
        </div>
        {leftOccupied && <ChipPile className="replay-seat-chips" chips={LEFT_SEAT_CHIPS} />}
        <div className="replay-hole-row">
          {leftOccupied ? (
            <>
              <img src={leftCards[0]} alt="left card 1" className="replay-card replay-card-hole" />
              <img src={leftCards[1]} alt="left card 2" className="replay-card replay-card-hole" />
            </>
          ) : (
            <div className="muted">Waiting for agent...</div>
          )}
        </div>
        {leftOccupied && thoughtText && thoughtSeat === left.seat_id && <div className="replay-thought left">{thoughtText}</div>}
      </div>

      <div className={`replay-seat replay-seat-right ${activeSeat === right.seat_id ? 'is-active' : ''}`}>
        <img className="replay-avatar" src={avatarBySeat(right.seat_id || 1)} alt="right avatar" />
        {rightWon && (
          <div className="replay-seat-win-toast" key={`winner-right-${handResult?.global_seq || handResult?.hand_id || winnerAgentID}`}>
            <span className="replay-seat-win-crown" aria-hidden="true">♛</span>
            <span>{`Winner +${handResult?.pot_cc ?? 0}`}</span>
          </div>
        )}
        <div className="replay-seat-meta">
          <div className="replay-seat-name">{rightName}</div>
          <div className="replay-seat-id">{rightID}</div>
          <div className="replay-seat-stack">Stack: {rightOccupied ? (right.stack ?? '-') : '-'}</div>
        </div>
        {rightOccupied && <ChipPile className="replay-seat-chips" chips={RIGHT_SEAT_CHIPS} />}
        <div className="replay-hole-row">
          {rightOccupied ? (
            <>
              <img src={rightCards[0]} alt="right card 1" className="replay-card replay-card-hole" />
              <img src={rightCards[1]} alt="right card 2" className="replay-card replay-card-hole" />
            </>
          ) : (
            <div className="muted">Waiting for agent...</div>
          )}
        </div>
        {rightOccupied && thoughtText && thoughtSeat === right.seat_id && <div className="replay-thought right">{thoughtText}</div>}
      </div>

      <div className="replay-board-row">
        {board.map((card, idx) => (
          <img
            key={`board-${idx}-${card || 'empty'}`}
            className={`replay-card replay-card-board ${card ? '' : 'is-empty'}`}
            src={card ? cardImageUrl(card) : BACK_CARD}
            alt={card || 'board empty'}
          />
        ))}
      </div>

      <div className="replay-pot-row">
        <span className="replay-chip-badge">Pot: {state?.pot_cc ?? 0}</span>
        <span className="replay-chip-badge">Street: {state?.street || '-'}</span>
      </div>

      <ChipPile className="replay-chip-pile replay-chip-pile-pot" chips={POT_CHIPS} />
    </div>
  )
}

export default React.memo(ReplayTableStage)
