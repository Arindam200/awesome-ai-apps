import { useCallback, useEffect, useRef, useState, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Icon } from '../components/Icon';
import { ShortcutRecorder } from '../components/ShortcutRecorder';
import { isDialogStatus, UpdateDialog, useAutoUpdate } from '../components/AutoUpdate';
import { detectOS } from '../components/WindowChrome';
import { APP_VERSION_LABEL } from '../lib/appVersion';
import { isHotkeyModeMigrationNoticeActive } from '../lib/hotkeyMigration';
import {
  defaultQaShortcut,
  getHotkeyBindingCodes,
  getHotkeyBindingLabel,
  getHotkeyCodeLabel,
} from '../lib/hotkey';
import { createHotkeyRecorderState, orderHotkeyCodes, updateHotkeyRecorderState } from '../lib/hotkeyRecorder';
import {
  checkAccessibilityPermission,
  checkMicrophonePermission,
  clearHistory,
  clearProviderConfiguration,
  clearVocab,
  exportDiagnosticBundle,
  getHotkeyStatus,
  getWindowsImeStatus,
  isTauri,
  listMicrophoneDevices,
  openExternal,
  openSystemSettings,
  listProviderModels,
  readCredential,
  requestAccessibilityPermission,
  requestMicrophonePermission,
  setActiveAsrProvider,
  setActiveLlmProvider,
  setCredential,
  setDictationHotkey,
  setOpenAppHotkey,
  setQaHotkey,
  setSwitchStyleHotkey,
  setTranslationHotkey,
  startMicrophoneLevelMonitor,
  stopMicrophoneLevelMonitor,
  validateProviderCredentials,
} from '../lib/ipc';
import type {
  HotkeyCapability,
  HotkeyBinding,
  HotkeyMode,
  HotkeyStatus,
  HotkeyTrigger,
  MicrophoneDevice,
  PasteShortcut,
  PermissionStatus,
  WindowsImeStatus,
} from '../lib/types';
import { emitSaved } from '../lib/savedEvent';
import { providerLogoSrc } from '../lib/providerBrand';
import { useHotkeySettings } from '../state/HotkeySettingsContext';
import i18n, {
  FOLLOW_SYSTEM,
  getLocalePreference,
  getOutputLanguagePreference,
  setOutputLanguagePreference,
  setLocalePreference,
  type SupportedLocale,
} from '../i18n';
import {
  OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY,
  isAdvancedOpenAiCompatibleConfigVisible,
  llmPresetSelectionForVisibleProvider,
  normalizeStandardLlmProvider,
  outputPrefsPatchForUiLanguageChange,
  providerSwitchControlsDisabled,
  settingsVisibleLocaleOptions,
  settingsVisibleOutputLanguageOptions,
} from '../lib/settingsVisibility';
import {
  ASR_PROVIDER_PRESETS,
  LLM_MODEL_PRESETS,
  type AsrProviderPreset,
  type LlmModelPreset,
} from '../lib/providerPresets';
import { Btn, Collapsible, PageHeader } from './_atoms';
import { Card } from '../components/ui/Card';
import { Pill } from '../components/ui/Pill';
import { SettingRow } from '../components/ui/SettingRow';
import {
  DEFAULT_ASR_PROVIDER_ID,
  DEFAULT_LLM_PROVIDER_ID,
  DOUBAO_ASR_PROVIDER_ID,
  DOUBAO_LLM_PROVIDER_ID,
  GEMINI_PROVIDER_ID,
  LOCAL_ASR_PROVIDER_ID,
  OPENAI_COMPATIBLE_PROVIDER_ID,
  QWEN_LLM_PROVIDER_ID,
  QWEN_REALTIME_ASR_PROVIDER_ID,
} from '../lib/product';
import { PRODUCT_FEATURES } from '../lib/productMode';

interface SettingsProps {
  embedded?: boolean;
  initialSection?: SettingsSectionId;
}
export type SettingsSectionId = 'models' | 'recording' | 'privacy' | 'output' | 'about';
const SECTION_ORDER: SettingsSectionId[] = [
  'models',
  'recording',
  'privacy',
  'output',
  'about',
];
const SECTION_ICON_BY_ID: Record<SettingsSectionId, string> = {
  models: 'settings',
  recording: 'mic',
  privacy: 'cloud',
  output: 'translate',
  about: 'info',
};

interface AutostartStatus {
  enabled: boolean;
  stale: boolean;
  registeredPath: string | null;
  expectedPath: string;
}

async function getAutostartStatus(): Promise<AutostartStatus> {
  const { invoke } = await import('@tauri-apps/api/core');
  return invoke<AutostartStatus>('get_autostart_status');
}

async function setAutostartEnabled(enabled: boolean): Promise<AutostartStatus> {
  const { invoke } = await import('@tauri-apps/api/core');
  return invoke<AutostartStatus>('set_autostart_enabled', { enabled });
}

export function Settings({ embedded = false, initialSection = 'models' }: SettingsProps) {
  const { t } = useTranslation();
  const [section, setSection] = useState<SettingsSectionId>(initialSection);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  useEffect(() => {
    setSection(initialSection);
  }, [initialSection]);

  const selectedTabId = `wi-settings-tab-${section}`;
  const selectedPanelId = `wi-settings-panel-${section}`;
  const focusTab = (index: number) => {
    window.requestAnimationFrame(() => tabRefs.current[index]?.focus());
  };
  const onTabKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>, index: number) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    const delta = event.key === 'ArrowRight' ? 1 : -1;
    const nextIndex = (index + delta + SECTION_ORDER.length) % SECTION_ORDER.length;
    setSection(SECTION_ORDER[nextIndex]);
    focusTab(nextIndex);
  };

  return (
    <>
      {!embedded && (
        <PageHeader
          kicker={t('settings.kicker')}
          title={t('settings.title')}
          desc={t('settings.desc')}
        />
      )}
      <div
        className="wi-settings-layout"
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
          minHeight: 0,
          ...(embedded ? { flex: 1 } : {}),
        }}
      >
        <div className="wi-settings-tabs" role="tablist" aria-label={t('settings.title')}>
          {SECTION_ORDER.map((s, index) => {
            const active = section === s;
            const tabId = `wi-settings-tab-${s}`;
            const panelId = `wi-settings-panel-${s}`;
            return (
              <button
                key={s}
                ref={el => { tabRefs.current[index] = el; }}
                type="button"
                role="tab"
                id={tabId}
                aria-selected={active}
                aria-controls={panelId}
                tabIndex={active ? 0 : -1}
                onClick={() => setSection(s)}
                onKeyDown={event => onTabKeyDown(event, index)}
                className={active ? 'wi-settings-tab wi-settings-tab-active' : 'wi-settings-tab'}
              >
                <Icon name={SECTION_ICON_BY_ID[s]} size={16} strokeWidth={1.7} />
                <span>{t(`settings.sections.${s}`)}</span>
              </button>
            );
          })}
        </div>
        <div
          className={[
            'wi-settings-panel',
            `wi-settings-panel-${section}`,
            embedded ? 'ol-thinscroll' : '',
          ].filter(Boolean).join(' ')}
          role="tabpanel"
          id={selectedPanelId}
          aria-labelledby={selectedTabId}
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            minHeight: 0,
            overflow: 'auto',
            paddingRight: 4,
            paddingBottom: embedded ? 16 : 0,
          }}
        >
          {section === 'models' && <ModelsSection />}
          {section === 'recording' && <RecordingSection />}
          {section === 'privacy' && <PrivacySection />}
          {section === 'output' && <LanguageSection />}
          {section === 'about' && <AboutSection />}
        </div>
      </div>
    </>
  );
}

