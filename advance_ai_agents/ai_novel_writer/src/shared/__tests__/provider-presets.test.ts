import { describe, expect, it } from 'vitest'

import { BUILTIN_PRESETS } from '../provider-presets'

describe('Nebius Token Factory preset', () => {
  it('exposes the OpenAI-compatible Nebius endpoint and a documented chat model', () => {
    expect(BUILTIN_PRESETS).toContainEqual(expect.objectContaining({
      provider: 'nebius',
      displayName: 'Nebius Token Factory',
      baseUrl: 'https://api.tokenfactory.nebius.com/v1',
      protocol: 'openai',
      models: expect.arrayContaining([
        expect.objectContaining({ name: 'meta-llama/Meta-Llama-3.1-70B-Instruct' }),
      ]),
    }))
  })
})
