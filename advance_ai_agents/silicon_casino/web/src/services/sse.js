const defaultUrl = `${window.location.origin}/api/public/spectate/events`

export class SpectateSSE {
  constructor({ url = defaultUrl, onMessage, onStatus }) {
    this.url = url
    this.onMessage = onMessage
    this.onStatus = onStatus
    this.es = null
    this.roomId = ''
    this.tableId = ''
    this.retry = 0
    this.closedByUser = false
    this.timer = null
  }

  connect(roomOrOpts) {
    this._clearTimer()
    if (this.es) {
      this.es.close()
      this.es = null
    }
    if (roomOrOpts && typeof roomOrOpts === 'object') {
      this.roomId = roomOrOpts.roomId || ''
      this.tableId = roomOrOpts.tableId || ''
    } else {
      this.roomId = roomOrOpts || ''
      this.tableId = ''
    }
    this.closedByUser = false
    this.retry = 0
    this._open()
  }

  disconnect() {
    this.closedByUser = true
    this._clearTimer()
    if (this.es) {
      this.es.close()
    }
    this.es = null
    this._emitStatus('disconnected')
  }

  _open() {
    this._emitStatus('connecting')
    const params = new URLSearchParams()
    if (this.roomId) params.set('room_id', this.roomId)
    if (this.tableId) params.set('table_id', this.tableId)
    const source = new EventSource(`${this.url}?${params.toString()}`)
    this.es = source

    source.onopen = () => {
      this.retry = 0
      this._emitStatus('connected')
    }

    source.onerror = () => {
      this.es = null
      if (this.closedByUser) {
        this._emitStatus('disconnected')
        return
      }
      this._emitStatus('reconnecting')
      source.close()
      this._scheduleReconnect()
    }

    const handleEnvelope = (ev) => {
      if (!this.onMessage) return
      try {
        const envelope = JSON.parse(ev.data)
        const evt = envelope?.event || ev.type
        if (evt === 'table_snapshot') {
          this.onMessage({
            type: 'state_update',
            table_id: envelope?.data?.table_id || envelope?.session_id || '',
            ...envelope.data
          })
          return
        }
        if (evt === 'action_log') {
          this.onMessage({
            type: 'event_log',
            table_id: envelope?.data?.table_id || envelope?.session_id || '',
            player_seat: envelope.data?.player_seat,
            action: envelope.data?.action,
            amount: envelope.data?.amount || 0,
            thought_log: envelope.data?.thought_log || '',
            event: envelope.data?.event || 'action'
          })
          return
        }
        if (evt === 'hand_end') {
          this.onMessage({ type: 'hand_end', ...envelope.data })
          return
        }
        if (evt === 'reconnect_grace_started') {
          this.onMessage({
            type: 'table_closing',
            table_id: envelope?.data?.table_id || envelope?.session_id || '',
            disconnected_agent_id: envelope?.data?.disconnected_agent_id || '',
            deadline_ts: envelope?.data?.deadline_ts || 0,
            reason: envelope?.data?.reason || 'table_closing'
          })
          return
        }
        if (evt === 'opponent_reconnected') {
          this.onMessage({
            type: 'table_recovered',
            table_id: envelope?.data?.table_id || envelope?.session_id || '',
            agent_id: envelope?.data?.agent_id || ''
          })
          return
        }
        if (evt === 'opponent_forfeited') {
          this.onMessage({
            type: 'table_closing',
            table_id: envelope?.data?.table_id || envelope?.session_id || '',
            disconnected_agent_id: envelope?.data?.forfeiter_agent_id || '',
            reason: envelope?.data?.reason || 'opponent_forfeited'
          })
          return
        }
        if (evt === 'table_closed') {
          this.onMessage({
            type: 'table_closed',
            table_id: envelope?.data?.table_id || envelope?.session_id || '',
            reason: envelope?.data?.reason || 'table_closed'
          })
        }
      } catch (err) {
        this.onMessage({ type: 'parse_error', error: err?.message || 'parse_error' })
      }
    }

    source.addEventListener('table_snapshot', handleEnvelope)
    source.addEventListener('action_log', handleEnvelope)
    source.addEventListener('hand_end', handleEnvelope)
    source.addEventListener('reconnect_grace_started', handleEnvelope)
    source.addEventListener('opponent_reconnected', handleEnvelope)
    source.addEventListener('opponent_forfeited', handleEnvelope)
    source.addEventListener('table_closed', handleEnvelope)
    source.addEventListener('message', handleEnvelope)
  }

  _scheduleReconnect() {
    this._clearTimer()
    const delays = [500, 1000, 2000, 5000]
    const wait = delays[Math.min(this.retry, delays.length - 1)]
    this.retry += 1
    this.timer = setTimeout(() => this._open(), wait)
  }

  _clearTimer() {
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }
  }

  _emitStatus(status) {
    if (this.onStatus) this.onStatus(status)
  }
}