function RecordingSection() {
  const { t } = useTranslation();
  const { prefs, capability, updatePrefs: savePrefs } = useHotkeySettings();
  const [microphoneDevices, setMicrophoneDevices] = useState<MicrophoneDevice[]>([]);
  const [microphoneDevicesLoaded, setMicrophoneDevicesLoaded] = useState(false);
  const [microphoneDevicesError, setMicrophoneDevicesError] = useState<string | null>(null);
  const [microphonePickerOpen, setMicrophonePickerOpen] = useState(false);

  const loadMicrophoneDevices = useCallback(async (
    signal?: { cancelled: boolean },
    options: { showLoading?: boolean } = {},
  ) => {
    if (options.showLoading ?? true) {
      setMicrophoneDevicesLoaded(false);
    }
    setMicrophoneDevicesError(null);
    try {
      const devices = await listMicrophoneDevices();
      if (signal?.cancelled) return;
      setMicrophoneDevices(devices);
      setMicrophoneDevicesLoaded(true);
    } catch (err) {
      console.error('[settings] list microphone devices failed', err);
      if (signal?.cancelled) return;
      setMicrophoneDevices([]);
      setMicrophoneDevicesError(err instanceof Error ? err.message : String(err));
      setMicrophoneDevicesLoaded(true);
    }
  }, []);

  useEffect(() => {
    const signal = { cancelled: false };
    void loadMicrophoneDevices(signal);
    return () => {
      signal.cancelled = true;
    };
  }, [loadMicrophoneDevices]);

  useEffect(() => {
    if (!isTauri) return;
    let cancelled = false;
    let unlisten: (() => void) | undefined;
    async function listenForDeviceChanges() {
      const { listen } = await import('@tauri-apps/api/event');
      if (cancelled) return;
      const stopListening = await listen('microphone:devices-changed', () => {
        void loadMicrophoneDevices(undefined, { showLoading: false });
      });
      if (cancelled) {
        stopListening();
        return;
      }
      unlisten = stopListening;
    }
    void listenForDeviceChanges();
    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, [loadMicrophoneDevices]);

  useEffect(() => {
    if (microphonePickerOpen) {
      void loadMicrophoneDevices(undefined, { showLoading: false });
    }
  }, [loadMicrophoneDevices, microphonePickerOpen]);

  if (!prefs || !capability) {
    return (
      <Card>
        <div style={{ fontSize: 12, color: 'var(--ol-ink-4)' }}>{t('common.loading')}</div>
      </Card>
    );
  }

  const onModeChange = (mode: HotkeyMode) =>
    savePrefs({ ...prefs, hotkey: { ...prefs.hotkey, mode } });
  const onMuteDuringRecordingChange = (muteDuringRecording: boolean) =>
    savePrefs({ ...prefs, muteDuringRecording });
  const onMicrophoneDeviceChange = (microphoneDeviceName: string) =>
    savePrefs({ ...prefs, microphoneDeviceName });
  const onRestoreClipboardChange = (restoreClipboardAfterPaste: boolean) =>
    savePrefs({ ...prefs, restoreClipboardAfterPaste });
  const onPasteShortcutChange = (pasteShortcut: PasteShortcut) =>
    savePrefs({ ...prefs, pasteShortcut });
  const onAllowNonTsfFallbackChange = (allowNonTsfInsertionFallback: boolean) =>
    savePrefs({ ...prefs, allowNonTsfInsertionFallback });
  const onStreamingInsertChange = (next: boolean) =>
    savePrefs({ ...prefs, streamingInsert: next });
  const onStreamingInsertSaveClipboardChange = (next: boolean) =>
    savePrefs({ ...prefs, streamingInsertSaveClipboard: next });
  const clamp = (n: number, min: number, max: number) => Math.max(min, Math.min(max, n));
  const onHistoryRetentionChange = (raw: string) => {
    const parsed = raw === '' ? 0 : Number.parseInt(raw, 10);
    if (Number.isNaN(parsed)) return;
    void savePrefs({ ...prefs, historyRetentionDays: clamp(parsed, 0, 365) });
  };
  const onPolishContextWindowChange = (raw: string) => {
    const parsed = raw === '' ? 0 : Number.parseInt(raw, 10);
    if (Number.isNaN(parsed)) return;
    void savePrefs({ ...prefs, polishContextWindowMinutes: clamp(parsed, 0, 60) });
  };
  const onStartMinimizedChange = (startMinimized: boolean) =>
    savePrefs({ ...prefs, startMinimized });

  const choices: Array<[HotkeyMode, string]> = [
    ['toggle', t('settings.recording.modeToggle')],
    ['hold', t('settings.recording.modeHold')],
  ];
  const hotkeyDesc = capability.requiresAccessibilityPermission
    ? t('settings.recording.hotkeyDescAcc')
    : t('settings.recording.hotkeyDescNoAcc');
  const os = detectOS();
  const isMac = os === 'mac';
  const isWin = os === 'win';
  const isLinux = os === 'linux';
  const preferredMicrophoneAvailable = Boolean(
    prefs.microphoneDeviceName
    && microphoneDevices.some(device => device.name === prefs.microphoneDeviceName),
  );
  const effectiveMicrophoneDeviceName = prefs.microphoneDeviceName
    && (!microphoneDevicesLoaded || preferredMicrophoneAvailable)
    ? prefs.microphoneDeviceName
    : '';
  const selectedMicrophoneLabel = effectiveMicrophoneDeviceName
    ? effectiveMicrophoneDeviceName
    : t('settings.recording.microphoneDefault');

  return (
    <div className="wi-recording-settings-grid">
      <Card className="wi-recording-settings-primary">
        <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{t('settings.recording.title')}</div>
        <div style={{ fontSize: 11.5, color: 'var(--ol-ink-4)', marginBottom: 6 }}>{t('settings.recording.desc')}</div>
        {isHotkeyModeMigrationNoticeActive() && (
          <div
            style={{
              marginTop: 10,
              marginBottom: 8,
              padding: '12px 14px',
              borderRadius: 10,
              background: 'rgba(37,99,235,0.08)',
              border: '0.5px solid rgba(37,99,235,0.18)',
            }}
          >
            <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--ol-blue)', marginBottom: 4 }}>
              {t('settings.recording.migrationNoticeTitle')}
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--ol-ink-3)', lineHeight: 1.55 }}>
              {t('settings.recording.migrationNoticeDesc')}
            </div>
          </div>
        )}
        <SettingRow label={t('settings.recording.hotkeyLabel')} desc={hotkeyDesc}>
          <ShortcutRecorder
            value={prefs.dictationHotkey}
            onSave={async binding => {
              await setDictationHotkey(binding);
              await savePrefs({ ...prefs, dictationHotkey: binding });
            }}
          />
        </SettingRow>
        <SettingRow label={t('settings.recording.modeLabel')} desc={t('settings.recording.modeDesc')}>
          <div style={{ display: 'inline-flex', padding: 2, borderRadius: 8, background: 'rgba(0,0,0,0.05)' }}>
            {choices.map(([v, l]) => (
              <button
                key={v}
                onClick={() => onModeChange(v)}
                style={{
                  padding: '5px 14px', fontSize: 12, fontWeight: 500,
                  border: 0, borderRadius: 6, fontFamily: 'inherit',
                  background: prefs.hotkey.mode === v ? '#fff' : 'transparent',
                  color: prefs.hotkey.mode === v ? 'var(--ol-ink)' : 'var(--ol-ink-3)',
                  boxShadow: prefs.hotkey.mode === v ? '0 1px 2px rgba(0,0,0,.08)' : 'none',
                  cursor: 'default',
                  transition: 'background 0.16s var(--ol-motion-quick), color 0.16s var(--ol-motion-quick), box-shadow 0.18s var(--ol-motion-soft)',
                }}
              >
                {l}
              </button>
            ))}
          </div>
        </SettingRow>
        <SettingRow label={t('settings.recording.microphoneLabel')} desc={t('settings.recording.microphoneDesc')}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <button
              type="button"
              aria-label={t('settings.recording.microphoneLabel')}
              onClick={() => setMicrophonePickerOpen(true)}
              onKeyDown={e => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  setMicrophonePickerOpen(true);
                }
              }}
              onChange={() => {}}
              style={{
                ...inputStyle,
                flex: '0 0 auto',
                width: 200,
                maxWidth: 200,
                height: 32,
                minWidth: 0,
                alignSelf: 'flex-start',
                padding: '0 9px 0 10px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 8,
                textAlign: 'left',
                color: 'var(--ol-ink)',
              }}
            >
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {selectedMicrophoneLabel}
              </span>
              <Icon name="chevRight" size={13} />
            </button>
            {!microphoneDevicesLoaded && (
              <div style={{ fontSize: 11, color: 'var(--ol-ink-4)' }}>{t('common.loading')}</div>
            )}
            {microphoneDevicesError && (
              <div style={{ fontSize: 11, color: 'var(--ol-err)', lineHeight: 1.5 }}>
                {t('settings.recording.microphoneLoadError', { message: microphoneDevicesError })}
              </div>
            )}
          </div>
        </SettingRow>
        {microphonePickerOpen && (
          <MicrophonePickerDialog
            devices={microphoneDevices}
            selectedName={effectiveMicrophoneDeviceName}
            onClose={() => setMicrophonePickerOpen(false)}
            onRefresh={() => void loadMicrophoneDevices()}
            loading={!microphoneDevicesLoaded}
            onSelect={onMicrophoneDeviceChange}
          />
        )}
        <SettingRow
          label={t('settings.recording.muteDuringRecordingLabel')}
          desc={t('settings.recording.muteDuringRecordingDesc')}
        >
          <Toggle
            label={t('settings.recording.muteDuringRecordingLabel')}
            on={prefs.muteDuringRecording}
            onToggle={onMuteDuringRecordingChange}
          />
        </SettingRow>
      </Card>

      <Card className="wi-recording-settings-stream-startup">
        <section className="wi-recording-settings-section wi-recording-settings-stream">
          <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>
            {t(isLinux
              ? 'settings.advanced.streamingInsertTitleLinux'
              : 'settings.advanced.streamingInsertTitle')}
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--ol-ink-4)', marginBottom: 10, lineHeight: 1.55 }}>
            {t('settings.advanced.streamingInsertDesc')}
          </div>
          <SettingRow
            label={t('settings.advanced.streamingInsertLabel')}
            desc={t(
              isMac
                ? 'settings.advanced.streamingInsertHintMac'
                : isWin
                  ? 'settings.advanced.streamingInsertHintWindows'
                  : 'settings.advanced.streamingInsertHintLinux'
            )}
          >
            <Toggle
              label={t('settings.advanced.streamingInsertLabel')}
              on={prefs.streamingInsert}
              onToggle={onStreamingInsertChange}
            />
          </SettingRow>
          <SettingRow
            label={t('settings.advanced.streamingInsertSaveClipboardLabel')}
            desc={t('settings.advanced.streamingInsertSaveClipboardHint')}
          >
            <Toggle
              label={t('settings.advanced.streamingInsertSaveClipboardLabel')}
              on={prefs.streamingInsertSaveClipboard}
              onToggle={onStreamingInsertSaveClipboardChange}
            />
          </SettingRow>
        </section>

        <section className="wi-recording-settings-section wi-recording-settings-startup">
          <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>
            {t('settings.recording.startupGroupTitle')}
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--ol-ink-4)', marginBottom: 6, lineHeight: 1.55 }}>
            {t('settings.recording.startupAtBootDesc')}
          </div>
          <AutostartRow />
          <SettingRow
            label={t('settings.recording.startMinimizedLabel')}
            desc={t('settings.recording.startMinimizedDesc')}
          >
            <Toggle
              label={t('settings.recording.startMinimizedLabel')}
              on={prefs.startMinimized}
              onToggle={onStartMinimizedChange}
            />
          </SettingRow>
          {capability.statusHint && (
            <div className="wi-recording-settings-status-hint">
              {capability.statusHint}
            </div>
          )}
        </section>
      </Card>

      <Card className="wi-recording-settings-secondary wi-recording-settings-insert" padding={0}>
        <Collapsible title={t('settings.recording.insertGroupTitle')} defaultOpen embedded>
          <SettingRow
            label={t('settings.recording.restoreClipboardLabel')}
            desc={t('settings.recording.restoreClipboardDesc')}
          >
            <Toggle
              label={t('settings.recording.restoreClipboardLabel')}
              on={prefs.restoreClipboardAfterPaste}
              onToggle={onRestoreClipboardChange}
            />
          </SettingRow>
          {capability.adapter !== 'macEventTap' && (
            <SettingRow
              label={t('settings.recording.pasteShortcutLabel')}
              desc={t('settings.recording.pasteShortcutDesc')}
            >
              <select
                value={prefs.pasteShortcut}
                onChange={e => onPasteShortcutChange(e.target.value as PasteShortcut)}
                style={{ ...inputStyle, maxWidth: 220 }}
              >
                <option value="ctrlV">{t('settings.recording.pasteShortcutCtrlV')}</option>
                <option value="ctrlShiftV">{t('settings.recording.pasteShortcutCtrlShiftV')}</option>
                <option value="shiftInsert">{t('settings.recording.pasteShortcutShiftInsert')}</option>
              </select>
            </SettingRow>
          )}
          {PRODUCT_FEATURES.showTsfImeSettings && capability.adapter === 'windowsLowLevel' && (
            <SettingRow
              label={t('settings.recording.allowNonTsfFallbackLabel')}
              desc={t('settings.recording.allowNonTsfFallbackDesc')}
            >
              <Toggle
                label={t('settings.recording.allowNonTsfFallbackLabel')}
                on={prefs.allowNonTsfInsertionFallback}
                onToggle={onAllowNonTsfFallbackChange}
              />
            </SettingRow>
          )}
        </Collapsible>
      </Card>

      <Card className="wi-recording-settings-secondary wi-recording-settings-history" padding={0}>
        <Collapsible title={t('settings.recording.historyGroupTitle')} defaultOpen embedded>
          <SettingRow
            label={t('settings.recording.historyRetentionLabel')}
            desc={t('settings.recording.historyRetentionDesc')}
          >
            <input
              type="number"
              min={0}
              max={365}
              value={prefs.historyRetentionDays}
              onChange={e => onHistoryRetentionChange(e.target.value)}
              style={{ ...inputStyle, width: 80, textAlign: 'right' }}
            />
          </SettingRow>
          <SettingRow
            label={t('settings.recording.polishContextWindowLabel')}
            desc={t('settings.recording.polishContextWindowDesc')}
          >
            <input
              type="number"
              min={0}
              max={60}
              value={prefs.polishContextWindowMinutes}
              onChange={e => onPolishContextWindowChange(e.target.value)}
              style={{ ...inputStyle, width: 80, textAlign: 'right' }}
            />
          </SettingRow>
        </Collapsible>
      </Card>
    </div>
  );
}

function PrivacySection() {
  const { t } = useTranslation();
  const { prefs, updatePrefs, refresh } = useHotkeySettings();
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const helpItems = privacyHelpItemsCopy();
  const groupLabels = privacyGroupLabelsCopy();

  if (!prefs) {
    return (
      <Card>
        <div style={{ fontSize: 12, color: 'var(--ol-ink-4)' }}>{t('common.loading')}</div>
      </Card>
    );
  }

  const runAction = async (
    action: string,
    task: () => Promise<void | string | null>,
    successMessage = t('common.saved'),
  ) => {
    setBusyAction(action);
    emitSaved('saving', t('common.saving'));
    try {
      const result = await task();
      if (result === null) {
        return;
      }
      emitSaved('saved', typeof result === 'string' && result ? result : successMessage);
    } catch (error) {
      console.error(`[settings] ${action} failed`, error);
      emitSaved('failed', t('common.operationFailed'));
    } finally {
      setBusyAction(null);
    }
  };

  const onHistoryEnabledChange = (historyEnabled: boolean) => {
    void updatePrefs({ ...prefs, historyEnabled }).then(() => {
      emitSaved('saved', t('common.saved'));
    }).catch(async error => {
      console.error('[settings] failed to update history setting', error);
      try {
        await refresh();
      } catch (refreshError) {
        console.error('[settings] failed to refresh history setting after save failure', refreshError);
      }
      emitSaved('failed', t('common.operationFailed'));
    });
  };

  const onClearHistory = () => {
    if (!window.confirm(t('settings.privacy.confirmClearHistory'))) return;
    void runAction('clearHistory', clearHistory, t('settings.privacy.actionDone'));
  };

  const onClearVocab = () => {
    if (!window.confirm(t('settings.privacy.confirmClearVocab'))) return;
    void runAction('clearVocab', clearVocab, t('settings.privacy.actionDone'));
  };

  const onClearConfiguration = () => {
    if (!window.confirm(t('settings.privacy.confirmClearConfig'))) return;
    void runAction(
      'clearProviderConfiguration',
      async () => {
        await clearProviderConfiguration();
        await refresh();
      },
      t('settings.privacy.actionDone'),
    );
  };

  const onExportDiagnostics = () => {
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    void runAction(
      'exportDiagnostics',
      () => exportDiagnosticBundle(`whisper-input-diagnostics-${stamp}.zip`),
      t('settings.privacy.diagnosticExportDone'),
    );
  };

  const isBusy = (action: string) => busyAction === action;

  return (
    <Card className="wi-privacy-card" padding={16}>
      <div className="wi-privacy-heading">
        <div>
          <div className="wi-privacy-title">{t('settings.privacy.title')}</div>
          <div className="wi-privacy-desc">{t('settings.privacy.desc')}</div>
        </div>
        <div className="wi-privacy-notice">{t('settings.privacy.notice')}</div>
      </div>

      <div className="wi-help-list wi-privacy-data-flow">
        {helpItems.map(item => (
          <div key={item.title} className="wi-help-item">
            <span className="wi-privacy-data-icon">
              <Icon name={item.icon} size={16} strokeWidth={1.7} />
            </span>
            <strong>{item.title}</strong>
            <span>{item.desc}</span>
          </div>
        ))}
      </div>

      <div className="wi-privacy-controls">
        <div className="wi-privacy-control-section wi-privacy-retention">
          <div className="wi-privacy-group-title">{groupLabels.retention}</div>
          <section className="wi-privacy-control-group">
            <PrivacyActionRow
              label={t('settings.privacy.historyEnabledLabel')}
              desc={t('settings.privacy.historyEnabledDesc')}
            >
              <Toggle
                label={t('settings.privacy.historyEnabledLabel')}
                on={prefs.historyEnabled}
                onToggle={onHistoryEnabledChange}
              />
            </PrivacyActionRow>
            <PrivacyActionRow
              label={t('settings.privacy.clearHistoryLabel')}
              desc={t('settings.privacy.clearHistoryDesc')}
            >
              <Btn size="sm" variant="ghost" onClick={onClearHistory} disabled={isBusy('clearHistory')}>
                {isBusy('clearHistory') ? t('common.saving') : t('settings.privacy.clearHistoryBtn')}
              </Btn>
            </PrivacyActionRow>
            <PrivacyActionRow
              label={t('settings.privacy.clearVocabLabel')}
              desc={t('settings.privacy.clearVocabDesc')}
            >
              <Btn size="sm" variant="ghost" onClick={onClearVocab} disabled={isBusy('clearVocab')}>
                {isBusy('clearVocab') ? t('common.saving') : t('settings.privacy.clearVocabBtn')}
              </Btn>
            </PrivacyActionRow>
          </section>
        </div>

        <div className="wi-privacy-control-section wi-privacy-maintenance">
          <div className="wi-privacy-group-title">{groupLabels.maintenance}</div>
          <section className="wi-privacy-control-group">
            <PrivacyActionRow
              label={t('settings.privacy.clearConfigLabel')}
              desc={t('settings.privacy.clearConfigDesc')}
            >
              <Btn size="sm" variant="ghost" onClick={onClearConfiguration} disabled={isBusy('clearProviderConfiguration')}>
                {isBusy('clearProviderConfiguration') ? t('common.saving') : t('settings.privacy.clearConfigBtn')}
              </Btn>
            </PrivacyActionRow>
            <PrivacyActionRow
              label={t('settings.privacy.exportDiagnosticsLabel')}
              desc={t('settings.privacy.exportDiagnosticsDesc')}
            >
              <Btn size="sm" variant="ghost" onClick={onExportDiagnostics} disabled={isBusy('exportDiagnostics')}>
                {isBusy('exportDiagnostics') ? t('common.saving') : t('settings.privacy.exportDiagnosticsBtn')}
              </Btn>
            </PrivacyActionRow>
          </section>
        </div>
      </div>
    </Card>
  );
}

function PrivacyActionRow({ label, desc, children }: { label: string; desc: string; children: ReactNode }) {
  return (
    <div className="wi-privacy-action-row">
      <div className="wi-privacy-action-copy">
        <div className="wi-privacy-action-label">{label}</div>
        <div className="wi-privacy-action-desc">{desc}</div>
      </div>
      <div className="wi-privacy-action-control">{children}</div>
    </div>
  );
}

