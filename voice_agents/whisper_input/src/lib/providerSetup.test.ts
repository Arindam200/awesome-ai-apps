import {
  areProvidersConfigured,
  shouldShowProviderSetupPrompt,
} from './providerSetup';

function assertEqual(actual: boolean, expected: boolean, name: string) {
  if (actual !== expected) {
    throw new Error(`${name}: expected ${expected}, got ${actual}`);
  }
}

assertEqual(
  areProvidersConfigured({
    activeAsrProvider: 'qwen3-asr-flash-realtime',
    activeLlmProvider: 'qwen-llm',
    asrConfigured: true,
    llmConfigured: true,
    volcengineConfigured: false,
    arkConfigured: false,
  }),
  true,
  'configured when Qwen ASR and Qwen LLM are ready',
);

assertEqual(
  areProvidersConfigured({
    activeAsrProvider: 'qwen3-asr-flash-realtime',
    activeLlmProvider: 'gemini',
    asrConfigured: false,
    llmConfigured: true,
    volcengineConfigured: false,
    arkConfigured: false,
  }),
  false,
  'not configured when Qwen API key is missing',
);

assertEqual(
  areProvidersConfigured({
    activeAsrProvider: 'qwen3-asr-flash-realtime',
    activeLlmProvider: 'qwen-llm',
    asrConfigured: true,
    llmConfigured: false,
    volcengineConfigured: false,
    arkConfigured: false,
  }),
  false,
  'not configured when Qwen LLM API key is missing',
);

assertEqual(
  areProvidersConfigured({
    activeAsrProvider: 'doubao-streaming-asr-2',
    activeLlmProvider: 'doubao-llm',
    asrConfigured: true,
    llmConfigured: true,
    volcengineConfigured: true,
    arkConfigured: true,
  }),
  true,
  'configured when Doubao ASR and Doubao LLM are ready',
);

assertEqual(
  areProvidersConfigured({
    activeAsrProvider: 'qingyu-local-fired-asr',
    activeLlmProvider: 'openai-compatible',
    asrConfigured: true,
    llmConfigured: true,
    volcengineConfigured: false,
    arkConfigured: true,
  }),
  false,
  'legacy local ASR does not satisfy cloud-first provider setup',
);

assertEqual(
  shouldShowProviderSetupPrompt(
    {
      activeAsrProvider: 'qwen3-asr-flash-realtime',
      activeLlmProvider: 'qwen-llm',
      asrConfigured: false,
      llmConfigured: false,
      volcengineConfigured: false,
      arkConfigured: false,
    },
    null,
  ),
  true,
  'show setup prompt when cloud defaults are missing',
);

assertEqual(
  shouldShowProviderSetupPrompt(
    {
      activeAsrProvider: 'qwen3-asr-flash-realtime',
      activeLlmProvider: 'qwen-llm',
      asrConfigured: false,
      llmConfigured: false,
      volcengineConfigured: false,
      arkConfigured: false,
    },
    '1',
  ),
  false,
  'do not repeat first-run prompt after the user has deferred it in this session',
);

assertEqual(
  shouldShowProviderSetupPrompt(
    {
      activeAsrProvider: 'qwen3-asr-flash-realtime',
      activeLlmProvider: 'qwen-llm',
      asrConfigured: true,
      llmConfigured: true,
      volcengineConfigured: false,
      arkConfigured: true,
    },
    null,
  ),
  false,
  'do not show prompt when providers are already configured',
);
