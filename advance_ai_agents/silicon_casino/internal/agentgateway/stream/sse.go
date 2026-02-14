package stream

import (
	"encoding/json"
	"fmt"
	"net/http"
)

func WriteSSE(w http.ResponseWriter, ev StreamEvent) error {
	data, err := json.Marshal(ev)
	if err != nil {
		return err
	}
	if ev.EventID != "" {
		if _, err := fmt.Fprintf(w, "id: %s\n", ev.EventID); err != nil {
			return err
		}
	}
	if _, err := fmt.Fprintf(w, "event: %s\n", ev.Event); err != nil {
		return err
	}
	if _, err := fmt.Fprintf(w, "data: %s\n\n", data); err != nil {
		return err
	}
	return nil
}
