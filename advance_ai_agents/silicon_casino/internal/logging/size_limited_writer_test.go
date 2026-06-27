package logging

import (
	"os"
	"path/filepath"
	"testing"
)

func TestSizeLimitedWriterTruncates(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "app.log")
	writer, err := newSizeLimitedWriter(path, 1)
	if err != nil {
		t.Fatalf("create writer: %v", err)
	}
	defer writer.Close()

	chunk := make([]byte, 512*1024)
	if _, err := writer.Write(chunk); err != nil {
		t.Fatalf("write chunk: %v", err)
	}
	if _, err := writer.Write(chunk); err != nil {
		t.Fatalf("write chunk: %v", err)
	}
	if _, err := writer.Write(chunk); err != nil {
		t.Fatalf("write chunk: %v", err)
	}

	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat log: %v", err)
	}
	if info.Size() > 1024*1024 {
		t.Fatalf("expected log <= 1MB, got %d", info.Size())
	}
}
