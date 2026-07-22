import {
  DOUBAO_ASR_PROVIDER_ID,
  DOUBAO_LLM_PROVIDER_ID,
  GEMINI_PROVIDER_ID,
  QWEN_LLM_PROVIDER_ID,
  QWEN_REALTIME_ASR_PROVIDER_ID,
} from './product';

const PROVIDER_LOGOS: Record<string, string> = {
  [QWEN_REALTIME_ASR_PROVIDER_ID]: 'provider-qwen.ico',
  [QWEN_LLM_PROVIDER_ID]: 'provider-qwen.ico',
  [DOUBAO_ASR_PROVIDER_ID]: 'provider-doubao.png',
  [DOUBAO_LLM_PROVIDER_ID]: 'provider-doubao.png',
  [GEMINI_PROVIDER_ID]: 'provider-gemini.svg',
};

export function providerLogoSrc(providerId: string | null | undefined): string {
  return PROVIDER_LOGOS[providerId ?? ''] ?? 'provider-qwen.ico';
}
