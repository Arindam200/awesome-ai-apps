import type { CredentialsStatus } from './types';
import {
  DOUBAO_ASR_PROVIDER_ID,
  DOUBAO_LLM_PROVIDER_ID,
  GEMINI_PROVIDER_ID,
  OPENAI_COMPATIBLE_PROVIDER_ID,
  QWEN_LLM_PROVIDER_ID,
  QWEN_REALTIME_ASR_PROVIDER_ID,
} from './product';

export const PROVIDER_SETUP_PROMPT_DEFERRED_KEY = 'ol.providerSetupPromptDeferredThisSession';

const CLOUD_ASR_PROVIDER_IDS = new Set<string>([
  QWEN_REALTIME_ASR_PROVIDER_ID,
  DOUBAO_ASR_PROVIDER_ID,
]);

const SUPPORTED_LLM_PROVIDER_IDS = new Set<string>([
  QWEN_LLM_PROVIDER_ID,
  DOUBAO_LLM_PROVIDER_ID,
  GEMINI_PROVIDER_ID,
  OPENAI_COMPATIBLE_PROVIDER_ID,
]);

export function areProvidersConfigured(credentials: CredentialsStatus): boolean {
  const asrConfigured =
    CLOUD_ASR_PROVIDER_IDS.has(credentials.activeAsrProvider) && credentials.asrConfigured;
  const llmConfigured =
    SUPPORTED_LLM_PROVIDER_IDS.has(credentials.activeLlmProvider) && credentials.llmConfigured;
  return asrConfigured && llmConfigured;
}

export function shouldShowProviderSetupPrompt(
  credentials: CredentialsStatus,
  promptDeferredValue: string | null,
): boolean {
  return !areProvidersConfigured(credentials) && promptDeferredValue !== '1';
}
