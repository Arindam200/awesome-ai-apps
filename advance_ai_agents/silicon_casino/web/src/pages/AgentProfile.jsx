import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getAgentTables } from '../services/api.js'

export default function AgentProfile() {
  const { agentId } = useParams()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let dead = false
    setLoading(true)
    setError('')
    getAgentTables(agentId, { limit: 100, offset: 0 })
      .then((res) => {
        if (!dead) setItems(res.items || [])
      })
      .catch((err) => {
        if (!dead) setError(err?.message || 'agent_tables_load_failed')
      })
      .finally(() => {
        if (!dead) setLoading(false)
      })
    return () => {
      dead = true
    }
  }, [agentId])

  return (
    <section className="page">
      <div className="panel">
        <div className="panel-title">Agent Profile</div>
        <div className="muted">agent_id={agentId}</div>
        {loading && <div className="muted" style={{ marginTop: 8 }}>Loading...</div>}
        {error && <div className="muted" style={{ marginTop: 8 }}>{error}</div>}
      </div>

      <div className="panel" style={{ marginTop: 12 }}>
        <div className="panel-title">Participated Tables</div>
        {items.length === 0 && !loading && <div className="muted">No table history</div>}
        {items.map((it) => (
          <div key={it.table_id} style={{ borderBottom: '1px solid #2a2a2a', padding: '8px 0', display: 'flex', justifyContent: 'space-between' }}>
            <div>
              <strong>{it.table_id}</strong>
              <div className="muted">room={it.room_id} status={it.status} last_end={it.last_hand_ended_at || '-'}</div>
            </div>
            <Link className="btn btn-ghost" to={`/replay/${it.table_id}`}>Replay</Link>
          </div>
        ))}
      </div>
    </section>
  )
}
