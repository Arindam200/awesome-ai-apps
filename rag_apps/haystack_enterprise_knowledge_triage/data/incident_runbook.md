# Production Incident Runbook

## Severity levels
- SEV1: complete outage or data loss affecting customers. Page the on-call engineer immediately; target acknowledgement within 5 minutes.
- SEV2: major degradation with a workaround. Acknowledge within 15 minutes.
- SEV3: minor issue. Handle during business hours.

## Response steps
1. Acknowledge the page and open an incident channel named `inc-YYYYMMDD-short-name`.
2. Assign an incident commander and a communications lead.
3. Post a status page update within 20 minutes of a SEV1 declaration, then every 30 minutes.
4. After resolution, hold a blameless postmortem within 5 business days.

## Rollbacks
If a deploy is suspected, roll back first and investigate afterwards. Use the `deploy rollback --service <name>` command from the release tooling.
