package platforms

import "net/http"

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return f(req)
}

func newTestHTTPClient(fn roundTripFunc) *HTTPClient {
	return &HTTPClient{inner: &http.Client{Transport: fn}}
}
