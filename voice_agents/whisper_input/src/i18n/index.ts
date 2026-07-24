// i18n 入口 — 必须在任意 UI 组件 import 之前完成 init。
//
// 设计说明：
// - 资源在打包时静态注入（zh-CN.ts / en.ts）。无需后端推送，无网络请求。
// - LocalStorage key `ol.locale` 持久化用户选择；首次启动按 navigator.language 推断。
// - fallback 永远是 zh-CN：已知的产品权威文案，且 zh-CN.ts 是 source of truth。
// - 不用 LanguageDetector 插件：它的异步 init 在 Tauri WebView 里会让首次渲染拿到的
//   `t()` 返回 key（react-i18next useSuspense 默认 false 时返回 key 而非阻塞）。
//   手写检测 + initImmediate: false 让 init 同步完成，渲染前 t 就能用。

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { en } from './en';
import { ja } from './ja';
import { ko } from './ko';
import { zhCN } from './zh-CN';
import { zhTW } from './zh-TW';
import type { OutputLanguagePreference, UserPreferences } from '../lib/types';

export const SUPPORTED_LOCALES = ['zh-CN', 'zh-TW', 'en', 'ja', 'ko'] as const;
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

export const LOCALE_STORAGE_KEY = 'ol.locale';
export const OUTPUT_LANGUAGE_STORAGE_KEY = 'ol.outputLanguagePreference';
const FOLLOW_SYSTEM_VALUE = 'system';
export type OutputLanguageSelectPreference = Extract<
  OutputLanguagePreference,
  'auto' | 'zhCn' | 'zhTw' | 'en'
>;
export type OutputLanguagePreferencePatch = Pick<
  UserPreferences,
  'chineseScriptPreference' | 'outputLanguagePreference' | 'outputLanguagePreferenceExplicit'
>;

function detectSystemLocale(): SupportedLocale {
  if (typeof navigator === 'undefined') return 'zh-CN';
  const nav = (navigator.language || '').toLowerCase();
  if (nav.startsWith('zh')) {
    if (nav.includes('hant') || nav.includes('tw') || nav.includes('hk') || nav.includes('mo')) return 'zh-TW';
    return 'zh-CN';
  }
  if (nav.startsWith('ja')) return 'ja';
  if (nav.startsWith('ko')) return 'ko';
  return 'en';
}

function resolveLocalePreference(pref: SupportedLocale | typeof FOLLOW_SYSTEM_VALUE): SupportedLocale {
  if (pref === FOLLOW_SYSTEM_VALUE) return detectSystemLocale();
  return pref;
}

function getStoredLocale(): SupportedLocale | null {
  if (typeof window === 'undefined') return null;
  const raw = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  return raw === 'zh-CN' || raw === 'zh-TW' || raw === 'en' || raw === 'ja' || raw === 'ko' ? raw : null;
}

const initialLng: SupportedLocale = getStoredLocale() ?? detectSystemLocale();

void i18n.use(initReactI18next).init({
  resources: {
    'zh-CN': { translation: zhCN },
    'zh-TW': { translation: zhTW },
    en: { translation: en },
    ja: { translation: ja },
    ko: { translation: ko },
  },
  lng: initialLng,
  fallbackLng: 'zh-CN',
  supportedLngs: SUPPORTED_LOCALES as unknown as string[],
  partialBundledLanguages: true, // 告诉 i18next 我们的内联资源已完整，无需 backend 拉取
  interpolation: { escapeValue: false },
  react: { useSuspense: false }, // 不悬挂；首次渲染必须能拿到译文（无 backend 时 init 同步完成）
});

export default i18n;

/**
 * 当前持久化偏好。'system' 表示跟随系统；具体语言 tag 表示用户已显式选择。
 * 与 i18n.language 不同：i18n.language 永远是已 resolve 的具体语言。
 */
export function getLocalePreference(): SupportedLocale | typeof FOLLOW_SYSTEM_VALUE {
  return getStoredLocale() ?? FOLLOW_SYSTEM_VALUE;
}

