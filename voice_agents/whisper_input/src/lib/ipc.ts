// ipc.ts — typed wrapper around Tauri `invoke`. When running outside Tauri
// (e.g. `vite dev` in a browser), every command falls back to mock data so
// the UI is still operable for visual review.

import type {
  ComboBinding,
  CorrectionRule,
  CredentialsStatus,
  DictationSession,
  DictionaryEntry,
  HotkeyCapability,
  HotkeyStatus,
  MicrophoneDevice,
  PermissionStatus,
  PolishMode,
  QaHotkeyBinding,
  ShortcutBinding,
  UpdateChannel,
  UsageStats,
  UserPreferences,
  WindowsImeStatus,
  VocabPresetStore,
} from './types';
export type { UpdateChannel } from './types';
import { OL_DATA } from './mockData';
import { defaultAppShortcutModifiers, defaultQaShortcut, formatComboLabel } from './hotkey';
import { PRODUCT_FEATURES } from './productMode';
import {
  DEFAULT_ASR_PROVIDER_ID,
  DEFAULT_LLM_PROVIDER_ID,
  DOUBAO_ASR_PROVIDER_ID,
  GEMINI_PROVIDER_ID,
  OPENAI_COMPATIBLE_PROVIDER_ID,
} from './product';

declare global {
  interface Window {
    __TAURI_INTERNALS__?: unknown;
  }
}

const isTauri =
  globalThis.window !== undefined && '__TAURI_INTERNALS__' in globalThis.window;

export async function invokeOrMock<T>(
  cmd: string,
  args: Record<string, unknown> | undefined,
  mock: () => T,
): Promise<T> {
  if (!isTauri) {
    return mock();
  }
  const { invoke } = await import('@tauri-apps/api/core');
  return invoke<T>(cmd, args);
}

// ── Mock fixtures ──────────────────────────────────────────────────────
const mockSettings: UserPreferences = {
  hotkey: { trigger: 'rightAlt', mode: 'hold', keys: [{ code: 'AltRight' }] },
  dictationHotkey: { primary: 'RightAlt', modifiers: [] },
  defaultMode: 'structured',
  enabledModes: ['raw', 'light', 'structured', 'formal'],
  launchAtLogin: false,
  showCapsule: true,
  muteDuringRecording: false,
  microphoneDeviceName: '',
  activeAsrProvider: DEFAULT_ASR_PROVIDER_ID,
  activeLlmProvider: DEFAULT_LLM_PROVIDER_ID,
  llmThinkingEnabled: false,
  restoreClipboardAfterPaste: true,
  pasteShortcut: 'ctrlV',
  allowNonTsfInsertionFallback: true,
  workingLanguages: ['简体中文'],
  translationTargetLanguage: '',
  qaHotkey: PRODUCT_FEATURES.showSelectionAskTab ? defaultQaShortcut() : null,
  chineseScriptPreference: 'auto',
  outputLanguagePreference: 'auto',
  outputLanguagePreferenceExplicit: false,
  historyEnabled: true,
  qaSaveHistory: false,
  customComboHotkey: null,
  translationHotkey: PRODUCT_FEATURES.showTranslationTab
    ? { primary: 'Shift', modifiers: [] }
    : { primary: 'Disabled', modifiers: [] },
  switchStyleHotkey: { primary: 'S', modifiers: defaultAppShortcutModifiers() },
  openAppHotkey: { primary: 'O', modifiers: defaultAppShortcutModifiers() },
  localAsrActiveModel: 'qwen3-asr-0.6b',
  localAsrMirror: 'huggingface',
  localAsrKeepLoadedSecs: 300,
  foundryLocalAsrModel: 'whisper-small',
  foundryLocalRuntimeSource: 'auto',
  foundryLocalAsrLanguageHint: '',
  foundryLocalAsrKeepLoadedSecs: 300,
  historyRetentionDays: 7,
  polishContextWindowMinutes: 5,
  startMinimized: false,
  updateChannel: 'stable',
  streamingInsert: true,
  streamingInsertSaveClipboard: true,
  rightAltHotkeyMigrationVersion: 1,
};

