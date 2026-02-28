import {
  AgentProfileSchema,
  AgentTableSchema,
  LeaderboardSchema,
  PublicRoomsSchema,
  PublicTablesSchema,
  TableHistorySchema,
  TableReplayResponseSchema,
  TableSnapshotResponseSchema,
  TableTimelineResponseSchema
} from '../lib/schemas.js'

async function fetchJSON(url, code) {
  const res = await fetch(url)
  if (!res.ok) {
    const err = new Error(`${code}:${res.status}`)
    err.status = res.status
    throw err
  }
  return res.json()
}

function parseOrThrow(schema, data, code) {
  if (!schema || typeof schema.safeParse !== 'function') {
    const err = new Error(`schema_missing:${code}`)
    err.status = 500
    throw err
  }
  const parsed = schema.safeParse(data)
  if (parsed.success) return parsed.data
  const issue = parsed.error.issues?.[0]
  const path = issue?.path?.join('.') || 'unknown'
  const err = new Error(`schema_invalid:${code}:${path}`)
  err.status = 500
  throw err
}

export async function getPublicRooms() {
  const data = await fetchJSON('/api/public/rooms', 'rooms_fetch_failed')
  const parsed = parseOrThrow(PublicRoomsSchema, data, 'public_rooms')
  return parsed.items
}

export async function getPublicTables(roomId) {
  const qs = roomId ? `?room_id=${encodeURIComponent(roomId)}` : ''
  const data = await fetchJSON(`/api/public/tables${qs}`, 'tables_fetch_failed')
  const parsed = parseOrThrow(PublicTablesSchema, data, 'public_tables')
  return parsed.items
}

export async function getPublicAgentTable(agentId) {
  if (!agentId) {
    const err = new Error('agent_id_required')
    err.status = 400
    throw err
  }
  const data = await fetchJSON(`/api/public/agent-table?agent_id=${encodeURIComponent(agentId)}`, 'agent_table_unavailable')
  return parseOrThrow(AgentTableSchema, data, 'public_agent_table')
}

export async function getLeaderboard({
  window = '30d',
  roomId = 'all',
  sort = 'score',
  limit = 50,
  offset = 0
} = {}) {
  const params = new URLSearchParams()
  params.set('window', window)
  params.set('room_id', roomId)
  params.set('sort', sort)
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  const data = await fetchJSON(`/api/public/leaderboard?${params.toString()}`, 'leaderboard_unavailable')
  return parseOrThrow(LeaderboardSchema, data, 'public_leaderboard')
}

export async function getTableHistory({ roomId = '', agentId = '', limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams()
  if (roomId) params.set('room_id', roomId)
  if (agentId) params.set('agent_id', agentId)
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  const data = await fetchJSON(`/api/public/tables/history?${params.toString()}`, 'table_history_unavailable')
  return parseOrThrow(TableHistorySchema, data, 'table_history')
}

export async function getTableReplay(tableId, { fromSeq = 1, limit = 200 } = {}) {
  const params = new URLSearchParams()
  params.set('from_seq', String(fromSeq))
  params.set('limit', String(limit))
  const data = await fetchJSON(`/api/public/tables/${encodeURIComponent(tableId)}/replay?${params.toString()}`, 'table_replay_unavailable')
  return parseOrThrow(TableReplayResponseSchema, data, 'table_replay')
}

export async function getTableTimeline(tableId) {
  const data = await fetchJSON(`/api/public/tables/${encodeURIComponent(tableId)}/timeline`, 'table_timeline_unavailable')
  return parseOrThrow(TableTimelineResponseSchema, data, 'table_timeline')
}

export async function getTableSnapshot(tableId, atSeq) {
  const params = new URLSearchParams()
  params.set('at_seq', String(atSeq))
  const data = await fetchJSON(`/api/public/tables/${encodeURIComponent(tableId)}/snapshot?${params.toString()}`, 'table_snapshot_unavailable')
  return parseOrThrow(TableSnapshotResponseSchema, data, 'table_snapshot')
}

export async function getAgentTables(agentId, { limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams()
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  const data = await fetchJSON(`/api/public/agents/${encodeURIComponent(agentId)}/tables?${params.toString()}`, 'agent_tables_unavailable')
  return parseOrThrow(TableHistorySchema, data, 'agent_tables')
}

export async function getAgentProfile(agentId, { limit = 20, offset = 0 } = {}) {
  if (!agentId) {
    const err = new Error('agent_id_required')
    err.status = 400
    throw err
  }
  const params = new URLSearchParams()
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  const data = await fetchJSON(`/api/public/agents/${encodeURIComponent(agentId)}/profile?${params.toString()}`, 'agent_profile_unavailable')
  return parseOrThrow(AgentProfileSchema, data, 'agent_profile')
}
