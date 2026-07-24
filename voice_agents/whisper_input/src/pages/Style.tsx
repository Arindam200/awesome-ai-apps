// Style.tsx — 接 getSettings / setDefaultPolishMode / setStyleEnabled。
// defaultMode 来自 prefs.defaultMode，启停从 prefs.enabledModes 反推。

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Icon } from '../components/Icon';
import { getSettings, setDefaultPolishMode, setStyleEnabled, setSettings } from '../lib/ipc';
import type { PolishMode, UserPreferences } from '../lib/types';
import {
  PreviewButton,
  PreviewCard,
  PreviewPageHeader,
  PreviewPill,
} from '../components/preview/PreviewPrimitives';
import {
  applyStylePreferencesNotification,
  isStyleMasterEnabled,
  persistStylePreferenceChange,
  rollbackDefaultAndEnabledChange,
  rollbackDefaultModeChange,
  rollbackStyleEnabledChange,
  rollbackWholeStylePreferences,
  styleDefaultModePreferences,
  styleMasterOffPreferences,
  styleSaveErrorMessage,
} from '../lib/stylePrefs';
import { useHotkeySettings } from '../state/HotkeySettingsContext';

interface StyleDef {
  id: PolishMode;
  name: string;
  desc: string;
  sample: string;
}

const STYLE_IDS: PolishMode[] = ['raw', 'light', 'structured', 'formal'];
type StyleSaveErrorTarget = PolishMode | 'master';

function joinClassNames(...classes: Array<string | false | undefined>) {
  return classes.filter(Boolean).join(' ');
}

