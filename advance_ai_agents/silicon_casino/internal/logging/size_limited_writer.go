package logging

import (
	"os"
	"sync"
)

type sizeLimitedWriter struct {
	path     string
	maxBytes int64
	mu       sync.Mutex
	file     *os.File
	size     int64
}

func newSizeLimitedWriter(path string, maxMB int) (*sizeLimitedWriter, error) {
	if maxMB <= 0 {
		maxMB = 10
	}
	maxBytes := int64(maxMB) * 1024 * 1024
	f, size, err := openLogFile(path)
	if err != nil {
		return nil, err
	}
	return &sizeLimitedWriter{
		path:     path,
		maxBytes: maxBytes,
		file:     f,
		size:     size,
	}, nil
}

func (w *sizeLimitedWriter) Write(p []byte) (int, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.file == nil {
		f, size, err := openLogFile(w.path)
		if err != nil {
			return 0, err
		}
		w.file = f
		w.size = size
	}
	if w.size+int64(len(p)) > w.maxBytes {
		if err := w.truncate(); err != nil {
			return 0, err
		}
	}
	n, err := w.file.Write(p)
	w.size += int64(n)
	return n, err
}

func (w *sizeLimitedWriter) Close() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.file != nil {
		err := w.file.Close()
		w.file = nil
		return err
	}
	return nil
}

func (w *sizeLimitedWriter) truncate() error {
	if w.file != nil {
		_ = w.file.Close()
	}
	f, err := os.OpenFile(w.path, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	w.file = f
	w.size = 0
	return nil
}

func openLogFile(path string) (*os.File, int64, error) {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return nil, 0, err
	}
	info, err := f.Stat()
	if err != nil {
		_ = f.Close()
		return nil, 0, err
	}
	return f, info.Size(), nil
}