const mockHotkeyCapability: HotkeyCapability = {
  adapter: 'windowsLowLevel',
  availableTriggers: ['rightAlt', 'rightControl', 'leftControl', 'rightCommand', 'custom'],
  requiresAccessibilityPermission: false,
  supportsModifierOnlyTrigger: true,
  supportsSideSpecificModifiers: true,
  explicitFallbackAvailable: false,
  statusHint: '默认建议使用“按住右 Alt 说话”；若无响应，可在权限页查看 hook 安装状态。',
};

const mockCredentialsStatus: CredentialsStatus = {
  activeAsrProvider: DEFAULT_ASR_PROVIDER_ID,
  activeLlmProvider: DEFAULT_LLM_PROVIDER_ID,
  asrConfigured: true,
  llmConfigured: true,
  volcengineConfigured: true,
  arkConfigured: true,
};

export interface ProviderCheckResult {
  ok: boolean;
}

export interface ProviderModelsResult {
  models: string[];
}

const mockHotkeyStatus: HotkeyStatus = {
  adapter: 'windowsLowLevel',
  state: 'installed',
  message: 'Windows 低层键盘 hook 已安装',
  lastError: null,
};

const mockWindowsImeStatus: WindowsImeStatus = {
  state: 'notWindows',
  usingTsfBackend: false,
  message: 'Browser dev mock',
  dllPath: null,
};

const mockMicrophoneDevices: MicrophoneDevice[] = [
  { name: 'Built-in Microphone', isDefault: true },
  { name: 'USB Microphone', isDefault: false },
];

const mockHistory: DictationSession[] = OL_DATA.history.map((h, i) => ({
  id: `mock-${i}`,
  createdAt: new Date(Date.now() - i * 36 * 60 * 60 * 1000).toISOString(),
  rawTranscript: h.preview,
  finalText: h.preview,
  mode: 'structured',
  appBundleId: null,
  appName: 'VS Code',
  insertStatus: (['inserted', 'pasteSent', 'copiedFallback', 'failed'] as const)[i % 4],
  errorCode: null,
  durationMs: 600 + i * 1800,
  dictionaryEntryCount: 28,
  asrProviderId: i % 2 === 0 ? DEFAULT_ASR_PROVIDER_ID : DOUBAO_ASR_PROVIDER_ID,
  llmProviderId:
    i % 3 === 0
      ? DEFAULT_LLM_PROVIDER_ID
      : i % 3 === 1
        ? GEMINI_PROVIDER_ID
        : OPENAI_COMPATIBLE_PROVIDER_ID,
}));

const mockVocab: DictionaryEntry[] = OL_DATA.vocab.map((v, i) => ({
  id: `vocab-${i}`,
  phrase: v.word,
  note: null,
  enabled: true,
  hits: v.count,
  createdAt: new Date().toISOString(),
}));

const mockCorrectionRules: CorrectionRule[] = [
  {
    id: 'rule-quantity-classifier',
    pattern: '{num}粒',
    replacement: '{num}例',
    enabled: true,
    createdAt: new Date().toISOString(),
  },
];

// ── Settings ───────────────────────────────────────────────────────────
export function getSettings(): Promise<UserPreferences> {
  return invokeOrMock('get_settings', undefined, () => mockSettings);
}

export function setSettings(prefs: UserPreferences): Promise<void> {
  return invokeOrMock('set_settings', { prefs }, () => undefined);
}

// ── Release channel (Beta opt-in) ──────────────────────────────────────
// 渠道偏好与 fetch_latest_beta_release 实际效果只在 Tauri runtime 内有意义；
// 浏览器开发模式下走 mock，避免设置页因 invoke 抛错而白屏。
// UpdateChannel 类型搬到 types.ts（UserPreferences.updateChannel 字段使用），
// 这里 re-export 保持外部模块（SettingsModal 等）import 路径不变。

export interface LatestBetaRelease {
  tagName: string;
  htmlUrl: string;
  publishedAt: string;
}

export function getUpdateChannel(): Promise<UpdateChannel> {
  return invokeOrMock('get_update_channel', undefined, () => 'stable' as UpdateChannel);
}

export function setUpdateChannel(channel: UpdateChannel): Promise<void> {
  return invokeOrMock('set_update_channel', { channel }, () => undefined);
}

