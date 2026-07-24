const apiKey = process.env.NEBIUS_API_KEY?.trim();
const model =
  process.env.NEBIUS_MODEL?.trim() ||
  'meta-llama/Meta-Llama-3.1-8B-Instruct';
const endpoint = 'https://api.tokenfactory.nebius.com/v1/chat/completions';
const qwen35ReasoningModel = /^qwen\/qwen3\.5-/i.test(model);

if (!apiKey) {
  console.error('NEBIUS_API_KEY is required for the Nebius Token Factory smoke test.');
  process.exit(2);
}

const response = await fetch(endpoint, {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${apiKey}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    model,
    messages: [{ role: 'user', content: 'Reply with exactly: ok' }],
    max_completion_tokens: qwen35ReasoningModel ? 512 : 8,
    temperature: 0,
    ...(qwen35ReasoningModel ? { reasoning_effort: 'low' } : {}),
  }),
  signal: AbortSignal.timeout(30_000),
});

if (!response.ok) {
  console.error(`Nebius Token Factory request failed with HTTP ${response.status}.`);
  process.exit(1);
}

const payload = await response.json();
const content = payload?.choices?.[0]?.message?.content;
if (typeof content !== 'string' || content.trim().length === 0) {
  console.error('Nebius Token Factory returned no chat-completion content.');
  process.exit(1);
}

console.log(`Nebius Token Factory smoke test passed for model: ${model}`);
