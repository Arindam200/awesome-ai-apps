-- name: CreateRoom :exec
INSERT INTO rooms (id, name, min_buyin_cc, small_blind_cc, big_blind_cc, status)
VALUES ($1, $2, $3, $4, $5, 'active');

-- name: GetRoomByID :one
SELECT id, name, min_buyin_cc, small_blind_cc, big_blind_cc, status, created_at
FROM rooms
WHERE id = $1;

-- name: ListRooms :many
SELECT id, name, min_buyin_cc, small_blind_cc, big_blind_cc, status, created_at
FROM rooms
WHERE status = 'active'
ORDER BY min_buyin_cc ASC;

-- name: CountRooms :one
SELECT COUNT(1)::int
FROM rooms;

-- name: CreateTable :exec
INSERT INTO tables (id, room_id, status, small_blind_cc, big_blind_cc)
VALUES ($1, $2, $3, $4, $5);

-- name: ListTables :many
SELECT id, room_id, status, small_blind_cc, big_blind_cc, created_at
FROM tables
WHERE status = 'active'
  AND ($1::text = '' OR room_id = $1)
ORDER BY created_at DESC
LIMIT $2 OFFSET $3;

-- name: MarkTableStatusByID :execrows
UPDATE tables
SET status = $2
WHERE id = $1;

-- name: CreateHand :exec
INSERT INTO hands (id, table_id)
VALUES ($1, $2);

-- name: EndHand :exec
UPDATE hands
SET ended_at = now(),
    winner_agent_id = NULLIF($2::text, ''),
    pot_cc = $3,
    street_end = NULLIF($4::text, '')
WHERE id = $1;

-- name: RecordAction :exec
INSERT INTO actions (id, hand_id, agent_id, action_type, amount_cc)
VALUES ($1, $2, $3, $4, $5);
