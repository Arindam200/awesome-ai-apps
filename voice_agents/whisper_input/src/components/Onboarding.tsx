// Onboarding.tsx — productized first-run setup for Whisper Input.

import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import {
  checkAccessibilityPermission,
  checkMicrophonePermission,
  openSystemSettings,
  requestAccessibilityPermission,
  requestMicrophonePermission,
} from '../lib/ipc';
import { formatComboLabel } from '../lib/hotkey';
import type { PermissionStatus } from '../lib/types';
import { useHotkeySettings } from '../state/HotkeySettingsContext';
import type { SettingsSectionId } from '../pages/Settings';

interface OnboardingProps {
  onComplete: () => void;
  onOpenSettings?: (section: SettingsSectionId) => void;
}

export function Onboarding({ onComplete, onOpenSettings }: OnboardingProps) {
  const { t } = useTranslation();
  const [step, setStep] = useState(0);
  const [accessibility, setAccessibility] = useState<PermissionStatus>('notDetermined');
  const [microphone, setMicrophone] = useState<PermissionStatus>('notDetermined');
  const [busy, setBusy] = useState(false);
  const refreshTimeoutRef = useRef<number | null>(null);
  const mountedRef = useRef(false);
  const permissionSeqRef = useRef(0);
  const { capability, prefs } = useHotkeySettings();

  const refreshPermissions = useCallback(async () => {
    const seq = ++permissionSeqRef.current;
    const [a, m] = await Promise.all([
      checkAccessibilityPermission(),
      checkMicrophonePermission(),
    ]);
    if (mountedRef.current && seq === permissionSeqRef.current) {
      setAccessibility(a);
      setMicrophone(m);
    }
    return { accessibility: a, microphone: m };
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void refreshPermissions();
    const id = window.setInterval(refreshPermissions, 1000);
    const onFocus = () => {
      void refreshPermissions();
    };
    window.addEventListener('focus', onFocus);
    return () => {
      window.clearInterval(id);
      window.removeEventListener('focus', onFocus);
      if (refreshTimeoutRef.current) clearTimeout(refreshTimeoutRef.current);
      mountedRef.current = false;
      permissionSeqRef.current += 1;
    };
  }, [refreshPermissions]);

  const capabilityLoaded = capability !== null;
  const requiresAccessibility = capability?.requiresAccessibilityPermission === true;
  const accessibilityOk = capabilityLoaded && (!requiresAccessibility || accessibility === 'granted' || accessibility === 'notApplicable');
  const microphoneOk = microphone === 'granted' || microphone === 'notApplicable';
  const permissionsOk = capabilityLoaded && accessibilityOk && microphoneOk;
  const hotkeyLabel = prefs ? formatComboLabel(prefs.dictationHotkey) : t('hotkey.fallback');
  const hotkeyUsage = prefs?.hotkey.mode === 'hold'
    ? t('onboarding.steps.hotkey.usageHold', { hotkey: hotkeyLabel })
    : t('onboarding.steps.hotkey.usageToggle', { hotkey: hotkeyLabel });

  const onGrantAccessibility = async () => {
    setBusy(true);
    try {
      await requestAccessibilityPermission();
      await openSystemSettings('accessibility');
    } finally {
      if (mountedRef.current) setBusy(false);
    }
  };

  const onRequestMicrophone = async () => {
    setBusy(true);
    try {
      if (microphone === 'denied' || microphone === 'restricted') {
        await openSystemSettings('microphone');
      } else {
        const status = await requestMicrophonePermission();
        if (mountedRef.current) setMicrophone(status);
        if (status === 'denied' || status === 'restricted') {
          await openSystemSettings('microphone');
        }
      }
    } finally {
      if (mountedRef.current) setBusy(false);
    }
    if (refreshTimeoutRef.current) clearTimeout(refreshTimeoutRef.current);
    refreshTimeoutRef.current = window.setTimeout(() => {
      void refreshPermissions();
    }, 800);
  };

  const finish = async () => {
    if (!capabilityLoaded) {
      setStep(1);
      return;
    }
    const next = await refreshPermissions();
    const canComplete =
      capabilityLoaded &&
      (!requiresAccessibility || next.accessibility === 'granted' || next.accessibility === 'notApplicable') &&
      (next.microphone === 'granted' || next.microphone === 'notApplicable');
    if (mountedRef.current && canComplete) {
      onComplete();
      return;
    }
    if (mountedRef.current) setStep(1);
  };

  const openSettings = (section: SettingsSectionId) => {
    if (onOpenSettings) {
      onOpenSettings(section);
      return;
    }
    onComplete();
  };

  const steps = [
    {
      title: t('onboarding.steps.intro.title'),
      body: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <p style={copyStyle}>{t('onboarding.steps.intro.body')}</p>
          <div style={noteStyle}>{t('onboarding.steps.intro.privacy')}</div>
        </div>
      ),
    },
    {
      title: t('onboarding.steps.microphone.title'),
      body: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <PermissionRow
            label={t('onboarding.steps.microphone.micLabel')}
            desc={t('onboarding.steps.microphone.micDesc')}
            status={microphone}
            actionLabel={microphoneOk ? t('onboarding.actionGranted') : microphone === 'denied' || microphone === 'restricted' ? t('onboarding.actionOpenSystem') : t('onboarding.actionRequestMic')}
            disabled={busy || microphoneOk}
            onAction={onRequestMicrophone}
          />
          {requiresAccessibility && (
            <PermissionRow
              label={t('onboarding.steps.microphone.accessibilityLabel')}
              desc={t('onboarding.steps.microphone.accessibilityDesc')}
              status={accessibility}
              actionLabel={accessibilityOk ? t('onboarding.actionGranted') : accessibility === 'denied' || accessibility === 'restricted' ? t('onboarding.actionOpenSystem') : t('onboarding.actionGrant')}
              disabled={busy || accessibilityOk}
              onAction={onGrantAccessibility}
            />
          )}
          {!capabilityLoaded && (
            <div style={noteStyle}>{t('common.loading')}</div>
          )}
          {requiresAccessibility && (
            <div style={noteStyle}>{t('onboarding.steps.microphone.restartHint')}</div>
          )}
        </div>
      ),
    },
    {
      key: 'asr',
      title: t('onboarding.steps.asr.title'),
      body: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <p style={copyStyle}>{t('onboarding.steps.asr.body')}</p>
          <div style={noteStyle}>{t('onboarding.steps.asr.cloudNotice')}</div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
            <button style={primaryButtonStyle} onClick={() => openSettings('models')}>
              {t('onboarding.steps.asr.configure')}
            </button>
          </div>
        </div>
      ),
    },
    {
      key: 'llm',
      title: t('onboarding.steps.llm.title'),
      body: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <p style={copyStyle}>{t('onboarding.steps.llm.body')}</p>
          <div style={noteStyle}>{t('onboarding.steps.llm.geminiNotice')}</div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
            <button style={primaryButtonStyle} onClick={() => openSettings('models')}>
              {t('onboarding.steps.llm.configure')}
            </button>
          </div>
        </div>
      ),
    },
    {
      title: t('onboarding.steps.hotkey.title'),
      body: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ ...noteStyle, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <span>{t('onboarding.steps.hotkey.current')}</span>
            <kbd style={{ fontFamily: 'var(--ol-font-mono)', fontSize: 12, color: 'var(--ol-ink)', whiteSpace: 'nowrap' }}>{hotkeyLabel}</kbd>
          </div>
          <p style={copyStyle}>{hotkeyUsage}</p>
          <p style={copyStyle}>{t('onboarding.steps.hotkey.test')}</p>
          {!capabilityLoaded && (
            <div style={noteStyle}>{t('common.loading')}</div>
          )}
          {!permissionsOk && (
            <div style={{ ...noteStyle, color: 'var(--ol-red, #ef4444)', background: 'rgba(239,68,68,0.08)' }}>
              {t('onboarding.steps.hotkey.finishBlocked')}
            </div>
          )}
        </div>
      ),
    },
  ];

  const current = steps[step];

  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 40,
        fontFamily: 'var(--ol-font-sans)',
      }}
    >
      <div
        style={{
          width: 560,
          padding: 32,
          background: 'var(--ol-surface)',
          borderRadius: 14,
          border: '0.5px solid var(--ol-line)',
          boxShadow: 'var(--ol-shadow-lg)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: 13,
              background: 'linear-gradient(135deg, #0a0a0b 0%, #2563eb 100%)',
              color: '#fff',
              fontSize: 15,
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            WI
          </div>
          <div>
            <div style={{ fontSize: 18, fontWeight: 600 }}>{t('onboarding.welcome')}</div>
            <div style={{ fontSize: 12.5, color: 'var(--ol-ink-3)', marginTop: 2 }}>
              {t('onboarding.intro')}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 6, marginBottom: 18 }}>
          {steps.map((item, index) => (
            <button
              key={item.title}
              onClick={() => setStep(index)}
              style={{
                flex: 1,
                height: 4,
                border: 0,
                borderRadius: 999,
                background: index <= step ? 'var(--ol-blue)' : 'rgba(0,0,0,0.08)',
                padding: 0,
                cursor: 'default',
              }}
              aria-label={t('onboarding.stepLabel', { current: index + 1, total: steps.length })}
            />
          ))}
        </div>

        <div style={{ minHeight: 280 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--ol-blue)', marginBottom: 8 }}>
            {t('onboarding.stepLabel', { current: step + 1, total: steps.length })}
          </div>
          <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 10 }}>{current.title}</div>
          {current.body}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginTop: 18 }}>
          <button
            style={secondaryButtonStyle}
            disabled={step === 0}
            onClick={() => setStep(value => Math.max(0, value - 1))}
          >
            {t('onboarding.back')}
          </button>
          {step < steps.length - 1 ? (
            <button
              style={primaryButtonStyle}
              onClick={() => setStep(value => Math.min(steps.length - 1, value + 1))}
            >
              {t('onboarding.next')}
            </button>
          ) : (
            <button
              style={primaryButtonStyle}
              disabled={!permissionsOk}
              onClick={() => void finish()}
            >
              {t('onboarding.finish')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

interface PermissionRowProps {
  label: string;
  desc: string;
  status: PermissionStatus;
  actionLabel: string;
  disabled: boolean;
  onAction: () => void;
}

function PermissionRow({ label, desc, status, actionLabel, disabled, onAction }: PermissionRowProps) {
  const granted = status === 'granted' || status === 'notApplicable';
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 12, alignItems: 'center', padding: '12px 0', borderTop: '0.5px solid var(--ol-line-soft)' }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>{label}</div>
        <div style={{ fontSize: 12, color: 'var(--ol-ink-3)', marginTop: 3, lineHeight: 1.5 }}>{desc}</div>
      </div>
      <button
        style={granted ? secondaryButtonStyle : primaryButtonStyle}
        disabled={disabled}
        onClick={disabled ? undefined : onAction}
      >
        {actionLabel}
      </button>
    </div>
  );
}

const copyStyle: CSSProperties = {
  margin: 0,
  fontSize: 12.5,
  color: 'var(--ol-ink-3)',
  lineHeight: 1.65,
};

const noteStyle: CSSProperties = {
  padding: '10px 12px',
  borderRadius: 8,
  background: 'var(--ol-surface-2)',
  color: 'var(--ol-ink-3)',
  fontSize: 12,
  lineHeight: 1.55,
};

const primaryButtonStyle: CSSProperties = {
  padding: '7px 14px',
  fontSize: 12.5,
  fontWeight: 500,
  fontFamily: 'inherit',
  border: '0.5px solid transparent',
  borderRadius: 8,
  background: 'var(--ol-ink)',
  color: '#fff',
  cursor: 'default',
};

const secondaryButtonStyle: CSSProperties = {
  padding: '7px 14px',
  fontSize: 12.5,
  fontWeight: 500,
  fontFamily: 'inherit',
  border: '0.5px solid var(--ol-line-strong)',
  borderRadius: 8,
  background: 'transparent',
  color: 'var(--ol-ink-2)',
  cursor: 'default',
};