function privacyHelpItemsCopy() {
  const zh = i18n.language.toLowerCase().startsWith('zh');
  return zh
    ? [
        {
          icon: 'mic',
          title: '音频数据',
          desc: '你的语音音频会发送到你配置的云 ASR 服务商，用于语音识别。',
        },
        {
          icon: 'doc',
          title: '识别文本',
          desc: '识别文本会发送到你配置的 LLM 服务商，用于生成结果。',
        },
        {
          icon: 'archive',
          title: '本地数据',
          desc: '历史记录与词汇表默认仅存储在本地设备。',
        },
      ]
    : [
        {
          icon: 'mic',
          title: 'Audio data',
          desc: 'Your voice audio is sent to your configured cloud ASR provider for speech recognition.',
        },
        {
          icon: 'doc',
          title: 'Recognized text',
          desc: 'Recognized text is sent to your configured LLM provider to generate the result.',
        },
        {
          icon: 'archive',
          title: 'Local data',
          desc: 'History and vocabulary are stored only on this device by default.',
        },
      ];
}

function privacyGroupLabelsCopy() {
  return i18n.language.toLowerCase().startsWith('zh')
    ? { retention: '本地保留与历史', maintenance: '维护与支持' }
    : { retention: 'Local retention and history', maintenance: 'Maintenance and support' };
}

function HotkeyRecorder({
  binding,
  onCommit,
}: {
  binding: HotkeyBinding;
  onCommit: (codes: string[]) => void;
}) {
  const { t } = useTranslation();
  const [recording, setRecording] = useState(false);
  const [draftCodes, setDraftCodes] = useState<string[]>([]);
  const recorderStateRef = useRef(createHotkeyRecorderState());
  const recordingRef = useRef(false);

  const resetRecording = () => {
    recordingRef.current = false;
    recorderStateRef.current = createHotkeyRecorderState();
    setDraftCodes([]);
    setRecording(false);
  };

  const commitCodes = (codes: string[]) => {
    const ordered = orderHotkeyCodes(codes);
    resetRecording();
    onCommit(ordered);
  };

  const startRecording = () => {
    recordingRef.current = true;
    recorderStateRef.current = createHotkeyRecorderState();
    setDraftCodes([]);
    setRecording(true);
  };

  useEffect(() => {
    if (!recording) return undefined;

    const stopEvent = (event: Event) => {
      event.preventDefault();
      event.stopPropagation();
    };

    const applyHotkeyCode = (code: string, pressed: boolean) => {
      if (!recordingRef.current) return;
      const next = updateHotkeyRecorderState(recorderStateRef.current, code, pressed);
      recorderStateRef.current = next.state;
      setDraftCodes(next.state.draftCodes);
      if (next.commitCodes) commitCodes(next.commitCodes);
    };

    const onKeyDown = (event: KeyboardEvent) => {
      stopEvent(event);
      if (event.key === 'Escape' || event.code === 'Escape') {
        resetRecording();
        return;
      }
      const code = normalizeKeyboardHotkeyCode(event);
      if (!code) return;
      applyHotkeyCode(code, true);
    };

    const onKeyUp = (event: KeyboardEvent) => {
      stopEvent(event);
      if (!recordingRef.current) return;
      if (event.key === 'Escape' || event.code === 'Escape') {
        resetRecording();
        return;
      }
      const code = normalizeKeyboardHotkeyCode(event);
      if (!code) return;
      applyHotkeyCode(code, false);
    };

    const onMouseDown = (event: MouseEvent) => {
      const code = mouseButtonToHotkeyCode(event.button);
      if (!code) return;
      stopEvent(event);
      applyHotkeyCode(code, true);
    };

    const onMouseUp = (event: MouseEvent) => {
      const code = mouseButtonToHotkeyCode(event.button);
      if (!code) return;
      stopEvent(event);
      applyHotkeyCode(code, false);
    };

    window.addEventListener('keydown', onKeyDown, true);
    window.addEventListener('keyup', onKeyUp, true);
    window.addEventListener('mousedown', onMouseDown, true);
    window.addEventListener('mouseup', onMouseUp, true);
    return () => {
      window.removeEventListener('keydown', onKeyDown, true);
      window.removeEventListener('keyup', onKeyUp, true);
      window.removeEventListener('mousedown', onMouseDown, true);
      window.removeEventListener('mouseup', onMouseUp, true);
    };
  }, [recording]);

  const label = recording
    ? draftCodes.length > 0
      ? draftCodes.map(getHotkeyCodeLabel).join('+')
      : t('settings.recording.hotkeyRecording')
    : getHotkeyBindingLabel(binding);
  const hasKeys = getHotkeyBindingCodes(binding).length > 0;

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <button
        type="button"
        onClick={startRecording}
        style={{
          ...hotkeyRecorderButtonStyle,
          borderColor: recording ? 'var(--ol-blue)' : 'var(--ol-line-strong)',
          color: recording ? 'var(--ol-blue)' : 'var(--ol-ink)',
        }}
      >
        <span style={hotkeyRecorderLabelStyle}>{label}</span>
        {!recording && hasKeys && (
          <span
            role="button"
            tabIndex={0}
            aria-label={t('settings.recording.hotkeyClear')}
            onClick={event => {
              event.stopPropagation();
              onCommit([]);
            }}
            onKeyDown={event => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                event.stopPropagation();
                onCommit([]);
              }
            }}
            style={hotkeyClearButtonStyle}
          >
            <Icon name="x" size={11} strokeWidth={2} />
          </span>
        )}
      </button>
    </div>
  );
}

