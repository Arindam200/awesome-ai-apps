# Trace fixtures

This folder is populated by running:

```bash
python record_from_scenarios.py
```

That script runs each scenario in `scenarios/*.json` through the AI
clients under Monocle instrumentation, then copies the emitted trace JSON
files here as `<scenario_id>.json`. The offline tests in
`test_temporal_tx_coverage.py` load these fixtures with
`JSONSpanLoader.from_json(...)`.

After a successful first recording, update the placeholder token/duration
budgets in `test_temporal_tx_coverage.py` with the measured values rounded
up with headroom — same convention as the open-swe/monocle-test suite.
