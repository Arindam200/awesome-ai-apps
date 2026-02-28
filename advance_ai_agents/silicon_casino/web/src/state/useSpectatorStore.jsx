import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { SpectateSSE } from '../services/sse.js'

const SpectatorContext = createContext(null)

const MAX_EVENTS = 120
const MAX_THOUGHTS = 60

const demoCards = ['As', 'Kd', 'Qh', 'Jh', 'Th', '9c', '8d']
const demoAgents = ['DeepSeek_V3', 'BotA', 'Nova-1', 'Echo']

function createDemoSnapshot(roomId) {
  const hand = Math.floor(Math.random() * 900 + 100)
  const pot = Math.floor(Math.random() * 12000 + 200)
  const communityCount = Math.floor(Math.random() * 5)
  const community = demoCards.slice(0, communityCount)
  const opp = demoAgents[Math.floor(Math.random() * demoAgents.length)]
  return {
    type: 'state_update',
    game_id: `room_${roomId}`,
    hand_id: `hand_${hand}`,
    community_cards: community,
    pot,
    min_raise: 200,
    current_bet: Math.floor(pot / 10),
    call_amount: Math.floor(pot / 20),
    my_balance: Math.floor(Math.random() * 100000 + 60000),
    opponents: [{ seat: 1, name: opp, stack: Math.floor(Math.random() * 100000 + 60000), action: 'check' }],
    action_timeout_ms: 5000,
    street: ['preflop', 'flop', 'turn', 'river'][communityCount] || 'preflop',
    current_actor_seat: Math.round(Math.random())
  }
}

function createDemoEvent() {
  const action = ['check', 'call', 'raise', 'fold'][Math.floor(Math.random() * 4)]
  return {
    type: 'event_log',
    player_seat: Math.round(Math.random()),
    action,
    amount: action === 'raise' ? Math.floor(Math.random() * 1200 + 200) : 0,
    thought_log: Math.random() > 0.4 ? 'Win rate 62%, push edge' : '',
    event: 'action'
  }
}