function MicrophonePickerDialog({
  devices,
  selectedName,
  onClose,
  onRefresh,
  loading,
  onSelect,
}: {
  devices: MicrophoneDevice[];
  selectedName: string;
  onClose: () => void;
  onRefresh: () => void;
  loading: boolean;
  onSelect: (name: string) => void;
}) {
  const { t } = useTranslation();
  const [pickedName, setPickedName] = useState(selectedName);
  const [previewName, setPreviewName] = useState(selectedName);
  const [level, setLevel] = useState(0);
  const [hoveredName, setHoveredName] = useState<string | null>(null);
  const [pressedName, setPressedName] = useState<string | null>(null);
  const [monitorError, setMonitorError] = useState<string | null>(null);
  const monitorQueueRef = useRef<Promise<void>>(Promise.resolve());

  const enqueueMonitorTask = useCallback((task: () => Promise<void>) => {
    const next = monitorQueueRef.current.catch(() => undefined).then(task);
    monitorQueueRef.current = next.catch(() => undefined);
    return next;
  }, []);

  useEffect(() => {
    setPickedName(selectedName);
    setPreviewName(selectedName);
  }, [selectedName]);

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    let cancelled = false;
    let timer: number | undefined;
    setLevel(0);
    setMonitorError(null);

    async function start() {
      await enqueueMonitorTask(async () => {
        try {
          if (isTauri) {
            const { listen } = await import('@tauri-apps/api/event');
            if (cancelled) return;
            const stopListening = await listen<{ level: number }>('microphone:level', event => {
              setLevel(Math.max(0, Math.min(1, event.payload.level ?? 0)));
            });
            if (cancelled) {
              stopListening();
              return;
            }
            unlisten = stopListening;
            await startMicrophoneLevelMonitor(previewName);
            if (cancelled) {
              unlisten?.();
              unlisten = undefined;
              await stopMicrophoneLevelMonitor();
            }
          } else {
            const tick = window.setInterval(() => {
              setLevel(0.25 + Math.random() * 0.55);
            }, 120);
            if (cancelled) {
              window.clearInterval(tick);
              return;
            }
            unlisten = () => window.clearInterval(tick);
          }
        } catch (err) {
          console.warn('[settings] microphone level monitor failed', err);
          if (!cancelled) {
            setMonitorError(err instanceof Error ? err.message : String(err));
          }
        }
      });
    }

    timer = window.setTimeout(() => {
      void start();
    }, 140);
    return () => {
      cancelled = true;
      if (timer !== undefined) {
        window.clearTimeout(timer);
      }
      void enqueueMonitorTask(async () => {
        unlisten?.();
        unlisten = undefined;
        await stopMicrophoneLevelMonitor();
      });
    };
  }, [enqueueMonitorTask, previewName]);

  const rows = [
    {
      id: 'default',
      name: '',
      label: t('settings.recording.microphoneDefault'),
      desc: t('settings.recording.microphoneDefaultDesc'),
      isDefault: false,
    },
    ...devices.map((device, index) => ({
      id: `${device.name}-${index}`,
      name: device.name,
      label: device.name,
      desc: device.isDefault ? t('settings.recording.microphoneSystemDefault') : '',
      isDefault: device.isDefault,
    })),
  ];

  return (
    <div
      role="presentation"
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 40,
        display: 'grid',
        placeItems: 'center',
        background: 'rgba(0,0,0,0.32)',
        animation: 'olMicPickerFadeIn 120ms ease-out',
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        onClick={e => e.stopPropagation()}
        style={{
          width: 450,
          maxWidth: 'calc(100vw - 48px)',
          borderRadius: 16,
          background: 'rgba(255,255,255,0.96)',
          border: '0.5px solid rgba(0,0,0,0.12)',
          boxShadow: '0 24px 70px rgba(0,0,0,0.28)',
          padding: 24,
          animation: 'olMicPickerPopIn 160ms cubic-bezier(.2,.8,.2,1)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 10 }}>
          <div style={{ fontSize: 18, fontWeight: 500 }}>{t('settings.recording.microphoneDialogTitle')}</div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <button
              type="button"
              onClick={onRefresh}
              disabled={loading}
              style={{
                border: 0,
                borderRadius: 999,
                background: 'transparent',
                color: loading ? 'var(--ol-ink-4)' : 'var(--ol-ink-3)',
                cursor: 'default',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 28,
                height: 28,
                opacity: loading ? 0.65 : 1,
                transition: 'background 0.16s var(--ol-motion-quick), opacity 0.16s var(--ol-motion-quick)',
              }}
              onMouseEnter={e => {
                if (!loading) e.currentTarget.style.background = 'rgba(0,0,0,0.05)';
              }}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              title={t('common.refresh')}
            >
              <Icon
                name="refresh"
                size={14}
                style={{ animation: loading ? 'olMicPickerSpin 800ms linear infinite' : undefined }}
              />
            </button>
            <button
              type="button"
              onClick={onClose}
              style={{
                border: 0,
                borderRadius: 999,
                background: 'transparent',
                color: 'var(--ol-ink-3)',
                cursor: 'default',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 28,
                height: 28,
                transition: 'background 0.16s var(--ol-motion-quick)',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(0,0,0,0.05)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              title={t('common.close')}
            >
              <Icon name="close" size={14} />
            </button>
          </div>
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--ol-ink-3)', lineHeight: 1.55, marginBottom: 18 }}>
          {t('settings.recording.microphoneDialogDesc')}
        </div>
        {monitorError && (
          <div style={{ fontSize: 11.5, color: 'var(--ol-err)', lineHeight: 1.45, marginBottom: 12 }}>
            {t('settings.recording.microphoneMonitorError', { message: monitorError })}
          </div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {rows.map(row => {
            const active = pickedName === row.name;
            const previewing = previewName === row.name;
            const hovered = hoveredName === row.name;
            const pressed = pressedName === row.name;
            return (
              <button
                key={row.id}
                type="button"
                onMouseEnter={() => {
                  setHoveredName(row.name);
                }}
                onMouseLeave={() => {
                  setHoveredName(null);
                  setPressedName(null);
                }}
                onMouseDown={() => setPressedName(row.name)}
                onMouseUp={() => setPressedName(null)}
                onFocus={() => {
                  setHoveredName(row.name);
                }}
                onBlur={() => setHoveredName(null)}
                onClick={() => {
                  setPickedName(row.name);
                  setPreviewName(row.name);
                  onSelect(row.name);
                }}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr auto',
                  gap: 14,
                  alignItems: 'center',
                  width: '100%',
                  padding: '14px 16px',
                  borderRadius: 10,
                  border: active ? '1px solid rgba(37,99,235,0.7)' : '0.5px solid rgba(0,0,0,0.12)',
                  background: active
                    ? 'rgba(37,99,235,0.08)'
                    : hovered
                      ? 'rgba(0,0,0,0.035)'
                      : '#fff',
                  boxShadow: active
                    ? '0 0 0 3px rgba(37,99,235,0.08)'
                    : hovered
                      ? '0 8px 18px rgba(0,0,0,0.06)'
                      : '0 1px 2px rgba(0,0,0,0.03)',
                  color: 'var(--ol-ink)',
                  cursor: 'default',
                  textAlign: 'left',
                  transform: pressed ? 'scale(0.992)' : hovered ? 'translateY(-1px)' : 'translateY(0)',
                  transition: 'background 140ms ease, border-color 140ms ease, box-shadow 160ms ease, transform 120ms ease',
                }}
              >
                <span style={{ minWidth: 0 }}>
                  <span style={{ display: 'block', fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {row.label}
                  </span>
                  {row.desc && (
                    <span style={{ display: 'block', fontSize: 11.5, color: 'var(--ol-ink-4)', marginTop: 3 }}>
                      {row.desc}
                    </span>
                  )}
                </span>
                <LevelMeter level={previewing ? level : 0} />
              </button>
            );
          })}
        </div>
        <style>
          {`
            @keyframes olMicPickerFadeIn {
              from { opacity: 0; }
              to { opacity: 1; }
            }
            @keyframes olMicPickerPopIn {
              from { opacity: 0; transform: translateY(8px) scale(.985); }
              to { opacity: 1; transform: translateY(0) scale(1); }
            }
            @keyframes olMicPickerSpin {
              from { transform: rotate(0deg); }
              to { transform: rotate(360deg); }
            }
          `}
        </style>
      </div>
    </div>
  );
}

function inferLegacyTrigger(codes: string[], fallback: HotkeyTrigger): HotkeyTrigger {
  if (codes.includes('ControlRight')) return 'rightControl';
  if (codes.includes('ControlLeft')) return 'leftControl';
  if (codes.includes('AltRight')) return 'rightAlt';
  if (codes.includes('AltLeft')) return 'leftOption';
  if (codes.includes('MetaRight')) return 'rightCommand';
  if (codes.includes('Fn')) return 'fn';
  return fallback;
}

function normalizeKeyboardHotkeyCode(event: KeyboardEvent): string | null {
  if (event.key === 'Fn' || event.code === 'Fn') return 'Fn';
  if (event.key === 'FnLock' || event.code === 'FnLock') return 'FnLock';
  const code = event.code === 'OSLeft' ? 'MetaLeft' : event.code === 'OSRight' ? 'MetaRight' : event.code;
  if (SUPPORTED_HOTKEY_CODES.has(code)) return code;
  if (/^Key[A-Z]$/.test(code)) return code;
  if (/^Digit[0-9]$/.test(code)) return code;
  if (/^F([1-9]|1[0-9]|2[0-4])$/.test(code)) return code;
  if (/^Numpad[0-9]$/.test(code)) return code;
  return null;
}

function mouseButtonToHotkeyCode(button: number): string | null {
  if (button === 3) return 'Mouse4';
  if (button === 4) return 'Mouse5';
  return null;
}

const SUPPORTED_HOTKEY_CODES = new Set([
  'ControlLeft', 'ControlRight', 'AltLeft', 'AltRight', 'ShiftLeft', 'ShiftRight',
  'MetaLeft', 'MetaRight', 'CapsLock', 'ScrollLock', 'Pause', 'PrintScreen',
  'Backspace', 'Tab', 'Enter', 'Space', 'Insert', 'Delete', 'Home', 'End',
  'PageUp', 'PageDown', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight',
  'ContextMenu', 'NumpadAdd', 'NumpadSubtract', 'NumpadMultiply', 'NumpadDivide',
  'NumpadDecimal', 'NumpadEnter', 'Backquote', 'Minus', 'Equal', 'BracketLeft',
  'BracketRight', 'Backslash', 'Semicolon', 'Quote', 'Comma', 'Period', 'Slash',
  'Fn', 'FnLock',
]);

function LevelMeter({ level }: { level: number }) {
  const amplified = Math.min(1, Math.max(0, level * 4.5));
  const bars = [0.25, 0.5, 0.75, 1, 0.75, 0.5];
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, height: 32 }}>
      {bars.map((weight, index) => {
        const intensity = Math.min(1, amplified * (0.85 + weight * 0.35));
        const height = 6 + intensity * (20 * weight);
        return (
          <span
            key={`${weight}-${index}`}
            style={{
              width: 5,
              height,
              borderRadius: 999,
              background: intensity > 0.08 ? 'var(--ol-blue)' : 'rgba(0,0,0,0.10)',
              opacity: 0.35 + intensity * 0.65,
              transition: 'height 70ms linear, opacity 90ms ease, background 120ms ease',
            }}
          />
        );
      })}
    </span>
  );
}

function AutostartRow() {
  const { t } = useTranslation();
  const [enabled, setEnabled] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isTauri) {
      setLoaded(true);
      return;
    }
    let cancelled = false;
    getAutostartStatus()
      .then((status: AutostartStatus) => {
        if (!cancelled) {
          setEnabled(status.enabled);
          setLoaded(true);
        }
      })
      .catch((err: unknown) => {
        console.error('[autostart] isEnabled failed', err);
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const onToggle = async (next: boolean) => {
    setEnabled(next);
    setError(null);
    try {
      if (!isTauri) return;
      const status = await setAutostartEnabled(next);
      setEnabled(status.enabled);
    } catch (err) {
      console.error('[autostart] toggle failed', err);
      setEnabled(!next);
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <SettingRow
      label={t('settings.recording.startupAtBoot')}
      desc={t('settings.recording.startupAtBootDesc')}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {loaded ? (
          <Toggle
            label={t('settings.recording.startupAtBoot')}
            on={enabled}
            onToggle={onToggle}
          />
        ) : null}
        {error && (
          <div style={{ fontSize: 11, color: 'var(--ol-err)', marginTop: 4, lineHeight: 1.5 }}>
            {t('settings.recording.startupAtBootError', { message: error })}
          </div>
        )}
      </div>
    </SettingRow>
  );
}

export function Toggle({
  label,
  on,
  onToggle,
  disabled = false,
}: {
  label: string;
  on: boolean;
  onToggle?: (next: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      className="wi-settings-toggle"
      onClick={() => {
        if (!disabled) onToggle?.(!on);
      }}
      disabled={disabled}
      style={{
        position: 'relative', width: 38, height: 22, borderRadius: 999, border: 0,
        background: on ? 'var(--ol-blue)' : 'rgba(0,0,0,0.15)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.55 : 1,
        transition: 'background 0.16s var(--ol-motion-quick)',
      }}
    >
      <span
        style={{
          position: 'absolute', top: 3, left: on ? 19 : 3,
          width: 16, height: 16, borderRadius: 999, background: '#fff',
          boxShadow: '0 1px 2px rgba(0,0,0,.25)', transition: 'left .16s var(--ol-motion-spring)',
        }}
      />
    </button>
  );
}

function LlmThinkingToggle({ enabled, onToggle, disabled = false }: { enabled: boolean; onToggle: (next: boolean) => void; disabled?: boolean }) {
  const { t } = useTranslation();
  return (
    <div
      title={t('settings.providers.thinkingModeHint')}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        paddingLeft: 2,
        whiteSpace: 'nowrap',
      }}
    >
      <span style={{ fontSize: 11.5, color: 'var(--ol-ink-4)' }}>
        {t('settings.providers.thinkingModeLabel')}
      </span>
      <Toggle
        label={t('settings.providers.thinkingModeLabel')}
        on={enabled}
        onToggle={onToggle}
        disabled={disabled}
      />
      <span style={{ fontSize: 11.5, color: enabled ? 'var(--ol-blue)' : 'var(--ol-ink-4)' }}>
        {enabled ? t('settings.providers.thinkingModeOn') : t('settings.providers.thinkingModeOff')}
      </span>
    </div>
  );
}

type LlmPresetKey = `${LlmModelPreset['providerId']}:${LlmModelPreset['model']}`;
type LlmPresetSelection = LlmPresetKey | typeof OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY;
type AsrPresetId = AsrProviderPreset['id'];
type ModelMode = 'simple' | 'advanced';
type ModelBundleId = 'qwen-priority' | 'doubao-backup';
type AdvancedAsrProviderId =
  | AsrPresetId
  | typeof LOCAL_ASR_PROVIDER_ID
  | 'local-qwen3'
  | 'foundry-local-whisper';

function llmPresetKey(preset: LlmModelPreset): LlmPresetKey {
  return `${preset.providerId}:${preset.model}`;
}

function findLlmPresetByKey(key: string): LlmModelPreset {
  return LLM_MODEL_PRESETS.find(preset => llmPresetKey(preset) === key) ?? LLM_MODEL_PRESETS[0];
}

function findLlmPreset(providerId: string | null | undefined, model: string | null | undefined): LlmModelPreset {
  const normalizedProvider = normalizeStandardLlmProvider(providerId);
  const modelMatch = LLM_MODEL_PRESETS.find(
    preset => preset.providerId === normalizedProvider && preset.model === model,
  );
  return modelMatch ?? LLM_MODEL_PRESETS.find(preset => preset.providerId === normalizedProvider) ?? LLM_MODEL_PRESETS[0];
}

function findRequiredLlmPreset(providerId: LlmModelPreset['providerId'], model: string): LlmModelPreset {
  return LLM_MODEL_PRESETS.find(
    preset => preset.providerId === providerId && preset.model === model,
  ) ?? LLM_MODEL_PRESETS[0];
}

function findAsrPreset(id: string | null | undefined): AsrProviderPreset {
  const normalized = normalizeVisibleAsrProvider(id);
  return ASR_PROVIDER_PRESETS.find(preset => preset.id === normalized) ?? ASR_PROVIDER_PRESETS[0];
}

const SETTINGS_PROVIDER_LOGO_SOURCES = {
  qwen: providerLogoSrc(QWEN_REALTIME_ASR_PROVIDER_ID),
  doubao: providerLogoSrc(DOUBAO_ASR_PROVIDER_ID),
  gemini: providerLogoSrc(GEMINI_PROVIDER_ID),
} as const;

const MODEL_BUNDLES: Record<ModelBundleId, { asrProviderId: AsrPresetId; llmPreset: LlmModelPreset; tone: 'blue' | 'outline'; logo: string }> = {
  'qwen-priority': {
    asrProviderId: QWEN_REALTIME_ASR_PROVIDER_ID,
    llmPreset: findRequiredLlmPreset(QWEN_LLM_PROVIDER_ID, 'qwen3.5-flash'),
    tone: 'blue',
    logo: SETTINGS_PROVIDER_LOGO_SOURCES.qwen,
  },
  'doubao-backup': {
    asrProviderId: DOUBAO_ASR_PROVIDER_ID,
    llmPreset: findRequiredLlmPreset(DOUBAO_LLM_PROVIDER_ID, 'doubao-seed-2-0-lite-260215'),
    tone: 'outline',
    logo: SETTINGS_PROVIDER_LOGO_SOURCES.doubao,
  },
};

function bundleIdForSelection(asrProviderId: AsrPresetId, llmPresetKeyValue: LlmPresetSelection): ModelBundleId | null {
  return (Object.keys(MODEL_BUNDLES) as ModelBundleId[]).find(bundleId => {
    const bundle = MODEL_BUNDLES[bundleId];
    return asrProviderId === bundle.asrProviderId && llmPresetKeyValue === llmPresetKey(bundle.llmPreset);
  }) ?? null;
}

function modelSettingsCopy() {
  const zh = i18n.language.toLowerCase().startsWith('zh');
  return zh
    ? {
        simpleMode: '简单模式',
        simpleModeDesc: '一键配置（推荐）',
        advancedMode: '高级模式',
        advancedModeDesc: '分别配置 ASR 与 LLM',
        bundleTitle: '1. 选择服务方案',
        quickConfigTitle: '2. 快速配置',
        sharedCredentialTitles: {
          'qwen-priority': '千问 ASR / LLM',
          'doubao-backup': '豆包 ASR / LLM',
        },
        recommended: '推荐',
        bundles: {
          'qwen-priority': {
            title: '千问优先',
            desc: '千问实时 ASR + 千问 Flash（qwen3.5-flash）润色，共用一个阿里云百炼 API Key。',
          },
          'doubao-backup': {
            title: '豆包备用',
            desc: '豆包流式 ASR + Doubao-Seed-2.0-Lite 润色，ASR 使用语音识别 APP Key，LLM 使用火山方舟 API Key。',
          },
        },
      }
    : {
        simpleMode: 'Simple mode',
        simpleModeDesc: 'One-step setup (recommended)',
        advancedMode: 'Advanced mode',
        advancedModeDesc: 'Configure ASR and LLM separately',
        bundleTitle: '1. Choose service bundle',
        quickConfigTitle: '2. Quick configuration',
        sharedCredentialTitles: {
          'qwen-priority': 'Qwen ASR / LLM',
          'doubao-backup': 'Doubao ASR / LLM',
        },
        recommended: 'Recommended',
        bundles: {
          'qwen-priority': {
            title: 'Qwen priority',
            desc: 'Qwen realtime ASR plus Qwen Flash (qwen3.5-flash) polish, using one Alibaba Cloud Bailian API key.',
          },
          'doubao-backup': {
            title: 'Doubao backup',
            desc: 'Doubao streaming ASR plus Doubao-Seed-2.0-Lite polish, using Speech APP Key for ASR and Ark API Key for LLM.',
          },
        },
      };
}

function normalizeVisibleAsrProvider(id: string | null | undefined): AsrPresetId {
  if (id === 'volcengine' || id === 'doubao' || id === 'doubao-streaming') {
    return DOUBAO_ASR_PROVIDER_ID;
  }
  if (ASR_PROVIDER_PRESETS.some(p => p.id === id)) {
    return id as AsrPresetId;
  }
  return DEFAULT_ASR_PROVIDER_ID;
}

function ApiKeyLinkButton({ url, labelKey, disabled = false }: { url: string; labelKey: string; disabled?: boolean }) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      onClick={() => {
        if (!disabled) void openExternal(url);
      }}
      disabled={disabled}
      title={t(labelKey)}
      style={{ ...miniBtnStyle, opacity: disabled ? 0.55 : 1 }}
    >
      {t(labelKey)}
    </button>
  );
}

