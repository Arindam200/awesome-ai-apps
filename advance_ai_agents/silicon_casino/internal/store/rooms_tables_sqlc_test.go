package store

import "testing"

func TestRoomsAndTables(t *testing.T) {
	st, ctx, cleanup := openStore(t)
	defer cleanup()

	roomID, err := st.CreateRoom(ctx, "Low", 1000, 50, 100)
	if err != nil {
		t.Fatalf("create room: %v", err)
	}

	room, err := st.GetRoom(ctx, roomID)
	if err != nil {
		t.Fatalf("get room: %v", err)
	}
	if room.Name != "Low" {
		t.Fatalf("unexpected room name: %s", room.Name)
	}

	rooms, err := st.ListRooms(ctx)
	if err != nil {
		t.Fatalf("list rooms: %v", err)
	}
	if len(rooms) != 1 {
		t.Fatalf("expected 1 room, got %d", len(rooms))
	}

	tableID, err := st.CreateTable(ctx, roomID, "active", 50, 100)
	if err != nil {
		t.Fatalf("create table: %v", err)
	}
	if tableID == "" {
		t.Fatalf("table id should not be empty")
	}
	tables, err := st.ListTables(ctx, roomID, 10, 0)
	if err != nil {
		t.Fatalf("list tables: %v", err)
	}
	if len(tables) != 1 || tables[0].RoomID != roomID {
		t.Fatalf("unexpected tables: %+v", tables)
	}
}
