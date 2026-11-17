# Database connection pool saturation

Keywords: connection pool, saturated, payments-db, timeouts, 5xx

## Symptoms
- Pool utilisation above 90%
- Upstream services show rising latency and 5xx errors

## Steps
1. Check for a recent deploy of a dependent service that changed query patterns or pool settings.
2. Look for long-running or idle-in-transaction sessions and terminate them if safe.
3. Temporarily raise the pool limit by at most 25% if the database has CPU headroom.
4. If a recent deploy is the cause, roll it back.
5. Post a status update to the incident channel every 30 minutes.