function ModelsSection() {
  const { t } = useTranslation();
  const { prefs, updatePrefs } = useHotkeySettings();
  const modelCopy = modelSettingsCopy();
  const [modelMode, setModelMode] = useState<ModelMode>('simple');
  const [llmPreset, setLlmPreset] = useState<LlmPresetSelection>(llmPresetKey(LLM_MODEL_PRESETS[0]));
  const [asrProvider, setAsrProvider] = useState<AsrPresetId>(DEFAULT_ASR_PROVIDER_ID);
  const [committedLlmSelection, setCommittedLlmSelection] = useState<LlmPresetSelection>(llmPresetKey(LLM_MODEL_PRESETS[0]));
  const [committedAsrProvider, setCommittedAsrProvider] = useState<AsrPresetId>(DEFAULT_ASR_PROVIDER_ID);
  const [llmSwitching, setLlmSwitching] = useState(false);
  const [asrSwitching, setAsrSwitching] = useState(false);
  const llmSwitchSeqRef = useRef(0);
  const llmSwitchInFlightRef = useRef(0);
  const asrSwitchSeqRef = useRef(0);
  const visibleLlmPreset = llmPresetSelectionForVisibleProvider(prefs?.activeLlmProvider, llmPreset);
  const openAiCompatibleLlmSelected = visibleLlmPreset === OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY;
  const committedStandardLlmPresetKey = committedLlmSelection === OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY
    ? llmPresetKey(LLM_MODEL_PRESETS[0])
    : committedLlmSelection;
  const selectedLlmPresetKey: LlmPresetKey = openAiCompatibleLlmSelected || !LLM_MODEL_PRESETS.some(preset => llmPresetKey(preset) === llmPreset)
    ? committedStandardLlmPresetKey
    : llmPreset as LlmPresetKey;
  const activeLlmPreset = findLlmPresetByKey(selectedLlmPresetKey);
  const activeAsrPreset = findAsrPreset(asrProvider);
  const selectedBundleId = bundleIdForSelection(asrProvider, openAiCompatibleLlmSelected ? OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY : selectedLlmPresetKey);
  const llmControlsDisabled = providerSwitchControlsDisabled(llmSwitching);
  const asrControlsDisabled = providerSwitchControlsDisabled(asrSwitching);
  const simpleBundleUsesSharedApiKey =
    selectedBundleId !== null &&
    activeAsrPreset.apiKeyAccount === activeLlmPreset.apiKeyAccount;
  const sharedCredentialTitle = selectedBundleId
    ? modelCopy.sharedCredentialTitles[selectedBundleId]
    : modelCopy.sharedCredentialTitles['qwen-priority'];
  const llmApiKeyLink = (
    <ApiKeyLinkButton
      url={activeLlmPreset.apiKeyUrl}
      labelKey={activeLlmPreset.apiKeyLinkKey}
      disabled={llmControlsDisabled}
    />
  );
  const asrApiKeyLink = (
    <ApiKeyLinkButton
      url={activeAsrPreset.apiKeyUrl}
      labelKey={activeAsrPreset.apiKeyLinkKey}
      disabled={asrControlsDisabled}
    />
  );

  const beginLlmSwitch = useCallback((): number | null => {
    if (llmSwitchInFlightRef.current !== 0) return null;
    const seq = ++llmSwitchSeqRef.current;
    llmSwitchInFlightRef.current = seq;
    setLlmSwitching(true);
    return seq;
  }, []);

  const isCurrentLlmSwitch = useCallback((seq: number): boolean => {
    return llmSwitchInFlightRef.current === seq && llmSwitchSeqRef.current === seq;
  }, []);

  const endLlmSwitch = useCallback((seq: number) => {
    if (llmSwitchInFlightRef.current === seq && llmSwitchSeqRef.current === seq) {
      llmSwitchInFlightRef.current = 0;
      setLlmSwitching(false);
    }
  }, []);

  const rollbackLlmPreset = async () => {
    if (committedLlmSelection === OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY) {
      setLlmPreset(OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY);
      await setActiveLlmProvider(OPENAI_COMPATIBLE_PROVIDER_ID);
      if (prefs) {
        await updatePrefs({ ...prefs, activeLlmProvider: OPENAI_COMPATIBLE_PROVIDER_ID });
      }
      return;
    }
    const previous = findLlmPresetByKey(committedLlmSelection);
    setLlmPreset(committedLlmSelection);
    await setActiveLlmProvider(previous.providerId);
    await setCredential('ark.model_id', previous.model);
    if (prefs) {
      await updatePrefs({ ...prefs, activeLlmProvider: previous.providerId });
    }
  };

  const rollbackAsrProvider = async () => {
    setAsrProvider(committedAsrProvider);
    await setActiveAsrProvider(committedAsrProvider);
    if (prefs) {
      await updatePrefs({ ...prefs, activeAsrProvider: committedAsrProvider });
    }
  };

  useEffect(() => {
    if (!prefs) return;
    let cancelled = false;
    const syncLlmPreset = async () => {
      if (prefs.activeLlmProvider === OPENAI_COMPATIBLE_PROVIDER_ID) {
        setLlmPreset(OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY);
        setCommittedLlmSelection(OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY);
        return;
      }
      const model = await readCredential('ark.model_id').catch(() => null);
      if (cancelled || llmSwitchInFlightRef.current !== 0) return;
      const preset = findLlmPreset(prefs.activeLlmProvider, model);
      const key = llmPresetKey(preset);
      setLlmPreset(llmPresetSelectionForVisibleProvider(prefs.activeLlmProvider, key));
      setCommittedLlmSelection(key);
    };
    void syncLlmPreset();
    const asrId = normalizeVisibleAsrProvider(prefs.activeAsrProvider);
    setAsrProvider(asrId);
    setCommittedAsrProvider(asrId);
    return () => {
      cancelled = true;
    };
  }, [prefs]);

  const onLlmPresetChange = async (key: LlmPresetSelection) => {
    if (key === OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY) return;
    const seq = beginLlmSwitch();
    if (seq === null) return;
    const preset = findLlmPresetByKey(key);
    setLlmPreset(key);
    emitSaved('saving', t('common.saving'));
    try {
      await setActiveLlmProvider(preset.providerId);
      if (!isCurrentLlmSwitch(seq)) return;
      await setCredential('ark.model_id', preset.model);
      if (!isCurrentLlmSwitch(seq)) return;
      if (prefs) {
        const next = { ...prefs, activeLlmProvider: preset.providerId };
        await updatePrefs(next);
        if (!isCurrentLlmSwitch(seq)) return;
      }
      setCommittedLlmSelection(key);
      emitSaved('saved', t('common.saved'));
    } catch (err) {
      if (isCurrentLlmSwitch(seq)) {
        try {
          await rollbackLlmPreset();
        } catch (error) {
          console.error('[settings] failed to rollback LLM provider switch', error);
        }
        emitSaved('failed', t('common.operationFailed'));
      }
    } finally {
      endLlmSwitch(seq);
    }
  };

  const onAsrProviderChange = async (id: AsrPresetId) => {
    id = normalizeVisibleAsrProvider(id);
    setAsrProvider(id);
    const seq = ++asrSwitchSeqRef.current;
    setAsrSwitching(true);
    emitSaved('saving', t('common.saving'));
    try {
      await setActiveAsrProvider(id);
      if (seq !== asrSwitchSeqRef.current) return;
      if (prefs) {
        const next = { ...prefs, activeAsrProvider: id };
        await updatePrefs(next);
        if (seq !== asrSwitchSeqRef.current) return;
      }
      setCommittedAsrProvider(id);
      emitSaved('saved', t('common.saved'));
    } catch (err) {
      if (seq === asrSwitchSeqRef.current) {
        try {
          await rollbackAsrProvider();
        } catch (error) {
          console.error('[settings] failed to rollback ASR provider switch', error);
        }
        emitSaved('failed', t('common.operationFailed'));
      }
    } finally {
      if (seq === asrSwitchSeqRef.current) {
        setAsrSwitching(false);
      }
    }
  };

  const onBundleChange = async (bundleId: ModelBundleId) => {
    if (!prefs || llmSwitching || asrSwitching) return;
    const bundle = MODEL_BUNDLES[bundleId];
    const nextLlmPresetKey = llmPresetKey(bundle.llmPreset);
    const llmSeq = beginLlmSwitch();
    if (llmSeq === null) return;
    const asrSeq = ++asrSwitchSeqRef.current;
    setAsrSwitching(true);
    setAsrProvider(bundle.asrProviderId);
    setLlmPreset(nextLlmPresetKey);
    emitSaved('saving', t('common.saving'));
    try {
      await setActiveAsrProvider(bundle.asrProviderId);
      if (asrSeq !== asrSwitchSeqRef.current || !isCurrentLlmSwitch(llmSeq)) return;
      await setActiveLlmProvider(bundle.llmPreset.providerId);
      if (asrSeq !== asrSwitchSeqRef.current || !isCurrentLlmSwitch(llmSeq)) return;
      await setCredential('ark.model_id', bundle.llmPreset.model);
      if (asrSeq !== asrSwitchSeqRef.current || !isCurrentLlmSwitch(llmSeq)) return;
      await updatePrefs({
        ...prefs,
        activeAsrProvider: bundle.asrProviderId,
        activeLlmProvider: bundle.llmPreset.providerId,
      });
      if (asrSeq !== asrSwitchSeqRef.current || !isCurrentLlmSwitch(llmSeq)) return;
      setCommittedAsrProvider(bundle.asrProviderId);
      setCommittedLlmSelection(nextLlmPresetKey);
      emitSaved('saved', t('common.saved'));
    } catch (err) {
      if (asrSeq === asrSwitchSeqRef.current && isCurrentLlmSwitch(llmSeq)) {
        try {
          await rollbackAsrProvider();
          await rollbackLlmPreset();
        } catch (error) {
          console.error('[settings] failed to rollback bundle switch', error);
        }
        emitSaved('failed', t('common.operationFailed'));
      }
    } finally {
      if (asrSeq === asrSwitchSeqRef.current) {
        setAsrSwitching(false);
      }
      endLlmSwitch(llmSeq);
    }
  };

  return (
    <div className="wi-model-settings-compact">
      <div className="wi-model-storage-notice">
        {t('settings.providers.credentialStorageNotice')}
      </div>
      <div className="wi-model-mode">
        <button
          type="button"
          className={modelMode === 'simple' ? 'active' : undefined}
          onClick={() => setModelMode('simple')}
        >
          {modelCopy.simpleMode}
          <small>{modelCopy.simpleModeDesc}</small>
        </button>
        <button
          type="button"
          className={modelMode === 'advanced' ? 'active' : undefined}
          onClick={() => setModelMode('advanced')}
        >
          {modelCopy.advancedMode}
          <small>{modelCopy.advancedModeDesc}</small>
        </button>
      </div>

      {modelMode === 'simple' ? (
        <>
          <div className="wi-model-bundle-title">{modelCopy.bundleTitle}</div>
          <div className="wi-plan-grid">
            {(Object.keys(MODEL_BUNDLES) as ModelBundleId[]).map(bundleId => {
              const bundle = MODEL_BUNDLES[bundleId];
              const selected = selectedBundleId === bundleId;
              const bundleLogoSrc = bundle.logo;
              return (
                <button
                  key={bundleId}
                  type="button"
                  className={selected ? 'wi-plan-card selected' : 'wi-plan-card'}
                  onClick={() => onBundleChange(bundleId)}
                  disabled={llmControlsDisabled || asrControlsDisabled}
                >
                  <span className={selected ? 'wi-radio-corner on' : 'wi-radio-corner'} />
                  <img className="wi-plan-logo" src={bundleLogoSrc} alt="" />
                  <span className="wi-plan-body">
                    <span className="wi-plan-heading">
                      {modelCopy.bundles[bundleId].title}
                      {bundleId === 'qwen-priority' && <Pill tone="blue" size="sm">{modelCopy.recommended}</Pill>}
                    </span>
                    <span className="wi-plan-desc">{modelCopy.bundles[bundleId].desc}</span>
                    <span className="wi-plan-meta">ASR: {t(findAsrPreset(bundle.asrProviderId).labelKey)}</span>
                    <span className="wi-plan-meta">LLM: {t(bundle.llmPreset.labelKey)}</span>
                  </span>
                </button>
              );
            })}
          </div>
          <Card className="wi-quick-card">
            <div className="wi-quick-card-title">{modelCopy.quickConfigTitle}</div>
            <div className="wi-provider-stack">
              {simpleBundleUsesSharedApiKey ? (
                <div className="wi-provider-row">
                  <div className="wi-provider-label">
                    <span>{sharedCredentialTitle}</span>
                    <small>{t(activeAsrPreset.labelKey)} · {t(activeLlmPreset.labelKey)}</small>
                  </div>
                  <CredentialField
                    key="doubao:shared-simple-api-key"
                    label={t('settings.providers.apiKeyLabel')}
                    account={activeAsrPreset.apiKeyAccount}
                    mono
                    mask
                    inline
                    disabled={asrControlsDisabled || llmControlsDisabled}
                  />
                  {asrApiKeyLink}
                  <div className="wi-provider-inline-check wi-provider-inline-check-pair">
                    <ProviderValidateButton kind="asr" label={t('settings.providers.validateAsr')} />
                    <ProviderValidateButton kind="llm" label={t('settings.providers.validateLlm')} />
                  </div>
                </div>
              ) : (
                <>
                  <div className="wi-provider-row">
                    <div className="wi-provider-label">
                      <span>{t('settings.providers.asrTitle')}</span>
                      <small>{t(activeAsrPreset.labelKey)}</small>
                    </div>
                    <CredentialField
                      key={`${asrProvider}:simple-api-key`}
                      label={t('settings.providers.apiKeyLabel')}
                      account={activeAsrPreset.apiKeyAccount}
                      mono
                      mask
                      inline
                      disabled={asrControlsDisabled}
                    />
                    {asrApiKeyLink}
                    <div className="wi-provider-inline-check">
                      <ProviderValidateButton kind="asr" label={t('settings.providers.validateAsr')} />
                    </div>
                  </div>
                  <div className="wi-provider-row">
                    <div className="wi-provider-label">
                      <span>{t('settings.providers.llmTitle')}</span>
                      <small>{t(activeLlmPreset.labelKey)}</small>
                    </div>
                    <CredentialField
                      key={`${selectedLlmPresetKey}:simple-api-key`}
                      label={t('settings.providers.apiKeyLabel')}
                      account={activeLlmPreset.apiKeyAccount}
                      mono
                      mask
                      inline
                      disabled={llmControlsDisabled}
                    />
                    {llmApiKeyLink}
                    <div className="wi-provider-inline-check">
                      <ProviderValidateButton kind="llm" label={t('settings.providers.validateLlm')} />
                    </div>
                  </div>
                </>
              )}
            </div>
          </Card>
        </>
      ) : (
        <>
          <Card>
            <div className="wi-provider-section-head">
              <img className="wi-provider-section-logo" src={providerLogoSrc(asrProvider)} alt="" />
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{t('settings.providers.asrTitle')}</div>
                <div style={{ fontSize: 11.5, color: 'var(--ol-ink-4)', marginTop: 2 }}>{t('settings.providers.asrDesc')}</div>
              </div>
            </div>
            <div className="wi-provider-row">
              <select
                value={asrProvider}
                onChange={e => onAsrProviderChange(e.target.value as AsrPresetId)}
                disabled={asrControlsDisabled}
                style={{ ...inputStyle, maxWidth: 'none' }}
                aria-label={t('settings.providers.providerLabel')}
              >
                {ASR_PROVIDER_PRESETS.map(preset => (
                  <option key={preset.id} value={preset.id}>{t(preset.labelKey)}</option>
                ))}
              </select>
              <CredentialField
                key={`${asrProvider}:api_key`}
                label={t('settings.providers.apiKeyLabel')}
                account={activeAsrPreset.apiKeyAccount}
                mono
                mask
                inline
                disabled={asrControlsDisabled}
              />
              {asrApiKeyLink}
              <div className="wi-provider-inline-check">
                <ProviderValidateButton kind="asr" label={t('settings.providers.validateAsr')} />
              </div>
            </div>
          </Card>

          <Card>
            <div className="wi-provider-section-head">
              <img
                className="wi-provider-section-logo"
                src={openAiCompatibleLlmSelected ? SETTINGS_PROVIDER_LOGO_SOURCES.qwen : providerLogoSrc(activeLlmPreset.providerId)}
                alt=""
              />
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{t('settings.providers.llmTitle')}</div>
                <div style={{ fontSize: 11.5, color: 'var(--ol-ink-4)', marginTop: 2 }}>
                  {t('settings.providers.llmDesc')}
                </div>
              </div>
            </div>
            <div className="wi-provider-row">
              <select
                value={visibleLlmPreset}
                onChange={e => onLlmPresetChange(e.target.value as LlmPresetSelection)}
                disabled={llmControlsDisabled}
                style={{ ...inputStyle, maxWidth: 'none' }}
                aria-label={t('settings.providers.modelLabel')}
              >
                {openAiCompatibleLlmSelected && (
                  <option value={OPENAI_COMPATIBLE_ACTIVE_LLM_PRESET_KEY}>
                    {t('settings.providers.presets.openaiCompatible')}
                  </option>
                )}
                {LLM_MODEL_PRESETS.map(preset => {
                  const key = llmPresetKey(preset);
                  return <option key={key} value={key}>{t(preset.labelKey)}</option>;
                })}
              </select>
              {!openAiCompatibleLlmSelected ? (
                <>
                  <CredentialField
                    key={`${selectedLlmPresetKey}:api_key`}
                    label={t('settings.providers.apiKeyLabel')}
                    account={activeLlmPreset.apiKeyAccount}
                    mono
                    mask
                    inline
                    disabled={llmControlsDisabled}
                  />
                  {llmApiKeyLink}
                </>
              ) : (
                <div className="wi-provider-row-note">
                  {t('settings.advanced.openAiCompatibleActive')}
                </div>
              )}
              <div className="wi-provider-inline-check">
                <ProviderValidateButton kind="llm" label={t('settings.providers.validateLlm')} />
              </div>
            </div>
          </Card>
          <AdvancedSection
            llmSwitching={llmSwitching}
            beginLlmSwitch={beginLlmSwitch}
            isCurrentLlmSwitch={isCurrentLlmSwitch}
            endLlmSwitch={endLlmSwitch}
          />
        </>
      )}
    </div>
  );
}