/**
 * 写入用户偏好并立即切换 i18n 语言。
 * pref === 'system' 时清除存储项，重新走 navigator 检测。
 */
export async function setLocalePreference(
  pref: SupportedLocale | typeof FOLLOW_SYSTEM_VALUE,
): Promise<SupportedLocale> {
  const resolved = resolveLocalePreference(pref);
  if (pref === FOLLOW_SYSTEM_VALUE) {
    window.localStorage.removeItem(LOCALE_STORAGE_KEY);
  } else {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, pref);
  }
  await i18n.changeLanguage(resolved);
  return resolved;
}

export const FOLLOW_SYSTEM = FOLLOW_SYSTEM_VALUE;

function parseOutputLanguagePreference(raw: string | null): OutputLanguageSelectPreference | null {
  if (raw === 'auto' || raw === 'zhCn' || raw === 'zhTw' || raw === 'en') return raw;
  return null;
}

export function getStoredOutputLanguagePreference(): OutputLanguageSelectPreference | null {
  if (typeof window === 'undefined') return null;
  return parseOutputLanguagePreference(window.localStorage.getItem(OUTPUT_LANGUAGE_STORAGE_KEY));
}

export function hasStoredOutputLanguagePreference(): boolean {
  return getStoredOutputLanguagePreference() !== null;
}

export function outputPrefsForPreference(
  pref: OutputLanguageSelectPreference,
): OutputLanguagePreferencePatch {
  if (pref === 'zhCn') {
    return {
      chineseScriptPreference: 'simplified',
      outputLanguagePreference: 'zhCn',
      outputLanguagePreferenceExplicit: true,
    };
  }
  if (pref === 'zhTw') {
    return {
      chineseScriptPreference: 'traditional',
      outputLanguagePreference: 'zhTw',
      outputLanguagePreferenceExplicit: true,
    };
  }
  if (pref === 'en') {
    return {
      chineseScriptPreference: 'auto',
      outputLanguagePreference: 'en',
      outputLanguagePreferenceExplicit: true,
    };
  }
  return {
    chineseScriptPreference: 'auto',
    outputLanguagePreference: 'auto',
    outputLanguagePreferenceExplicit: true,
  };
}

export function getOutputLanguagePreference(
  current?: UserPreferences | null,
): OutputLanguageSelectPreference {
  const stored = getStoredOutputLanguagePreference();
  if (stored) return stored;
  if (!current?.outputLanguagePreferenceExplicit) return 'auto';
  return parseOutputLanguagePreference(current?.outputLanguagePreference ?? null) ?? 'auto';
}

export function setOutputLanguagePreference(
  pref: OutputLanguageSelectPreference,
): OutputLanguagePreferencePatch {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(OUTPUT_LANGUAGE_STORAGE_KEY, pref);
  }
  return outputPrefsForPreference(pref);
}

export function outputPrefsForLocale(
  resolved: SupportedLocale,
): Pick<UserPreferences, 'chineseScriptPreference' | 'outputLanguagePreference'> {
  const explicitOutputPreference = getStoredOutputLanguagePreference();
  if (explicitOutputPreference) {
    return outputPrefsForPreference(explicitOutputPreference);
  }
  if (resolved === 'zh-CN') {
    return {
      chineseScriptPreference: 'simplified',
      outputLanguagePreference: 'zhCn',
    };
  }
  if (resolved === 'zh-TW') {
    return {
      chineseScriptPreference: 'traditional',
      outputLanguagePreference: 'zhTw',
    };
  }
  if (resolved === 'en') {
    return {
      chineseScriptPreference: 'auto',
      outputLanguagePreference: 'en',
    };
  }
  if (resolved === 'ja') {
    return {
      chineseScriptPreference: 'auto',
      outputLanguagePreference: 'ja',
    };
  }
  if (resolved === 'ko') {
    return {
      chineseScriptPreference: 'auto',
      outputLanguagePreference: 'ko',
    };
  }
  return {
    chineseScriptPreference: 'auto',
    outputLanguagePreference: 'auto',
  };
}
