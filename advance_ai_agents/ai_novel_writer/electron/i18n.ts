import { localize, resolveLocale, translate, type MessageKey, type MessageParams } from '../src/i18n/core'
import type { Locale } from '../src/i18n/types'
import type { GlobalConfig } from '../src/shared/ipc-channels'
import { DEFAULT_GLOBAL_CONFIG, GLOBAL_CONFIG_PATH, readJsonFile } from './utils/config-utils'

export function resolveStoredOrSystemLocale(
  storedLocale: Locale | undefined,
  systemLocale: string | undefined,
): Locale {
  return storedLocale ?? resolveLocale(systemLocale)
}

export function getMainLocale(systemLocale: string | undefined): Locale {
  const config = readJsonFile<GlobalConfig>(GLOBAL_CONFIG_PATH, DEFAULT_GLOBAL_CONFIG)
  return resolveStoredOrSystemLocale(config.locale, systemLocale)
}

export function mainT(
  systemLocale: string | undefined,
  key: MessageKey,
  params?: MessageParams,
): string {
  return translate(getMainLocale(systemLocale), key, params)
}

export function mainText(
  systemLocale: string | undefined,
  zhCNText: string,
  enUSText: string,
  params?: MessageParams,
): string {
  return localize(getMainLocale(systemLocale), zhCNText, enUSText, params)
}