function ProviderValidateButton({ kind, label }: { kind: 'asr' | 'llm'; label: string }) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<ProviderToolStatus>('idle');
  const [message, setMessage] = useState('');

  const validate = async () => {
    setStatus('loading');
    setMessage(t('settings.providers.validating'));
    try {
      const result = await validateProviderCredentials(kind);
      setStatus(result.ok ? 'success' : 'error');
      setMessage(t(kind === 'asr' ? 'settings.providers.validateAsrSuccess' : 'settings.providers.validateLlmSuccess'));
    } catch (error) {
      setStatus('error');
      setMessage(providerErrorMessage(error, t));
    }
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
      <button onClick={validate} style={miniBtnStyle} disabled={status === 'loading'}>{label}</button>
      {message && (
        <span style={{ fontSize: 11, color: status === 'error' ? 'var(--ol-warn)' : status === 'loading' ? 'var(--ol-ink-4)' : 'var(--ol-ok)', lineHeight: 1.4 }}>
          {message}
        </span>
      )}
    </div>
  );
}

interface AdvancedSectionProps {
  llmSwitching: boolean;
  beginLlmSwitch: () => number | null;
  isCurrentLlmSwitch: (seq: number) => boolean;
  endLlmSwitch: (seq: number) => void;
}

function AdvancedSection({ llmSwitching, beginLlmSwitch, isCurrentLlmSwitch, endLlmSwitch }: AdvancedSectionProps) {
  const { t } = useTranslation();
  const { prefs, updatePrefs } = useHotkeySettings();
  const os = detectOS();
  const isMac = os === 'mac';
  const isWin = os === 'win';
  const isLinux = os === 'linux';
  const platformSupported = isMac || isWin;
  const switchSeqRef = useRef(0);
  const [busy, setBusy] = useState(false);
  const [pendingTarget, setPendingTarget] = useState<AdvancedAsrProviderId | null>(null);
  const [advancedLlmModelRevision, setAdvancedLlmModelRevision] = useState(0);

  const activeAsrProvider = (prefs?.activeAsrProvider ?? DEFAULT_ASR_PROVIDER_ID) as AdvancedAsrProviderId;
  const activeLlmProvider = prefs?.activeLlmProvider ?? DEFAULT_LLM_PROVIDER_ID;
  const openAiCompatibleActive = activeLlmProvider === OPENAI_COMPATIBLE_PROVIDER_ID;
  const openAiCompatibleFieldsVisible = isAdvancedOpenAiCompatibleConfigVisible(
    activeLlmProvider,
    false,
  );
  const isOnLocalQwen3 = activeAsrProvider === 'local-qwen3';
  const isOnFoundry = activeAsrProvider === 'foundry-local-whisper';
  const isOnAnyLocal = isOnLocalQwen3 || isOnFoundry;

  const requestEnable = (target: AdvancedAsrProviderId) => {
    setPendingTarget(target);
  };

  const performSwitch = async (target: AdvancedAsrProviderId) => {
    if (!prefs) return;
    setBusy(true);
    const seq = ++switchSeqRef.current;
    const previous = activeAsrProvider;
    try {
      await setActiveAsrProvider(target);
      if (seq !== switchSeqRef.current) return;
      try {
        await updatePrefs({ ...prefs, activeAsrProvider: target });
      } catch (error) {
        await setActiveAsrProvider(previous);
        throw error;
      }
      emitSaved('saved', t('common.saved'));
    } catch (error) {
      console.error('[settings] failed to switch advanced ASR provider', error);
      emitSaved('failed', t('common.operationFailed'));
    } finally {
      if (seq === switchSeqRef.current) {
        setBusy(false);
        setPendingTarget(null);
      }
    }
  };

  const pendingNameKey =
    pendingTarget === 'local-qwen3' ? 'asrLocalQwen3'
    : pendingTarget === 'foundry-local-whisper' ? 'asrFoundryLocalWhisper'
    : null;

  const activateOpenAiCompatibleLlm = async () => {
    if (!prefs) return;
    const seq = beginLlmSwitch();
    if (seq === null) return;
    emitSaved('saving', t('common.saving'));
    const previous = activeLlmProvider;
    try {
      await setActiveLlmProvider(OPENAI_COMPATIBLE_PROVIDER_ID);
      if (!isCurrentLlmSwitch(seq)) return;
      try {
        await updatePrefs({ ...prefs, activeLlmProvider: OPENAI_COMPATIBLE_PROVIDER_ID });
        if (!isCurrentLlmSwitch(seq)) return;
      } catch (error) {
        await setActiveLlmProvider(previous);
        throw error;
      }
      emitSaved('saved', t('common.saved'));
    } catch (error) {
      console.error('[settings] failed to activate OpenAI-compatible LLM provider', error);
      emitSaved('failed', t('common.operationFailed'));
    } finally {
      endLlmSwitch(seq);
    }
  };

  const onAdvancedLlmThinkingToggle = (enabled: boolean) => {
    if (!prefs) return;
    void updatePrefs(current => ({ ...current, llmThinkingEnabled: enabled })).catch(error => {
      console.error('[settings] failed to update LLM thinking mode', error);
      emitSaved('failed', t('common.operationFailed'));
    });
  };

  return (
    <>
      {PRODUCT_FEATURES.showLocalAsrExperiments && (PRODUCT_FEATURES.showQwenLocalAsr || PRODUCT_FEATURES.showFoundryLocalAsr) && pendingTarget && pendingNameKey && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.32)',
            backdropFilter: 'blur(8px)',
            WebkitBackdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 16,
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget && !busy) setPendingTarget(null);
          }}>
          <Card
            style={{
              background: 'rgba(255, 188, 60, 0.12)',
              border: '1px solid rgba(220, 110, 0, 0.55)',
              maxWidth: 360,
              width: '100%',
            }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: '#A04500', marginBottom: 6 }}>
              ⚠️ {t('settings.advanced.confirmEnableLocalTitle')}
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--ol-ink-2)', lineHeight: 1.6, marginBottom: 10 }}>
              {t('settings.advanced.confirmEnableLocalBody', {
                target: t(`settings.providers.presets.${pendingNameKey}`),
              })}
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <Btn variant="ghost" size="sm" disabled={busy} onClick={() => setPendingTarget(null)}>
                {t('common.cancel')}
              </Btn>
              <Btn
                variant="primary"
                size="sm"
                disabled={busy}
                onClick={() => void performSwitch(pendingTarget)}>
                {t('settings.advanced.confirm')}
              </Btn>
            </div>
          </Card>
        </div>
      )}

      <Collapsible
        key={openAiCompatibleActive ? 'openai-compatible-active' : 'openai-compatible-inactive'}
        title={t('settings.advanced.openAiCompatibleTitle')}
        desc={t('settings.advanced.openAiCompatibleDesc')}
        defaultOpen={openAiCompatibleActive}
      >
        {!openAiCompatibleFieldsVisible ? (
          <SettingRow
            label={t('settings.providers.presets.openaiCompatible')}
            desc={t('settings.advanced.openAiCompatibleActivateDesc')}
          >
            <div style={{ display: 'flex', justifyContent: 'flex-end', width: '100%' }}>
              <Btn
                variant="primary"
                size="sm"
                disabled={!prefs || llmSwitching}
                onClick={() => void activateOpenAiCompatibleLlm()}
              >
                {t('settings.advanced.openAiCompatibleActivate')}
              </Btn>
            </div>
          </SettingRow>
        ) : (
          <div style={{ display: 'grid', gap: 10 }}>
            <SettingRow label={t('settings.providers.providerLabel')}>
              <div style={{ display: 'flex', justifyContent: 'flex-end', width: '100%' }}>
                <Pill tone="ok">{t('settings.advanced.openAiCompatibleActive')}</Pill>
              </div>
            </SettingRow>
            <CredentialField
              key="openai-compatible:api_key"
              label={t('settings.providers.apiKeyLabel')}
              account="ark.api_key"
              mono
              mask
              disabled={llmSwitching}
            />
            <CredentialField
              key="openai-compatible:endpoint"
              label={t('settings.providers.baseUrlLabel')}
              account="ark.endpoint"
              placeholder="https://api.openai.com/v1"
              disabled={llmSwitching}
            />
            <CredentialField
              key={`openai-compatible:model:${advancedLlmModelRevision}`}
              label={t('settings.providers.modelLabel')}
              account="ark.model_id"
              placeholder="gpt-4o-mini"
              mono
              trailing={(
                <LlmThinkingToggle
                  enabled={prefs?.llmThinkingEnabled ?? false}
                  onToggle={onAdvancedLlmThinkingToggle}
                  disabled={llmSwitching}
                />
              )}
              disabled={llmSwitching}
            />
            <ProviderTools
              kind="llm"
              modelAccount="ark.model_id"
              onModelSelected={() => setAdvancedLlmModelRevision(v => v + 1)}
              disabled={llmSwitching}
            />
          </div>
        )}
      </Collapsible>

      {/* Deprecated non-product local ASR experiment. Standard product mode keeps this gate false. */}
      {PRODUCT_FEATURES.showLocalAsrExperiments && (PRODUCT_FEATURES.showQwenLocalAsr || PRODUCT_FEATURES.showFoundryLocalAsr) && <Card>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 14 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 500 }}>{t('settings.advanced.localAsrTitle')}</div>
            <div style={{ fontSize: 11.5, color: 'var(--ol-ink-4)', marginTop: 2 }}>
              {t('settings.advanced.localAsrDesc')}
            </div>
          </div>
          <div style={{
            fontSize: 11,
            color: '#A04500',
            fontWeight: 500,
            lineHeight: 1.4,
            textAlign: 'right',
            flexShrink: 0,
            maxWidth: '52%',
            paddingTop: 2,
          }}>
            ⚠️ {t('settings.advanced.localAsrWarningShort')}
          </div>
        </div>

        {!platformSupported ? (
          <div style={{ fontSize: 12.5, color: 'var(--ol-ink-3)', lineHeight: 1.6, padding: '8px 0' }}>
            {t('settings.advanced.platformNotSupported')}
          </div>
        ) : (
          <>
            {PRODUCT_FEATURES.showLocalAsrExperiments && PRODUCT_FEATURES.showQwenLocalAsr && (
              <SettingRow
                label={t('settings.providers.presets.asrLocalQwen3')}
                desc={isMac ? t('settings.advanced.qwen3Desc') : t('settings.advanced.notSupportedHere')}>
                <div style={{ display: 'flex', justifyContent: 'flex-end', width: '100%' }}>
                  <Toggle
                    label={t('settings.providers.presets.asrLocalQwen3')}
                    on={isMac && isOnLocalQwen3}
                    onToggle={isMac && !busy && pendingTarget === null ? (next) => {
                      if (next) requestEnable('local-qwen3');
                      else void performSwitch(LOCAL_ASR_PROVIDER_ID);
                    } : undefined}
                  />
                </div>
              </SettingRow>
            )}

            {PRODUCT_FEATURES.showLocalAsrExperiments && PRODUCT_FEATURES.showFoundryLocalAsr && isWin && (
              <SettingRow
                label={t('settings.providers.presets.asrFoundryLocalWhisper')}
                desc={t('settings.advanced.foundryDesc')}>
                <div style={{ display: 'flex', justifyContent: 'flex-end', width: '100%' }}>
                  <Toggle
                    label={t('settings.providers.presets.asrFoundryLocalWhisper')}
                    on={isOnFoundry}
                    onToggle={!busy && pendingTarget === null ? (next) => {
                      if (next) requestEnable('foundry-local-whisper');
                      else void performSwitch(LOCAL_ASR_PROVIDER_ID);
                    } : undefined}
                  />
                </div>
              </SettingRow>
            )}
          </>
        )}

        {isOnAnyLocal && !(
          (PRODUCT_FEATURES.showLocalAsrExperiments && PRODUCT_FEATURES.showQwenLocalAsr && isMac && isOnLocalQwen3) ||
          (PRODUCT_FEATURES.showLocalAsrExperiments && PRODUCT_FEATURES.showFoundryLocalAsr && isWin && isOnFoundry)
        ) && (
          <SettingRow
            label={t('settings.advanced.disableLocalLabel')}
            desc={t('settings.advanced.disableLocalDesc')}>
            <div style={{ display: 'flex', justifyContent: 'flex-end', width: '100%' }}>
              <Btn
                variant="primary"
                size="sm"
                disabled={busy || pendingTarget !== null}
                onClick={() => void performSwitch(LOCAL_ASR_PROVIDER_ID)}>
                {t('settings.advanced.disable')}
              </Btn>
            </div>
          </SettingRow>
        )}
      </Card>}

    </>
  );
}

type ProviderToolStatus = 'idle' | 'loading' | 'success' | 'empty' | 'error';

