# Nebius Token Factory Smoke-Test Evidence

- Date: 2026-07-24 (Asia/Shanghai)
- Endpoint: `https://api.tokenfactory.nebius.com/v1/chat/completions`
- Model: `Qwen/Qwen3.5-397B-A17B`
- Authentication: `NEBIUS_API_KEY` supplied only through the process environment; no credential was written to source control.
- Request settings: `reasoning_effort=low`, `max_completion_tokens=512`, `temperature=0`.
- Result: HTTP success, `finish_reason=stop`, non-empty assistant content returned.
- Usage: 321 completion tokens, 336 total tokens.

Reproduce with a valid environment-scoped credential:

```powershell
$env:NEBIUS_API_KEY = "<redacted>"
$env:NEBIUS_MODEL = "Qwen/Qwen3.5-397B-A17B"
npm run check:nebius-token-factory
```