export function SpectatorProvider({ children }) {
  const [status, setStatus] = useState('disconnected')
  const [snapshot, setSnapshot] = useState(null)
  const [eventLogs, setEventLogs] = useState([])
  const [thoughtLogs, setThoughtLogs] = useState([])
  const [lastEvent, setLastEvent] = useState(null)
  const [showdown, setShowdown] = useState([])
  const [roomId, setRoomId] = useState('')
  const [actionDeadline, setActionDeadline] = useState(null)
  const [timeLeftMs, setTimeLeftMs] = useState(null)
  const [disconnectedAgentId, setDisconnectedAgentId] = useState('')
  const demoTimerRef = useRef(null)
  const sseRef = useRef(null)
  const disconnectedAgentIdRef = useRef('')

  const demoMode = useMemo(() => new URLSearchParams(window.location.search).get('demo') === '1', [])

  const setDisconnectedAgent = (agentId) => {
    disconnectedAgentIdRef.current = agentId || ''
    setDisconnectedAgentId(agentId || '')
  }

  const clearLiveState = () => {
    setSnapshot(null)
    setLastEvent(null)
    setShowdown([])
    setActionDeadline(null)
    setTimeLeftMs(null)
    setDisconnectedAgent('')
  }

  const clearLivePanels = () => {
    setEventLogs([])
    setThoughtLogs([])
    setShowdown([])
  }

  const handleStatus = (nextStatus) => {
    setStatus(nextStatus)
    if (nextStatus === 'reconnecting' || nextStatus === 'disconnected') {
      clearLiveState()
    }
  }

  const applyDisconnectedSeat = (snap, agentId) => {
    if (!snap || !agentId) return snap
    const seats = Array.isArray(snap.seats) ? snap.seats : []
    return {
      ...snap,
      seats: seats.map((seat) => {
        if (!seat || seat.agent_id !== agentId) return seat
        return {
          ...seat,
          agent_id: '',
          agent_name: '',
          stack: null,
          hole_cards: [],
          is_active: false
        }
      })
    }
  }

  const appendEvent = (evt) => {
    setEventLogs((prev) => [evt, ...prev].slice(0, MAX_EVENTS))
  }

  const appendThought = (evt) => {
    if (!evt?.thought_log) return
    const thought = {
      t: new Date().toLocaleTimeString(),
      seat: evt.player_seat,
      text: evt.thought_log
    }
    setThoughtLogs((prev) => [thought, ...prev].slice(0, MAX_THOUGHTS))
  }

  const handleMessage = (msg) => {
    if (msg.type === 'state_update') {
      const tableStatus = String(msg.table_status || 'active')
      if (tableStatus === 'closed') {
        clearLiveState()
        clearLivePanels()
        appendEvent({
          ts: new Date().toLocaleTimeString(),
          seat: '-',
          action: 'table_closed',
          amount: 0,
          event: 'table_closed',
          thought: msg.close_reason || 'table closed'
        })
        return
      }
      const nextSnapshot = applyDisconnectedSeat(msg, disconnectedAgentIdRef.current)
      setSnapshot(nextSnapshot)
      if (tableStatus === 'closing') {
        setActionDeadline(null)
        setTimeLeftMs(null)
      } else if (msg.action_timeout_ms) {
        const deadline = Date.now() + msg.action_timeout_ms
        setActionDeadline(deadline)
      }
    } else if (msg.type === 'event_log') {
      setLastEvent(msg)
      appendEvent({
        ts: new Date().toLocaleTimeString(),
        seat: msg.player_seat,
        action: msg.action,
        amount: msg.amount || 0,
        event: msg.event,
        thought: msg.thought_log || ''
      })
      appendThought(msg)
    } else if (msg.type === 'hand_end') {
      setShowdown(msg.showdown || [])
      appendEvent({
        ts: new Date().toLocaleTimeString(),
        seat: '-',
        action: 'hand_end',
        amount: msg.pot || 0,
        event: 'hand_end',
        thought: msg.winner ? `Winner: ${msg.winner}` : ''
      })
    } else if (msg.type === 'table_closing') {
      const nextDisconnectedId = msg.disconnected_agent_id || disconnectedAgentIdRef.current
      if (msg.disconnected_agent_id) {
        setDisconnectedAgent(msg.disconnected_agent_id)
      }
      setActionDeadline(null)
      setTimeLeftMs(null)
      setSnapshot((prev) => applyDisconnectedSeat(prev, nextDisconnectedId))
      appendEvent({
        ts: new Date().toLocaleTimeString(),
        seat: '-',
        action: 'table_closing',
        amount: 0,
        event: 'table_closing',
        thought: msg.reason || 'opponent disconnected'
      })
    } else if (msg.type === 'table_recovered') {
      setDisconnectedAgent('')
      appendEvent({
        ts: new Date().toLocaleTimeString(),
        seat: '-',
        action: 'table_recovered',
        amount: 0,
        event: 'table_recovered',
        thought: msg.agent_id ? `${msg.agent_id} reconnected` : 'opponent reconnected'
      })
    } else if (msg.type === 'table_closed') {
      clearLiveState()
      clearLivePanels()
      appendEvent({
        ts: new Date().toLocaleTimeString(),
        seat: '-',
        action: 'table_closed',
        amount: 0,
        event: 'table_closed',
        thought: msg.reason || 'table closed'
      })
    }
  }

  const connect = (nextRoomOrOpts, maybeTableId) => {
    let nextRoomId = ''
    let nextTableId = ''
    if (nextRoomOrOpts && typeof nextRoomOrOpts === 'object') {
      nextRoomId = nextRoomOrOpts.roomId || ''
      nextTableId = nextRoomOrOpts.tableId || ''
    } else {
      nextRoomId = nextRoomOrOpts || ''
      nextTableId = maybeTableId || ''
    }
    clearLiveState()
    setRoomId(nextTableId || nextRoomId || '')
    if (demoMode) return
    if (!sseRef.current) {
      sseRef.current = new SpectateSSE({
        onMessage: handleMessage,
        onStatus: handleStatus
      })
    }
    sseRef.current.connect({ roomId: nextRoomId || '', tableId: nextTableId || '' })
  }

  const disconnect = () => {
    if (demoMode) return
    sseRef.current?.disconnect()
    clearLiveState()
  }

  useEffect(() => {
    if (!actionDeadline) {
      setTimeLeftMs(null)
      return
    }
    const id = setInterval(() => {
      const next = actionDeadline - Date.now()
      setTimeLeftMs(next > 0 ? next : 0)
    }, 200)
    return () => clearInterval(id)
  }, [actionDeadline])

  useEffect(() => {
    if (!demoMode) return
    setStatus('demo')
    if (demoTimerRef.current) clearInterval(demoTimerRef.current)
    demoTimerRef.current = setInterval(() => {
      const snap = createDemoSnapshot(roomId || 'demo')
      handleMessage(snap)
      if (Math.random() > 0.4) {
        handleMessage(createDemoEvent())
      }
      if (Math.random() > 0.8) {
        handleMessage({
          type: 'hand_end',
          pot: Math.floor(Math.random() * 15000 + 1200),
          winner: demoAgents[Math.floor(Math.random() * demoAgents.length)],
          showdown: [
            { agent_id: 'You', hole_cards: ['As', 'Kd'] },
            { agent_id: 'Rival', hole_cards: ['Tc', 'Th'] }
          ]
        })
      }
    }, 1500)
    return () => clearInterval(demoTimerRef.current)
  }, [demoMode, roomId])

  const value = useMemo(
    () => ({
      status,
      snapshot,
      eventLogs,
      thoughtLogs,
      lastEvent,
      showdown,
      roomId,
      timeLeftMs,
      connect,
      disconnect,
      demoMode
    }),
    [status, snapshot, eventLogs, thoughtLogs, lastEvent, showdown, roomId, timeLeftMs, demoMode]
  )

  return <SpectatorContext.Provider value={value}>{children}</SpectatorContext.Provider>
}

export function useSpectatorStore() {
  const ctx = useContext(SpectatorContext)
  if (!ctx) {
    throw new Error('useSpectatorStore must be used within SpectatorProvider')
  }
  return ctx
}