export function fetchLatestBetaRelease(): Promise<LatestBetaRelease | null> {
  return invokeOrMock('fetch_latest_beta_release', undefined, () => null);
}

export function getHotkeyStatus(): Promise<HotkeyStatus> {
  return invokeOrMock('get_hotkey_status', undefined, () => mockHotkeyStatus);
}

export function getHotkeyCapability(): Promise<HotkeyCapability> {
  return invokeOrMock('get_hotkey_capability', undefined, () => mockHotkeyCapability);
}

export function getWindowsImeStatus(): Promise<WindowsImeStatus> {
  return invokeOrMock('get_windows_ime_status', undefined, () => mockWindowsImeStatus);
}

export function listMicrophoneDevices(): Promise<MicrophoneDevice[]> {
  return invokeOrMock('list_microphone_devices', undefined, () => mockMicrophoneDevices);
}

export function startMicrophoneLevelMonitor(deviceName: string): Promise<void> {
  return invokeOrMock('start_microphone_level_monitor', { deviceName }, () => undefined);
}

export function stopMicrophoneLevelMonitor(): Promise<void> {
  return invokeOrMock('stop_microphone_level_monitor', undefined, () => undefined);
}

// ── Credentials ────────────────────────────────────────────────────────
export function getCredentials(): Promise<CredentialsStatus> {
  return invokeOrMock('get_credentials', undefined, () => mockCredentialsStatus);
}

export function setCredential(account: string, value: string): Promise<void> {
  return invokeOrMock('set_credential', { account, value }, () => undefined);
}

export function setActiveAsrProvider(provider: string): Promise<void> {
  return invokeOrMock('set_active_asr_provider', { provider }, () => undefined);
}

export function setActiveLlmProvider(provider: string): Promise<void> {
  return invokeOrMock('set_active_llm_provider', { provider }, () => undefined);
}

export function readCredential(account: string): Promise<string | null> {
  return invokeOrMock<string | null>('read_credential', { account }, () => null);
}

export function validateProviderCredentials(kind: 'llm' | 'asr'): Promise<ProviderCheckResult> {
  return invokeOrMock('validate_provider_credentials', { kind }, () => ({ ok: true }));
}

export function listProviderModels(kind: 'llm' | 'asr'): Promise<ProviderModelsResult> {
  return invokeOrMock('list_provider_models', { kind }, () => ({ models: kind === 'llm' ? ['gpt-4o-mini', 'gemini-2.5-flash'] : ['whisper-1'] }));
}

// ── History ────────────────────────────────────────────────────────────
export function listHistory(): Promise<DictationSession[]> {
  return invokeOrMock('list_history', undefined, () => mockHistory);
}

export function getUsageStats(): Promise<UsageStats> {
  return invokeOrMock('get_usage_stats', undefined, () => {
    const totalChars = mockHistory.reduce((sum, session) => sum + session.finalText.length, 0);
    const totalDurationMs = mockHistory.reduce((sum, session) => sum + (session.durationMs ?? 0), 0);
    return {
      totalChars,
      totalDurationMs,
      totalSegments: mockHistory.length,
    };
  });
}

export function deleteHistoryEntry(id: string): Promise<void> {
  return invokeOrMock('delete_history_entry', { id }, () => undefined);
}

export function clearHistory(): Promise<void> {
  return invokeOrMock('clear_history', undefined, () => undefined);
}

export function clearLocalCache(): Promise<void> {
  return invokeOrMock('clear_local_cache', undefined, () => undefined);
}

export function clearProviderConfiguration(): Promise<UserPreferences> {
  return invokeOrMock('clear_provider_configuration', undefined, () => ({
    ...mockSettings,
    activeAsrProvider: DEFAULT_ASR_PROVIDER_ID,
    activeLlmProvider: DEFAULT_LLM_PROVIDER_ID,
  }));
}

export function deleteQingyuAsrModel(): Promise<void> {
  return invokeOrMock('delete_qingyu_asr_model', undefined, () => undefined);
}

// ── Vocab ──────────────────────────────────────────────────────────────
export function listVocab(): Promise<DictionaryEntry[]> {
  return invokeOrMock('list_vocab', undefined, () => mockVocab);
}