function ProviderTools({
  kind,
  modelAccount,
  onModelSelected,
  disabled = false,
}: {
  kind: 'llm' | 'asr';
  modelAccount: string;
  onModelSelected: () => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const [models, setModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [status, setStatus] = useState<ProviderToolStatus>('idle');
  const [message, setMessage] = useState('');
  const controlsDisabled = disabled || status === 'loading';

  const setResult = (next: ProviderToolStatus, nextMessage: string) => {
    setStatus(next);
    setMessage(nextMessage);
  };

  const validate = async () => {
    if (disabled) return;
    setModels([]);
    setSelectedModel('');
    setResult('loading', t('settings.providers.validating'));
    try {
      const result = await validateProviderCredentials(kind);
      setResult(
        result.ok ? 'success' : 'error',
        t(kind === 'asr' ? 'settings.providers.validateAsrSuccess' : 'settings.providers.validateLlmSuccess'),
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if ((kind === 'llm' && message === 'llmModelMissing') || (kind === 'asr' && message === 'asrModelMissing')) {
        setResult('empty', t('settings.providers.modelMissing'));
        return;
      }
      if (message === 'modelsEmpty') {
        setResult('empty', t('settings.providers.modelsEmpty'));
        return;
      }
      setResult('error', providerErrorMessage(error, t));
    }
  };

  const loadModels = async () => {
    if (disabled) return;
    setResult('loading', t('settings.providers.loadingModels'));
    try {
      const result = await listProviderModels(kind);
      setModels(result.models);
      if (result.models.length === 0) {
        setResult('empty', t('settings.providers.modelsEmpty'));
      } else {
        setSelectedModel('');
        setResult('success', t('settings.providers.modelsLoaded', { count: result.models.length }));
      }
    } catch (error) {
      setModels([]);
      setResult('error', providerErrorMessage(error, t));
    }
  };

  const applyModel = async (model: string) => {
    if (disabled) return;
    setResult('loading', t('common.saving'));
    try {
      await setCredential(modelAccount, model);
      setSelectedModel(model);
      onModelSelected();
      setResult('success', t('settings.providers.modelSaved', { model }));
    } catch (error) {
      setResult('error', providerErrorMessage(error, t));
    }
  };

  return (
    <SettingRow label={t('settings.providers.toolsLabel')} desc={t('settings.providers.toolsDesc')}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%', maxWidth: 420 }}>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
          <button onClick={validate} style={miniBtnStyle} disabled={controlsDisabled}>{t('settings.providers.validate')}</button>
          <button onClick={loadModels} style={miniBtnStyle} disabled={controlsDisabled}>{t('settings.providers.fetchModels')}</button>
          {models.length > 0 && (
            <select
              value={selectedModel}
              onChange={e => applyModel(e.target.value)}
              disabled={controlsDisabled}
              style={{ ...inputStyle, maxWidth: 220 }}
            >
              <option value="" disabled>{t('settings.providers.selectModel')}</option>
              {models.map(model => <option key={model} value={model}>{model}</option>)}
            </select>
          )}
        </div>
        {message && (
          <span style={{ fontSize: 11, color: status === 'error' ? 'var(--ol-warn)' : status === 'empty' ? 'var(--ol-ink-4)' : 'var(--ol-ok)', lineHeight: 1.4 }}>
            {message}
          </span>
        )}
      </div>
    </SettingRow>
  );
}


function providerErrorMessage(error: unknown, t: ReturnType<typeof useTranslation>['t']): string {
  const message = error instanceof Error ? error.message : String(error);
  if (message.startsWith('providerHttpStatus:')) {
    return t('settings.providers.providerHttpStatus', { status: message.split(':')[1] || '?' });
  }
  if (message === 'endpointMustUseHttps') return t('settings.providers.endpointMustUseHttps');
  if (message === 'endpointInvalid') return t('settings.providers.endpointInvalid');
  if (message === 'providerResponseTooLarge') return t('settings.providers.responseTooLarge');
  if (message === 'asrInvalidJson') return t('settings.providers.asrInvalidJson');
  if (message === 'asrMissingTextField') return t('settings.providers.asrMissingTextField');
  if (message === 'providerNetworkError') return t('common.networkError');
  if (message === 'providerReadResponseFailed' || message === 'providerClientInitFailed') return t('common.operationFailed');
  if (message === 'providerRequestTimeout') return t('settings.providers.requestTimeout');
  if (message.includes('API Key')) return t('settings.providers.apiKeyMissing');
  if (message.includes('Endpoint')) return t('settings.providers.endpointMissing');
  if (message.includes('timeout') || message.includes('超时')) return t('settings.providers.requestTimeout');
  return t('common.operationFailed');
}

type CredentialFieldStatus = 'idle' | 'saving' | 'saved' | 'readError' | 'saveError' | 'copied' | 'copyError';

interface CredentialFieldProps {
  label: string;
  account: string;
  placeholder?: string;
  mono?: boolean;
  mask?: boolean;
  defaultValue?: string;
  trailing?: ReactNode;
  inline?: boolean;
  disabled?: boolean;
}

function CredentialField({ label, account, placeholder, mono, mask, defaultValue, trailing, inline, disabled: disabledProp = false }: CredentialFieldProps) {
  const { t } = useTranslation();
  const [value, setValue] = useState('');
  const [revealed, setRevealed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [status, setStatus] = useState<CredentialFieldStatus>('idle');
  const debounceRef = useRef<number | null>(null);
  const statusRef = useRef<number | null>(null);
  const disabled = !loaded || disabledProp;
  const disabledRef = useRef(disabled);

  const clearPendingSave = () => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
  };

  useEffect(() => {
    let cancelled = false;
    setLoaded(false);
    setDirty(false);
    setStatus('idle');
    setValue('');
    clearPendingSave();
    readCredential(account)
      .then(v => {
        if (cancelled) return;
        setValue(v ?? '');
        setLoaded(true);
      })
      .catch(error => {
        if (cancelled) return;
        console.error('[settings] failed to read credential', account, error);
        setLoaded(true);
        setStatus('readError');
      });
    return () => {
      cancelled = true;
    };
  }, [account]);

  useEffect(() => {
    disabledRef.current = disabled;
    if (disabled) clearPendingSave();
  }, [disabled]);

  useEffect(() => {
    return () => {
      clearPendingSave();
      if (statusRef.current) clearTimeout(statusRef.current);
    };
  }, []);

  const showTemporaryStatus = (next: CredentialFieldStatus) => {
    if (next === 'saving') {
      emitSaved('saving', t('common.saving'));
    } else if (next === 'saved') {
      emitSaved('saved', t('common.saved'));
    } else if (next === 'saveError') {
      emitSaved('failed', t('common.operationFailed'));
    } else if (next === 'copied') {
      emitSaved('saved', t('common.copied'));
    } else if (next === 'copyError') {
      emitSaved('failed', t('common.operationFailed'));
    }
    setStatus(next);
    if (statusRef.current) clearTimeout(statusRef.current);
    statusRef.current = window.setTimeout(() => setStatus('idle'), 1600);
  };

  const save = async (v: string, force = false) => {
    if (disabledRef.current || !loaded || (!dirty && !force)) return;
    setStatus('saving');
    emitSaved('saving', t('common.saving'));
    try {
      await setCredential(account, v);
      if (disabledRef.current) return;
      setDirty(false);
      showTemporaryStatus('saved');
    } catch (error) {
      if (disabledRef.current) return;
      console.error('[settings] failed to save credential', account, error);
      showTemporaryStatus('saveError');
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (disabledRef.current) return;
    const v = e.target.value;
    setValue(v);
    if (!loaded) return;
    setDirty(true);
    clearPendingSave();
    debounceRef.current = window.setTimeout(() => save(v, true), 300);
  };

  const onBlur = () => {
    if (disabledRef.current || !loaded || !dirty) return;
    clearPendingSave();
    save(value, true);
  };

  const fillDefault = async () => {
    if (disabledRef.current || !loaded || !defaultValue) return;
    setValue(defaultValue);
    setDirty(true);
    await save(defaultValue, true);
  };

  const onCopy = async () => {
    if (disabledRef.current || !value || !loaded) return;
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error('Clipboard API unavailable');
      }
      await navigator.clipboard.writeText(value);
      showTemporaryStatus('copied');
    } catch (error) {
      console.error('[settings] failed to copy credential', account, error);
      showTemporaryStatus('copyError');
    }
  };

  const inputType = mask && !revealed ? 'password' : 'text';

  const control = (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center', width: '100%', maxWidth: inline ? 'none' : 420, minWidth: 0 }}>
        <input
          type={inputType}
          aria-label={label}
          value={value}
          placeholder={loaded ? placeholder : t('common.loading')}
          onChange={handleChange}
          onBlur={onBlur}
          disabled={disabled}
          style={{ ...inputStyle, minWidth: 0, fontFamily: mono ? 'var(--ol-font-mono)' : 'inherit' }}
        />
        {defaultValue && !value && loaded && (
          <button onClick={fillDefault} title={t('settings.providers.fillDefault')} style={iconBtnStyle} disabled={disabled}>
            <Icon name="check" size={13} />
          </button>
        )}
        {trailing}
        {mask && (
          <button
            onClick={() => setRevealed(r => !r)}
            title={revealed ? t('common.hide') : t('common.show')}
            style={iconBtnStyle}
            disabled={disabled}
          >
            <Icon name="eye" size={14} />
          </button>
        )}
        <button
          onClick={onCopy}
          title={t('common.copy')}
          style={iconBtnStyle}
          disabled={!value || disabled}
        >
          <Icon name="copy" size={14} />
        </button>
        {status === 'readError' && (
          <span
            style={{
              fontSize: 11,
              color: 'var(--ol-warn)',
              whiteSpace: 'nowrap',
            }}
          >
            {t('settings.providers.readFailed')}
          </span>
        )}
      </div>
  );

  if (inline) {
    return control;
  }

  return (
    <SettingRow label={label}>
      {control}
    </SettingRow>
  );
}

const inputStyle: CSSProperties = {
  flex: 1, height: 32, padding: '0 10px',
  border: '0.5px solid var(--ol-line-strong)',
  borderRadius: 8, fontSize: 12.5,
  fontFamily: 'inherit', outline: 'none',
  background: 'var(--ol-surface-2)',
  width: '100%', maxWidth: 360,
  transition: 'background 0.16s var(--ol-motion-quick), border-color 0.16s var(--ol-motion-quick)',
};
const miniBtnStyle: CSSProperties = {
  height: 32, padding: '0 10px',
  border: '0.5px solid var(--ol-line-strong)',
  borderRadius: 8, background: 'var(--ol-surface)',
  color: 'var(--ol-ink-2)', cursor: 'default', flexShrink: 0,
  fontSize: 12, fontWeight: 500,
  transition: 'background 0.16s var(--ol-motion-quick), border-color 0.16s var(--ol-motion-quick), color 0.16s var(--ol-motion-quick)',
};

const recordingHotkeyControlWidth = 178;

const hotkeyRecorderButtonStyle: CSSProperties = {
  width: recordingHotkeyControlWidth,
  height: 32,
  padding: '0 8px 0 11px',
  border: '0.5px solid var(--ol-line-strong)',
  borderRadius: 8,
  background: 'var(--ol-surface-2)',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 8,
  fontFamily: 'var(--ol-font-mono)',
  fontSize: 12.5,
  cursor: 'default',
  transition: 'background 0.16s var(--ol-motion-quick), border-color 0.16s var(--ol-motion-quick), color 0.16s var(--ol-motion-quick)',
};

const recordingHotkeySegmentedStyle: CSSProperties = {
  width: recordingHotkeyControlWidth,
  display: 'inline-flex',
  padding: 2,
  borderRadius: 8,
  background: 'rgba(0,0,0,0.05)',
};

const recordingHotkeyGroupStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'auto',
  rowGap: 10,
  justifyItems: 'start',
};

const recordingHotkeyLineStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: '64px auto',
  alignItems: 'center',
  columnGap: 10,
};

const recordingHotkeyFieldLabelStyle: CSSProperties = {
  fontSize: 12,
  color: 'var(--ol-ink-4)',
  textAlign: 'right',
  whiteSpace: 'nowrap',
};

const recordingHotkeyStatusStyle: CSSProperties = {
  marginLeft: 74,
  fontSize: 12,
  lineHeight: 1.3,
};

const hotkeyRecorderLabelStyle: CSSProperties = {
  minWidth: 0,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

const hotkeyClearButtonStyle: CSSProperties = {
  width: 18,
  height: 18,
  borderRadius: 999,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
  background: 'rgba(0,0,0,0.2)',
  color: '#fff',
};

const iconBtnStyle: CSSProperties = {
  width: 32, height: 32,
  border: '0.5px solid var(--ol-line-strong)',
  borderRadius: 8, background: 'var(--ol-surface)',
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  color: 'var(--ol-ink-3)', cursor: 'default', flexShrink: 0,
  transition: 'background 0.16s var(--ol-motion-quick), border-color 0.16s var(--ol-motion-quick), color 0.16s var(--ol-motion-quick)',
};

function ShortcutsSection() {
  const { t } = useTranslation();
  const { prefs, hotkey, capability, updatePrefs: savePrefs } = useHotkeySettings();

  if (!prefs || !hotkey || !capability) {
    return (
      <Card>
        <div style={{ fontSize: 12, color: 'var(--ol-ink-4)' }}>{t('common.loading')}</div>
      </Card>
    );
  }

  const desc = capability.requiresAccessibilityPermission
    ? t('settings.shortcuts.descAcc')
    : t('settings.shortcuts.descNoAcc');
  const readonlyRows: Array<[string, string]> = [
    [t('settings.shortcuts.cancel'), 'Esc'],
    [t('settings.shortcuts.confirm'), t('settings.shortcuts.confirmHint')],
  ];
  return (
    <Card>
      <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{t('settings.shortcuts.title')}</div>
      <div style={{ fontSize: 11.5, color: 'var(--ol-ink-4)', marginBottom: 6 }}>{desc}</div>
      <SettingRow label={t('settings.shortcuts.startStop')}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, width: '100%' }}>
          <ShortcutRecorder
            value={prefs.dictationHotkey}
            alignRecordButton
            onSave={async binding => {
              await setDictationHotkey(binding);
              await savePrefs({ ...prefs, dictationHotkey: binding });
            }}
          />
          <div style={{ fontSize: 11, color: 'var(--ol-ink-4)' }}>
            {hotkey.mode === 'hold' ? t('hotkey.modeHoldSuffix') : t('hotkey.modeToggleSuffix')}
          </div>
        </div>
      </SettingRow>
      {PRODUCT_FEATURES.showTranslationTab && (
        <SettingRow label={t('translation.hotkey.title', 'Translation shortcut')}>
          <ShortcutRecorder
            value={prefs.translationHotkey}
            alignRecordButton
            onSave={async binding => {
              await setTranslationHotkey(binding);
              await savePrefs({ ...prefs, translationHotkey: binding });
            }}
          />
        </SettingRow>
      )}
      {PRODUCT_FEATURES.showSelectionAskTab && (
        <SettingRow label={t('selectionAsk.hotkey.title')}>
          {prefs.qaHotkey ? (
          <ShortcutRecorder
            value={prefs.qaHotkey}
            alignRecordButton
            onSave={async binding => {
              await setQaHotkey(binding);
              await savePrefs({ ...prefs, qaHotkey: binding });
            }}
          />
          ) : (
            <button
              onClick={async () => {
                const binding = defaultQaShortcut();
                await setQaHotkey(binding);
                await savePrefs({ ...prefs, qaHotkey: binding });
              }}
              style={{ fontSize: 12, padding: '5px 14px', background: 'var(--ol-blue)', color: '#fff', border: 0, borderRadius: 6, fontFamily: 'inherit', fontWeight: 500, cursor: 'default' }}
            >
              {t('selectionAsk.hotkey.enable', 'Enable')}
            </button>
          )}
        </SettingRow>
      )}
      <SettingRow label={t('settings.shortcuts.switchStyle')}>
        <ShortcutRecorder
          value={prefs.switchStyleHotkey}
          alignRecordButton
          onSave={async binding => {
            await setSwitchStyleHotkey(binding);
            await savePrefs({ ...prefs, switchStyleHotkey: binding });
          }}
        />
      </SettingRow>
      <SettingRow label={t('settings.shortcuts.openApp')}>
        <ShortcutRecorder
          value={prefs.openAppHotkey}
          alignRecordButton
          onSave={async binding => {
            await setOpenAppHotkey(binding);
            await savePrefs({ ...prefs, openAppHotkey: binding });
          }}
        />
      </SettingRow>
      {readonlyRows.map(([k, v]) => (
        <SettingRow key={k} label={k}>
          <kbd style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            padding: '4px 10px', fontSize: 12, fontFamily: 'var(--ol-font-mono)',
            borderRadius: 6, background: 'var(--ol-surface-2)',
            border: '0.5px solid var(--ol-line-strong)',
            boxShadow: '0 1px 0 rgba(0,0,0,0.04)',
            color: 'var(--ol-ink-2)',
          }}>{v}</kbd>
        </SettingRow>
      ))}
    </Card>
  );
}

