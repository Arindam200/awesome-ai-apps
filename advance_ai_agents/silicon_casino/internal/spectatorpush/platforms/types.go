package platforms

import "context"

type Field struct {
	Name   string
	Value  string
	Inline bool
}

type Message struct {
	PanelKey    string
	Title       string
	Content     string
	Description string
	Color       int
	Timestamp   string
	Footer      string
	Fields      []Field
}

type Adapter interface {
	Name() string
	Send(ctx context.Context, endpoint, secret string, msg Message) error
}