export function clearVocab(): Promise<void> {
  return invokeOrMock('clear_vocab', undefined, () => {
    mockVocab.splice(0, mockVocab.length);
  });
}

export function addVocab(phrase: string, note?: string): Promise<DictionaryEntry> {
  return invokeOrMock('add_vocab', { phrase, note }, () => ({
    id: `vocab-new-${Date.now()}`,
    phrase,
    note: note ?? null,
    enabled: true,
    hits: 0,
    createdAt: new Date().toISOString(),
  }));
}

export function removeVocab(id: string): Promise<void> {
  return invokeOrMock('remove_vocab', { id }, () => undefined);
}

export function setVocabEnabled(id: string, enabled: boolean): Promise<void> {
  return invokeOrMock('set_vocab_enabled', { id, enabled }, () => undefined);
}

export function listCorrectionRules(): Promise<CorrectionRule[]> {
  return invokeOrMock('list_correction_rules', undefined, () => mockCorrectionRules);
}

export function addCorrectionRule(pattern: string, replacement: string): Promise<CorrectionRule> {
  return invokeOrMock('add_correction_rule', { pattern, replacement }, () => ({
    id: `rule-new-${Date.now()}`,
    pattern,
    replacement,
    enabled: true,
    createdAt: new Date().toISOString(),
  }));
}

export function removeCorrectionRule(id: string): Promise<void> {
  return invokeOrMock('remove_correction_rule', { id }, () => undefined);
}

export function setCorrectionRuleEnabled(id: string, enabled: boolean): Promise<void> {
  return invokeOrMock('set_correction_rule_enabled', { id, enabled }, () => undefined);
}

export function listVocabPresets(): Promise<VocabPresetStore> {
  return invokeOrMock('list_vocab_presets', undefined, () => ({
    custom: [],
    overrides: [],
    disabledBuiltinPresetIds: [],
  }));
}

export function saveVocabPresets(store: VocabPresetStore): Promise<void> {
  return invokeOrMock('save_vocab_presets', { store }, () => undefined);
}

// ── Dictation lifecycle ────────────────────────────────────────────────
export function startDictation(): Promise<void> {
  return invokeOrMock('start_dictation', undefined, () => undefined);
}

export function stopDictation(): Promise<void> {
  return invokeOrMock('stop_dictation', undefined, () => undefined);
}

export function cancelDictation(): Promise<void> {
  return invokeOrMock('cancel_dictation', undefined, () => undefined);
}

export function handleWindowHotkeyEvent(
  eventType: 'keydown' | 'keyup',
  key: string,
  code: string,
  repeat: boolean,
): Promise<void> {
  return invokeOrMock(
    'handle_window_hotkey_event',
    { event_type: eventType, key, code, repeat },
    () => undefined,
  );
}

// ── Polish ─────────────────────────────────────────────────────────────
export function repolish(rawText: string, mode: PolishMode): Promise<string> {
  return invokeOrMock('repolish', { rawText, mode }, () => rawText);
}

export function setDefaultPolishMode(mode: PolishMode): Promise<void> {
  return invokeOrMock('set_default_polish_mode', { mode }, () => undefined);
}

export function setStyleEnabled(mode: PolishMode, enabled: boolean): Promise<void> {
  return invokeOrMock('set_style_enabled', { mode, enabled }, () => undefined);
}

// ── Permissions ────────────────────────────────────────────────────────
export function checkAccessibilityPermission(): Promise<PermissionStatus> {
  return invokeOrMock('check_accessibility_permission', undefined, () => 'granted' as const);
}

export function requestAccessibilityPermission(): Promise<PermissionStatus> {
  return invokeOrMock('request_accessibility_permission', undefined, () => 'granted' as const);
}

export function checkMicrophonePermission(): Promise<PermissionStatus> {
  return invokeOrMock('check_microphone_permission', undefined, () => 'granted' as const);
}

export function requestMicrophonePermission(): Promise<PermissionStatus> {
  return invokeOrMock('request_microphone_permission', undefined, () => 'granted' as const);
}

export function openSystemSettings(pane: 'accessibility' | 'microphone'): Promise<void> {
  return invokeOrMock('open_system_settings', { pane }, () => undefined);
}