function PermissionsSection() {
  const { t } = useTranslation();
  const [accessibility, setAccessibility] = useState<PermissionStatus | 'loading'>('loading');
  const [microphone, setMicrophone] = useState<PermissionStatus | 'loading'>('loading');
  const [hotkey, setHotkey] = useState<HotkeyStatus | null>(null);
  const [windowsIme, setWindowsIme] = useState<WindowsImeStatus | null>(null);
  const { capability } = useHotkeySettings();

  const refreshPermissions = async () => {
    const [a, m] = await Promise.all([
      checkAccessibilityPermission(),
      checkMicrophonePermission(),
    ]);
    setAccessibility(a);
    setMicrophone(m);
  };

  const refreshHotkey = async () => {
    setHotkey(await getHotkeyStatus());
  };

  const refreshWindowsIme = async () => {
    setWindowsIme(await getWindowsImeStatus());
  };

  useEffect(() => {
    refreshPermissions();
    refreshHotkey();
    refreshWindowsIme();
    const hotkeyId = window.setInterval(refreshHotkey, 1000);
    const permissionId = window.setInterval(refreshPermissions, 10000);
    const onFocus = () => {
      refreshPermissions();
      refreshHotkey();
      refreshWindowsIme();
    };
    window.addEventListener('focus', onFocus);
    return () => {
      window.clearInterval(hotkeyId);
      window.clearInterval(permissionId);
      window.removeEventListener('focus', onFocus);
    };
  }, []);

  const reRequestAccessibility = async () => {
    await requestAccessibilityPermission();
    refreshPermissions();
  };

  const reRequestMicrophone = async () => {
    if (microphone === 'denied' || microphone === 'restricted') {
      await openSystemSettings('microphone');
      refreshPermissions();
      return;
    }
    const status = await requestMicrophonePermission();
    setMicrophone(status);
    if (status === 'denied' || status === 'restricted') {
      await openSystemSettings('microphone');
    }
    refreshPermissions();
  };

  const desc = capability?.requiresAccessibilityPermission
    ? t('settings.permissions.descAcc')
    : t('settings.permissions.descNoAcc');

  return (
    <Card>
      <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{t('settings.permissions.title')}</div>
      <div style={{ fontSize: 11.5, color: 'var(--ol-ink-4)', marginBottom: 6 }}>
        {desc}
      </div>
      <SettingRow label={t('settings.permissions.micLabel')} desc={t('settings.permissions.micDesc')}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'flex-end', width: '100%' }}>
          <PermissionPill status={microphone} />
          {microphone !== 'granted' && microphone !== 'notApplicable' && microphone !== 'loading' && (
            <Btn variant="ghost" size="sm" onClick={reRequestMicrophone}>
              {microphone === 'denied' || microphone === 'restricted' ? t('settings.permissions.openSystem') : t('settings.permissions.grant')}
            </Btn>
          )}
        </div>
      </SettingRow>
      {capability?.requiresAccessibilityPermission && (
        <SettingRow label={t('settings.permissions.accLabel')} desc={t('settings.permissions.accDesc')}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <PermissionPill status={accessibility} />
            {accessibility !== 'granted' && accessibility !== 'notApplicable' && (
              <Btn variant="ghost" size="sm" onClick={reRequestAccessibility}>
                {t('settings.permissions.grant')}
              </Btn>
            )}
          </div>
        </SettingRow>
      )}
      <SettingRow
        label={t('settings.permissions.hotkeyLabel')}
        desc={capability ? t('settings.permissions.hotkeyDescWithAdapter', { adapter: adapterDisplayName(capability.adapter) }) : t('settings.permissions.hotkeyDescPlain')}
      >
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', minWidth: 0, justifyContent: 'flex-end', width: '100%' }}>
          {hotkey?.message && (
            <span style={{ fontSize: 11.5, color: 'var(--ol-ink-4)', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {hotkey.message}
            </span>
          )}
          <HotkeyStatusPill status={hotkey} />
        </div>
      </SettingRow>
      {PRODUCT_FEATURES.showTsfImeSettings && windowsIme?.state !== 'notWindows' && (
        <SettingRow
          label={t('settings.permissions.windowsImeLabel')}
          desc={t('settings.permissions.windowsImeDesc')}
        >
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', minWidth: 0, justifyContent: 'flex-end', width: '100%' }}>
            {windowsIme && (
              <span style={{ fontSize: 11.5, color: 'var(--ol-ink-4)', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {t(`settings.permissions.windowsIme.${windowsIme.state}`)}
              </span>
            )}
            <WindowsImeStatusPill status={windowsIme} />
          </div>
        </SettingRow>
      )}
      <SettingRow label={t('settings.permissions.networkLabel')} desc={t('settings.permissions.networkDesc')}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', width: '100%' }}>
          <Pill tone="ok"><Icon name="check" size={11} />{t('settings.permissions.networkOk')}</Pill>
        </div>
      </SettingRow>
    </Card>
  );
}

function PermissionPill({ status }: { status: PermissionStatus | 'loading' }) {
  const { t } = useTranslation();
  if (status === 'loading') {
    return <Pill tone="default">{t('settings.permissions.checking')}</Pill>;
  }
  if (status === 'granted') {
    return <Pill tone="ok"><Icon name="check" size={11} />{t('settings.permissions.granted')}</Pill>;
  }
  if (status === 'notApplicable') {
    return <Pill tone="default">{t('settings.permissions.notApplicable')}</Pill>;
  }
  if (status === 'denied' || status === 'restricted') {
    return <Pill tone="outline">{t('settings.permissions.denied')}</Pill>;
  }
  return <Pill tone="outline">{t('settings.permissions.indeterminate')}</Pill>;
}

function LanguageSection() {
  const { t } = useTranslation();
  const { prefs, updatePrefs } = useHotkeySettings();
  const [pref, setPref] = useState<SupportedLocale | typeof FOLLOW_SYSTEM>(getLocalePreference());
  const visibleLocaleOptions = settingsVisibleLocaleOptions();
  const visibleOutputLanguageOptions = settingsVisibleOutputLanguageOptions();
  const visibleLocalePref = pref === 'en' ? 'en' : 'zh-CN';

  const apply = async (next: (typeof visibleLocaleOptions)[number]) => {
    setPref(next);
    await setLocalePreference(next);
    const localePrefs = outputPrefsPatchForUiLanguageChange();
    if (!localePrefs) return;
    await updatePrefs(current => {
      if (
        current.chineseScriptPreference === localePrefs.chineseScriptPreference &&
        current.outputLanguagePreference === localePrefs.outputLanguagePreference
      ) {
        return current;
      }
      return { ...current, ...localePrefs };
    });
  };

  const outputLanguagePreference = getOutputLanguagePreference(prefs) === 'en' ? 'en' : 'zhCn';
  const applyOutputLanguage = async (next: (typeof visibleOutputLanguageOptions)[number]) => {
    const outputPrefs = setOutputLanguagePreference(next);
    await updatePrefs(current => {
      if (
        current.chineseScriptPreference === outputPrefs.chineseScriptPreference &&
        current.outputLanguagePreference === outputPrefs.outputLanguagePreference
      ) {
        return current;
      }
      return { ...current, ...outputPrefs };
    });
  };

  return (
    <Card>
      <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{t('settings.language.title')}</div>
      <div style={{ fontSize: 11.5, color: 'var(--ol-ink-4)', marginBottom: 6 }}>{t('settings.language.desc')}</div>
      <SettingRow label={t('settings.language.label')} desc={t('settings.language.labelDesc')}>
        <select
          value={visibleLocalePref}
          onChange={e => apply(e.target.value as (typeof visibleLocaleOptions)[number])}
          style={{ ...inputStyle, maxWidth: 220 }}
        >
          {visibleLocaleOptions.map(locale => (
            <option key={locale} value={locale}>
              {locale === 'zh-CN' ? t('settings.language.zh') : t('settings.language.en')}
            </option>
          ))}
        </select>
      </SettingRow>
      <SettingRow label={t('settings.language.outputLabel')} desc={t('settings.language.outputDesc')}>
        <select
          value={outputLanguagePreference}
          onChange={e => applyOutputLanguage(e.target.value as (typeof visibleOutputLanguageOptions)[number])}
          disabled={!prefs}
          style={{ ...inputStyle, maxWidth: 220 }}
        >
          {visibleOutputLanguageOptions.map(language => (
            <option key={language} value={language}>
              {language === 'zhCn' ? t('settings.language.outputZhCn') : t('settings.language.outputEn')}
            </option>
          ))}
        </select>
      </SettingRow>
      <div style={{ fontSize: 11, color: 'var(--ol-ink-4)', marginTop: 8, lineHeight: 1.6 }}>
        {t('settings.language.restartHint')}
      </div>
    </Card>
  );
}

function AboutSection() {
  const { t } = useTranslation();
  const repoUrl = 'https://github.com/EthanYoQ/whisper-input';
  const openAboutLink = (url: string) => {
    void openExternal(url).catch(error => {
      console.error('[settings] failed to open about link', url, error);
    });
  };

  return (
    <Card>
      <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{t('settings.about.title')}</div>
      <div style={{ fontSize: 11.5, color: 'var(--ol-ink-4)', marginBottom: 6 }}>{t('settings.about.desc')}</div>
      <SettingRow label={t('settings.about.websiteLabel')} desc={t('settings.about.websiteDesc')}>
        <button style={miniBtnStyle} onClick={() => openAboutLink(repoUrl)}>
          {t('settings.about.websiteBtn')}
        </button>
      </SettingRow>
      <SettingRow label={t('settings.about.docs')} desc={t('settings.about.websiteDesc')}>
        <button style={miniBtnStyle} onClick={() => openAboutLink(`${repoUrl}#readme`)}>
          {t('settings.about.docs')}
        </button>
      </SettingRow>
      <SettingRow label={t('settings.about.githubStarLabel')} desc={t('settings.about.githubStarDesc')}>
        <button style={miniBtnStyle} onClick={() => openAboutLink(repoUrl)}>
          {t('settings.about.githubStarBtn')}
        </button>
      </SettingRow>
      <SettingRow label={t('settings.about.feedbackLabel')} desc={t('settings.about.feedbackDesc')}>
        <button style={miniBtnStyle} onClick={() => openAboutLink(`${repoUrl}/issues`)}>
          {t('settings.about.feedbackBtn')}
        </button>
      </SettingRow>
    </Card>
  );
}

export function AboutUpdateControl({ tagline }: { tagline: string }) {
  const { t } = useTranslation();
  const u = useAutoUpdate();
  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
        <span style={{ fontSize: 12, color: 'var(--ol-ink-3)' }}>{tagline} · {APP_VERSION_LABEL}</span>
        <Btn variant="ghost" size="sm" onClick={u.checkForUpdates} disabled={u.checking || u.busy}>
          {u.checking ? t('settings.about.checkingUpdate') : t('settings.about.checkUpdateBtn')}
        </Btn>
      </div>
      {(u.status === 'none' || u.status === 'error') && (
        <div style={{ fontSize: 11, color: u.status === 'error' ? 'var(--ol-err)' : 'var(--ol-ink-4)', marginTop: 4 }}>
          {u.status === 'none' ? t('settings.about.upToDate') : t('settings.about.updateError')}
        </div>
      )}
      {isDialogStatus(u.status) && (
        <UpdateDialog
          status={u.status}
          version={u.version}
          progress={u.progress}
          downloaded={u.downloaded}
          contentLength={u.contentLength}
          onInstall={u.installUpdate}
          onClose={u.dismissDialog}
        />
      )}
    </>
  );
}

function HotkeyStatusPill({ status }: { status: HotkeyStatus | null }) {
  const { t } = useTranslation();
  if (!status) {
    return <Pill tone="default">{t('settings.permissions.checking')}</Pill>;
  }
  if (status.state === 'installed') {
    return <Pill tone="ok"><Icon name="check" size={11} />{t('settings.permissions.hotkeyInstalled')}</Pill>;
  }
  if (status.state === 'starting') {
    return <Pill tone="default">{t('settings.permissions.hotkeyStarting')}</Pill>;
  }
  return <Pill tone="outline">{t('settings.permissions.hotkeyFailed')}</Pill>;
}

function WindowsImeStatusPill({ status }: { status: WindowsImeStatus | null }) {
  const { t } = useTranslation();
  if (!status) {
    return <Pill tone="default">{t('settings.permissions.checking')}</Pill>;
  }
  if (status.state === 'installed') {
    return <Pill tone="ok"><Icon name="check" size={11} />{t('settings.permissions.windowsImeInstalled')}</Pill>;
  }
  return <Pill tone="outline">{t('settings.permissions.windowsImeUnavailable')}</Pill>;
}

function adapterDisplayName(adapter: HotkeyCapability['adapter'] | HotkeyStatus['adapter']) {
  if (adapter === 'macEventTap') return i18n.t('hotkey.adapter.macEventTap');
  if (adapter === 'windowsLowLevel') return i18n.t('hotkey.adapter.windowsLowLevel');
  return i18n.t('hotkey.adapter.rdev');
}
