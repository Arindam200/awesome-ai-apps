# API high latency / elevated 5xx

Keywords: latency, p99, 5xx, error rate, checkout-api, slow

## Steps
1. Compare the start of the latency spike with the last deploy time.
2. Check dependency health (databases, downstream APIs).
3. If a deploy occurred within 30 minutes of the spike, prepare a rollback.
4. Enable the degraded-mode feature flag to shed non-essential traffic.
5. Notify support so they can prepare customer messaging.