export function triggerMicrophonePrompt(): Promise<void> {
  return invokeOrMock('trigger_microphone_prompt', undefined, () => undefined);
}

export function restartApp(): Promise<void> {
  return invokeOrMock('restart_app', undefined, () => undefined);
}

// ── QA (划词语音问答) ───────────────────────────────────────────────────
// 详见 issue #118。后端会发 `qa:state` / `qa:dismiss` 事件；前端通过下面四个
// 命令查询与控制 QA 浮窗。
export function getQaHotkeyLabel(): Promise<string> {
  return invokeOrMock('get_qa_hotkey_label', undefined, () => formatComboLabel(defaultQaShortcut()));
}

export function setQaHotkey(binding: QaHotkeyBinding | null): Promise<void> {
  return invokeOrMock('set_qa_hotkey', { binding }, () => undefined);
}

export function qaWindowDismiss(): Promise<void> {
  return invokeOrMock('qa_window_dismiss', undefined, () => undefined);
}

export function qaWindowPin(pinned: boolean): Promise<void> {
  return invokeOrMock('qa_window_pin', { pinned }, () => undefined);
}

// ── Combo Hotkey (自定义录音组合键) ───────────────────────────────────
export function validateComboHotkey(binding: ComboBinding): Promise<void> {
  return invokeOrMock('validate_combo_hotkey', { binding }, () => undefined);
}

export function setComboHotkey(binding: ComboBinding): Promise<void> {
  return invokeOrMock('set_combo_hotkey', { binding }, () => undefined);
}

export function validateShortcutBinding(binding: ShortcutBinding): Promise<void> {
  return invokeOrMock('validate_shortcut_binding', { binding }, () => undefined);
}

export function setDictationHotkey(binding: ShortcutBinding): Promise<void> {
  return invokeOrMock('set_dictation_hotkey', { binding }, () => undefined);
}

export function setTranslationHotkey(binding: ShortcutBinding): Promise<void> {
  return invokeOrMock('set_translation_hotkey', { binding }, () => undefined);
}

export function setSwitchStyleHotkey(binding: ShortcutBinding): Promise<void> {
  return invokeOrMock('set_switch_style_hotkey', { binding }, () => undefined);
}

export function setOpenAppHotkey(binding: ShortcutBinding): Promise<void> {
  return invokeOrMock('set_open_app_hotkey', { binding }, () => undefined);
}

export function setShortcutRecordingActive(active: boolean): Promise<void> {
  return invokeOrMock('set_shortcut_recording_active', { active }, () => undefined);
}

export async function openExternal(url: string): Promise<void> {
  if (!isTauri) {
    window.open(url, '_blank', 'noopener,noreferrer');
    return;
  }
  const { open } = await import('@tauri-apps/plugin-shell');
  await open(url);
}

/**
 * 让用户选 save 路径并把当前会话日志（openless.log）复制过去。
 * 浏览器开发模式下走 mock 不实际写盘。返回最终 save 的绝对路径，取消选择则返回 null。
 */
export async function exportErrorLog(suggestedFileName: string): Promise<string | null> {
  if (!isTauri) {
    return `~/Downloads/${suggestedFileName}`;
  }
  const { save } = await import('@tauri-apps/plugin-dialog');
  const target = await save({
    defaultPath: suggestedFileName,
    filters: [{ name: 'Log', extensions: ['log', 'txt'] }],
  });
  if (!target) return null;
  await invokeOrMock<void>('export_error_log', { targetPath: target }, () => undefined);
  return target;
}

export async function exportDiagnosticBundle(suggestedFileName: string): Promise<string | null> {
  if (!isTauri) {
    return `~/Downloads/${suggestedFileName}`;
  }
  const { save } = await import('@tauri-apps/plugin-dialog');
  const target = await save({
    defaultPath: suggestedFileName,
    filters: [{ name: 'Diagnostic bundle', extensions: ['zip'] }],
  });
  if (!target) return null;
  await invokeOrMock<string>(
    'export_diagnostic_bundle',
    { targetPath: target, recentLimit: 200 },
    () => target,
  );
  return target;
}

export { isTauri };
