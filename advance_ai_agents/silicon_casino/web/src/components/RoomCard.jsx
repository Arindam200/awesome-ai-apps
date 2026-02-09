import React from 'react'

function formatTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleTimeString()
}

function shortId(value) {
  if (!value) return '-'
  return value.length > 8 ? value.slice(0, 8) : value
}

function toLabel(value) {
  if (!value) return 'Open'
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function resolveRoomStatus(room, tables) {
  const roomStatus = String(room?.status || '')
    .trim()
    .toLowerCase()
  if (roomStatus) return toLabel(roomStatus)

  const statusSet = new Set((tables || []).map((table) => String(table?.status || '').toLowerCase()).filter(Boolean))
  if (statusSet.has('active')) return 'Live'
  if (statusSet.has('closing')) return 'Closing'
  if (statusSet.has('closed')) return 'Idle'
  return 'Open'
}

export default function RoomCard({ room, active, onSelect, tables, selectedTable, onSelectTable }) {
  const roomStatus = resolveRoomStatus(room, tables)

  return (
    <div className={`room-card ${active ? 'active' : ''}`}>
      <button className="room-card-main" onClick={() => onSelect(room)}>
        <div className="room-card-header">
          <div className="room-card-title">{room.name}</div>
          <div className="room-card-pill">{roomStatus}</div>
        </div>
        <div className="room-card-stats">
          <div>
            <span className="label">Min Buy-in</span>
            <strong>{room.min_buyin_cc} CC</strong>
          </div>
          <div>
            <span className="label">Blinds</span>
            <strong>
              {room.small_blind_cc}/{room.big_blind_cc}
            </strong>
          </div>
        </div>
        <div className="room-card-footer">Spectator feed ready</div>
      </button>

      {active && (
        <div className="room-table-panel">
          <div className="room-table-header">
            <div className="panel-title">Tables</div>
            <span className="rail-count">{tables?.length || 0} tables</span>
          </div>
          {!tables || tables.length === 0 ? (
            <div className="empty-panel">No active tables yet</div>
          ) : (
            <div className="room-table-list">
              {tables.map((table) => (
                <button
                  key={table.table_id}
                  className={`room-table-row ${selectedTable?.table_id === table.table_id ? 'active' : ''}`}
                  onClick={() => onSelectTable(table)}
                >
                  <div className="room-table-title">Table {shortId(table.table_id)}</div>
                  <div className="room-table-meta">
                    <span className="label">Blinds</span>
                    <strong>
                      {table.small_blind_cc}/{table.big_blind_cc}
                    </strong>
                  </div>
                  <div className="room-table-meta">
                    <span className="label">Created</span>
                    <strong>{formatTime(table.created_at)}</strong>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
