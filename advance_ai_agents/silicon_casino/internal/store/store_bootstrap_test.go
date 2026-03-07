package store

import "testing"

func TestStoreBootstrapPing(t *testing.T) {
	st, ctx, cleanup := openStore(t)
	defer cleanup()
	if err := st.Ping(ctx); err != nil {
		t.Fatalf("ping failed: %v", err)
	}
}
