const apiKey = process.env.NEBIUS_API_KEY
const baseUrl = (process.env.NEBIUS_BASE_URL || 'https://api.tokenfactory.nebius.com/v1').replace(/\/$/, '')
const model = process.env.NEBIUS_MODEL || 'meta-llama/Meta-Llama-3.1-70B-Instruct'

if (!apiKey) {
  console.error('NEBIUS_API_KEY is required. Create a Nebius Token Factory key and set it only in your shell environment.')
  process.exit(2)
}

const response = await fetch(`${baseUrl}/chat/completions`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${apiKey}`,
  },
  body: JSON.stringify({
    model,
    messages: [{ role: 'user', content: 'Reply exactly: Nebius smoke test passed.' }],
    temperature: 0,
    max_tokens: 32,
  }),
})

if (!response.ok) {
  throw new Error(`Nebius Token Factory request failed (${response.status}): ${await response.text()}`)
}

const payload = await response.json()
const content = payload.choices?.[0]?.message?.content?.trim()
if (!content) {
  throw new Error('Nebius Token Factory response did not include choices[0].message.content')
}

console.log(JSON.stringify({
  provider: 'Nebius Token Factory',
  baseUrl,
  model,
  responsePreview: content.slice(0, 120),
}, null, 2))