export function Style() {
  const { t } = useTranslation();
  const { prefs: sharedPrefs } = useHotkeySettings();
  const STYLES: StyleDef[] = STYLE_IDS.map(id => ({
    id,
    name: t(`style.modes.${id}.name`),
    desc: t(`style.modes.${id}.desc`),
    sample: t(`style.modes.${id}.sample`),
  }));
  const [prefs, setPrefs] = useState<UserPreferences | null>(null);
  const [settingsLoadError, setSettingsLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<{ target: StyleSaveErrorTarget; message: string } | null>(null);

  const loadSettings = async () => {
    setSettingsLoadError(null);
    try {
      const nextPrefs = await getSettings();
      setPrefs(nextPrefs);
    } catch (error) {
      setPrefs(null);
      setSettingsLoadError(styleSaveErrorMessage(error));
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setSettingsLoadError(null);
      try {
        const nextPrefs = await getSettings();
        if (!cancelled) setPrefs(nextPrefs);
      } catch (error) {
        if (!cancelled) {
          setPrefs(null);
          setSettingsLoadError(styleSaveErrorMessage(error));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!sharedPrefs) return;
    setPrefs(current => applyStylePreferencesNotification(current, sharedPrefs));
    setSettingsLoadError(null);
    setSaveError(null);
  }, [sharedPrefs]);

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    let cancelled = false;
    (async () => {
      try {
        const { listen } = await import('@tauri-apps/api/event');
        unlisten = await listen<UserPreferences>('prefs:changed', event => {
          setPrefs(current => applyStylePreferencesNotification(current, event.payload));
          setSaveError(null);
        });
        if (cancelled && unlisten) unlisten();
      } catch (error) {
        console.warn('[style] prefs:changed listener setup failed', error);
      }
    })();
    return () => {
      cancelled = true;
      if (unlisten) unlisten();
    };
  }, []);

  const showSaveError = (target: StyleSaveErrorTarget, error: string) => {
    setSaveError({ target, message: t('style.saveFailed', { error }) });
  };

  const onPickDefault = async (mode: PolishMode) => {
    if (!prefs) return;
    const masterWasEnabled = isStyleMasterEnabled(prefs);
    const modeWasEnabled = prefs.enabledModes.includes(mode);
    const next = styleDefaultModePreferences(prefs, mode);
    const shouldSaveWholePrefs = !masterWasEnabled || !modeWasEnabled;
    const saved = await persistStylePreferenceChange(
      next,
      () => (shouldSaveWholePrefs ? setSettings(next) : setDefaultPolishMode(mode)),
      setPrefs,
      error => showSaveError(mode, error),
      !shouldSaveWholePrefs
        ? rollbackDefaultModeChange(prefs, next)
        : rollbackDefaultAndEnabledChange(prefs, next),
    );
    if (saved) setSaveError(null);
  };

  const onToggleEnabled = async (mode: PolishMode) => {
    if (!prefs) return;
    const enabled = !prefs.enabledModes.includes(mode);
    const nextEnabled = enabled
      ? [...prefs.enabledModes, mode]
      : prefs.enabledModes.filter(m => m !== mode);
    const next = { ...prefs, enabledModes: nextEnabled };
    const saved = await persistStylePreferenceChange(
      next,
      () => setStyleEnabled(mode, enabled),
      setPrefs,
      error => showSaveError(mode, error),
      rollbackStyleEnabledChange(mode, prefs, next),
    );
    if (saved) setSaveError(null);
  };

  if (!prefs) {
    return (
      <div className="wi-style-page">
        <PreviewPageHeader
          title={t('style.title')}
          desc={settingsLoadError ? t('common.settingsLoadFailed') : t('common.loading')}
        />
        {settingsLoadError && (
          <PreviewCard className="wi-style-load-error">
            <div role="alert" className="wi-style-error">
              {settingsLoadError}
            </div>
            <PreviewButton onClick={() => void loadSettings()}>{t('common.retry')}</PreviewButton>
          </PreviewCard>
        )}
      </div>
    );
  }

  const masterEnabled = isStyleMasterEnabled(prefs);

  const onMasterToggle = async () => {
    if (!prefs) return;
    if (masterEnabled) {
      // 全部关闭 → 留 raw 和当前 default 兜底，避免持久化空集合。
      const next = styleMasterOffPreferences(prefs);
      const saved = await persistStylePreferenceChange(
        next,
        () => setSettings(next),
        setPrefs,
        error => showSaveError('master', error),
        rollbackWholeStylePreferences(prefs, next),
      );
      if (saved) setSaveError(null);
    } else {
      const next = { ...prefs, enabledModes: ['raw', 'light', 'structured', 'formal'] as PolishMode[] };
      const saved = await persistStylePreferenceChange(
        next,
        () => setSettings(next),
        setPrefs,
        error => showSaveError('master', error),
        rollbackWholeStylePreferences(prefs, next),
      );
      if (saved) setSaveError(null);
    }
  };

  return (
    <div className="wi-style-page">
      <PreviewPageHeader
        title={t('style.title')}
        desc={
          <span className="wi-style-header-row">
            <span>{t('style.desc')}</span>
            <span className="wi-style-master">
              <span className="wi-style-master-label">{t('style.masterToggle')}</span>
              <button
                type="button"
                onClick={onMasterToggle}
                className={joinClassNames('wi-style-toggle', masterEnabled && 'wi-style-toggle-on')}
                role="switch"
                aria-checked={masterEnabled}
                aria-label={t('style.masterToggle')}
              >
                <span />
              </button>
              {saveError?.target === 'master' && (
                <span role="alert" className="wi-style-error wi-style-error-inline">
                  {saveError.message}
                </span>
              )}
            </span>
          </span>
        }
      />
      <div className="wi-style-grid">
        {STYLES.map(s => {
          const isDefault = prefs.defaultMode === s.id;
          const isEnabled = prefs.enabledModes.includes(s.id);
          return (
            <PreviewCard
              key={s.id}
              className={joinClassNames(
                'wi-style-card',
                isDefault && 'wi-style-card-default',
                !isEnabled && 'wi-style-card-disabled',
              )}
            >
              <div className="wi-style-card-head">
                <div className="wi-style-title-block">
                  <div className="wi-style-name-row">
                    <button
                      type="button"
                      onClick={() => onPickDefault(s.id)}
                      className={joinClassNames('wi-style-radio', isDefault && 'wi-style-radio-on')}
                      aria-label={t('style.ariaSetDefault')}
                    >
                      {isDefault && (
                        <Icon name="check" size={10} strokeWidth={2} />
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => onPickDefault(s.id)}
                      className="wi-style-name"
                    >
                      {s.name}
                    </button>
                  </div>
                  <p className="wi-style-desc">{s.desc}</p>
                </div>
                <div className="wi-style-actions">
                  {isDefault ? (
                    <PreviewPill tone="blue">{t('style.currentDefault')}</PreviewPill>
                  ) : (
                    <PreviewButton onClick={() => onPickDefault(s.id)}>
                      {t('style.ariaSetDefault')}
                    </PreviewButton>
                  )}
                  {!isDefault && (
                  <button
                    type="button"
                    onClick={() => onToggleEnabled(s.id)}
                    className={joinClassNames('wi-style-toggle', isEnabled && 'wi-style-toggle-on')}
                    role="switch"
                    aria-checked={isEnabled}
                    aria-label={s.name}
                  >
                    <span />
                  </button>
                  )}
                </div>
              </div>
              <div className="wi-style-sample">
                {s.sample}
              </div>
              {saveError?.target === s.id && (
                <div role="alert" className="wi-style-error">
                  {saveError.message}
                </div>
              )}
            </PreviewCard>
          );
        })}
      </div>
    </div>
  );
}
