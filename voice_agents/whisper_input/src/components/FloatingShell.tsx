import { useCallback, useEffect, useMemo, useState, type ComponentType } from 'react';
import { useTranslation } from 'react-i18next';
import { Icon } from './Icon';
import { WindowChrome, detectOS, type OS } from './WindowChrome';
import { AppShell } from './shell/AppShell';
import { PageContainer } from './shell/PageContainer';
import { Sidebar } from './shell/Sidebar';
import { Overview } from '../pages/Overview';
import { History } from '../pages/History';
import { Vocab } from '../pages/Vocab';
import { Style } from '../pages/Style';
import { Settings } from '../pages/Settings';
import { applyFontScale, readFontScale } from '../lib/fontScale';
import { isHotkeyModeMigrationNoticeActive, HOTKEY_MODE_MIGRATION_ACK_KEY, HOTKEY_MODE_MIGRATION_DEFERRED_KEY, shouldShowHotkeyModeMigrationPrompt } from '../lib/hotkeyMigration';
import { getCredentials } from '../lib/ipc';
import i18n, { setLocalePreference } from '../i18n';
import { APP_TABS } from '../lib/appNavigation';
import { PRODUCT_NAME, PRODUCT_NAME_ZH } from '../lib/product';
import { PROVIDER_SETUP_PROMPT_DEFERRED_KEY, shouldShowProviderSetupPrompt } from '../lib/providerSetup';
import { type SettingsSectionId } from '../pages/Settings';
import { useAppState, type AppTab } from '../state/useAppState';

interface NavItem {
  id: AppTab;
  name: string;
  icon: string;
  cmp: ComponentType;
}

const NAV_COMPONENTS: Record<AppTab, Pick<NavItem, 'icon' | 'cmp'>> = {
  overview: { icon: 'overview', cmp: Overview },
  history: { icon: 'history', cmp: History },
  vocab: { icon: 'vocab', cmp: Vocab },
  style: { icon: 'style', cmp: Style },
  settings: { icon: 'settings', cmp: Settings },
};

const NAV_BASE: Array<Omit<NavItem, 'name'>> = APP_TABS.map(id => ({
  id,
  ...NAV_COMPONENTS[id],
}));

interface FloatingShellProps {
  os?: OS;
  initialTab?: AppTab;
  initialSettings?: boolean;
  initialSettingsSection?: SettingsSectionId;
}

export function FloatingShell({
  os: osProp,
  initialTab = 'overview',
  initialSettings = false,
  initialSettingsSection,
}: FloatingShellProps) {
  const os = osProp ?? detectOS();
  return (
    <WindowChrome os={os} title={`${PRODUCT_NAME_ZH} / ${PRODUCT_NAME}`} height="100%">
      <FloatingShellBody
        os={os}
        initialTab={initialTab}
        initialSettings={initialSettings}
        initialSettingsSection={initialSettingsSection}
      />
    </WindowChrome>
  );
}

function FloatingShellBody({
  os,
  initialTab,
  initialSettings,
  initialSettingsSection,
}: {
  os: OS;
  initialTab: AppTab;
  initialSettings: boolean;
  initialSettingsSection?: SettingsSectionId;
}) {
  const { t } = useTranslation();
  const { currentTab, setCurrentTab } = useAppState(initialSettings ? 'settings' : initialTab);
  const [settingsInitialSection, setSettingsInitialSection] = useState<SettingsSectionId | undefined>(initialSettingsSection);
  const [startupPrompt, setStartupPrompt] = useState<'provider' | 'hotkey' | null>(null);

  const [displayTab, setDisplayTab] = useState<AppTab>(currentTab);
  const [tabPhase, setTabPhase] = useState<'idle' | 'exiting'>('idle');
  useEffect(() => {
    if (currentTab === displayTab) return;
    setTabPhase('exiting');
    const id = window.setTimeout(() => {
      setDisplayTab(currentTab);
      setTabPhase('idle');
    }, 180);
    return () => window.clearTimeout(id);
  }, [currentTab, displayTab]);

  useEffect(() => {
    applyFontScale(readFontScale());
  }, []);

  const NAV = useMemo<NavItem[]>(
    () => NAV_BASE.map(b => ({ ...b, name: t(`nav.${b.id}`) })),
    [t],
  );
  const openSettingsPage = useCallback((section?: SettingsSectionId) => {
    setSettingsInitialSection(section);
    setCurrentTab('settings');
  }, [setCurrentTab]);
  const openHelp = () => openSettingsPage('about');
  const Page = (NAV.find((n) => n.id === displayTab) ?? NAV[0]).cmp;
  const sidebarItems = useMemo(
    () => NAV.map(n => ({
      id: n.id,
      icon: n.icon,
      label: n.name,
      active: currentTab === n.id,
      onClick: () => n.id === 'settings' ? openSettingsPage() : setCurrentTab(n.id),
    })),
    [NAV, currentTab, openSettingsPage, setCurrentTab],
  );

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const modifierPressed = os === 'mac' ? e.metaKey : e.ctrlKey;
      if (modifierPressed && e.key === ',') {
        e.preventDefault();
        openSettingsPage();
      }
    };
    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [openSettingsPage, os]);

  useEffect(() => {
    if (os !== 'win') return;
    let cancelled = false;

    const loadStartupPrompt = async () => {
      const credentials = await getCredentials();
      if (cancelled) return;
      if (shouldShowProviderSetupPrompt(credentials, window.sessionStorage.getItem(PROVIDER_SETUP_PROMPT_DEFERRED_KEY))) {
        setStartupPrompt('provider');
      } else if (shouldShowHotkeyModeMigrationPrompt(
        window.localStorage.getItem(HOTKEY_MODE_MIGRATION_ACK_KEY),
        window.sessionStorage.getItem(HOTKEY_MODE_MIGRATION_DEFERRED_KEY),
      )) {
        setStartupPrompt('hotkey');
      }
    };

    void loadStartupPrompt().catch(error => {
      console.warn('[startup] failed to determine setup prompt', error);
    });
    return () => {
      cancelled = true;
    };
  }, [os]);

  const deferStartupPrompt = () => {
    if (startupPrompt === 'provider') {
      window.sessionStorage.setItem(PROVIDER_SETUP_PROMPT_DEFERRED_KEY, '1');
    } else if (startupPrompt === 'hotkey') {
      window.sessionStorage.setItem(HOTKEY_MODE_MIGRATION_DEFERRED_KEY, '1');
    }
    setStartupPrompt(null);
  };

  const openStartupPromptSettings = () => {
    if (startupPrompt === 'provider') {
      window.sessionStorage.setItem(PROVIDER_SETUP_PROMPT_DEFERRED_KEY, '1');
      openSettingsPage('models');
    } else if (startupPrompt === 'hotkey') {
      window.localStorage.setItem(HOTKEY_MODE_MIGRATION_ACK_KEY, '1');
      openSettingsPage('recording');
    }
    setStartupPrompt(null);
  };

  const switchLocale = () => {
    const currentLanguage = (i18n.resolvedLanguage || i18n.language || '').toLowerCase();
    void setLocalePreference(currentLanguage.startsWith('en') ? 'zh-CN' : 'en');
  };

  return (
    <>
      <AppShell
        os={os}
        sidebar={
          <Sidebar items={sidebarItems} />
        }
        commandBar={
          <CommandBar
            onOpenHelp={openHelp}
            onToggleLocale={switchLocale}
          />
        }
        overlays={
          startupPrompt === 'provider' ? (
            <ProviderSetupPrompt onLater={deferStartupPrompt} onOpenSettings={openStartupPromptSettings} />
          ) : startupPrompt === 'hotkey' && isHotkeyModeMigrationNoticeActive() ? (
            <HotkeyModeMigrationPrompt onLater={deferStartupPrompt} onOpenSettings={openStartupPromptSettings} />
          ) : null
        }
      >
        <PageContainer key={displayTab} phase={tabPhase}>
          {displayTab === 'overview' ? (
            <Overview onOpenHistory={() => setCurrentTab('history')} onOpenSettings={() => openSettingsPage('models')} />
          ) : displayTab === 'settings' ? (
            <Settings embedded initialSection={settingsInitialSection ?? 'models'} />
          ) : (
            <Page />
          )}
        </PageContainer>
      </AppShell>

      <style>{`
        .ol-nav-btn {
          color: var(--ol-ink-3);
          font-weight: 500;
        }
        .ol-nav-btn.ol-nav-btn-active {
          color: var(--ol-ink);
          font-weight: 600;
        }
        .ol-nav-btn:not(.ol-nav-btn-active):hover {
          background: var(--ol-surface-3);
          color: var(--ol-ink);
        }
        @keyframes ol-page-slide {
          from { opacity: 0; transform: translate3d(10px, 0, 0) scale(.996); filter: blur(6px); }
          to   { opacity: 1; transform: translate3d(0, 0, 0) scale(1); filter: blur(0); }
        }
        @keyframes ol-page-fadeout {
          from { opacity: 1; filter: blur(0); }
          to   { opacity: 0; filter: blur(8px); }
        }
        @keyframes ol-prompt-fade {
          from { opacity: 0; backdrop-filter: blur(0); -webkit-backdrop-filter: blur(0); }
          to   { opacity: 1; backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px); }
        }
        @keyframes ol-prompt-pop {
          from { opacity: 0; transform: translateY(6px) scale(.97); filter: blur(6px); }
          to   { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
        }
      `}</style>
    </>
  );
}

function CommandBar({
  onOpenHelp,
  onToggleLocale,
}: {
  onOpenHelp: () => void;
  onToggleLocale: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="wi-commandbar">
      <button className="wi-btn" type="button" onClick={onOpenHelp}>
        <Icon name="help" size={14} strokeWidth={1.75} />
        {t('shell.commandBar.help')}
      </button>
      <button
        className="wi-btn"
        type="button"
        title={t('shell.commandBar.language')}
        onClick={onToggleLocale}
      >
        {t('shell.commandBar.languageToggle')}
      </button>
    </div>
  );
}

function ProviderSetupPrompt({ onLater, onOpenSettings }: { onLater: () => void; onOpenSettings: () => void }) {
  const { t } = useTranslation();
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 70,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 28,
        background: 'rgba(15,17,22,0.28)',
        backdropFilter: 'blur(6px) saturate(140%)',
        WebkitBackdropFilter: 'blur(6px) saturate(140%)',
        animation: 'ol-prompt-fade 0.2s var(--ol-motion-soft)',
      }}
    >
      <div
        style={{
          width: 360,
          borderRadius: 12,
          background: 'var(--ol-surface)',
          border: '0.5px solid rgba(0,0,0,.08)',
          boxShadow: '0 24px 70px -24px rgba(15,17,22,.38), 0 0 0 0.5px rgba(0,0,0,.06)',
          padding: 20,
          animation: 'ol-prompt-pop 0.26s var(--ol-motion-spring)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              background: 'rgba(37,99,235,0.10)',
              color: 'var(--ol-blue)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <Icon name="settings" size={17} />
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ol-ink)' }}>{t('shell.providerPrompt.title')}</div>
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--ol-ink-3)', lineHeight: 1.55 }}>
          {t('shell.providerPrompt.body')}
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 18 }}>
          <button
            onClick={onLater}
            style={{
              height: 32,
              padding: '0 13px',
              borderRadius: 8,
              border: '0.5px solid var(--ol-line-strong)',
              background: 'var(--ol-surface)',
              color: 'var(--ol-ink-3)',
              fontFamily: 'inherit',
              fontSize: 12.5,
              fontWeight: 500,
              cursor: 'default',
              transition: 'background 0.16s var(--ol-motion-quick), border-color 0.16s var(--ol-motion-quick)',
            }}
          >
            {t('shell.providerPrompt.later')}
          </button>
          <button
            onClick={onOpenSettings}
            style={{
              height: 32,
              padding: '0 14px',
              borderRadius: 8,
              border: 0,
              background: 'var(--ol-ink)',
              color: '#fff',
              fontFamily: 'inherit',
              fontSize: 12.5,
              fontWeight: 500,
              cursor: 'default',
              transition: 'background 0.16s var(--ol-motion-quick), transform 0.12s var(--ol-motion-quick)',
            }}
          >
            {t('shell.providerPrompt.openSettings')}
          </button>
        </div>
      </div>
    </div>
  );
}

function HotkeyModeMigrationPrompt({ onLater, onOpenSettings }: { onLater: () => void; onOpenSettings: () => void }) {
  const { t } = useTranslation();
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 70,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 28,
        background: 'rgba(15,17,22,0.28)',
        backdropFilter: 'blur(6px) saturate(140%)',
        WebkitBackdropFilter: 'blur(6px) saturate(140%)',
        animation: 'ol-prompt-fade 0.2s var(--ol-motion-soft)',
      }}
    >
      <div
        style={{
          width: 380,
          borderRadius: 12,
          background: 'var(--ol-surface)',
          border: '0.5px solid rgba(0,0,0,.08)',
          boxShadow: '0 24px 70px -24px rgba(15,17,22,.38), 0 0 0 0.5px rgba(0,0,0,.06)',
          padding: 20,
          animation: 'ol-prompt-pop 0.26s var(--ol-motion-spring)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              background: 'rgba(37,99,235,0.10)',
              color: 'var(--ol-blue)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <Icon name="mic" size={17} />
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ol-ink)' }}>{t('shell.hotkeyModePrompt.title')}</div>
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--ol-ink-3)', lineHeight: 1.55 }}>
          {t('shell.hotkeyModePrompt.body')}
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 18 }}>
          <button
            onClick={onLater}
            style={{
              height: 32,
              padding: '0 13px',
              borderRadius: 8,
              border: '0.5px solid var(--ol-line-strong)',
              background: 'var(--ol-surface)',
              color: 'var(--ol-ink-3)',
              fontFamily: 'inherit',
              fontSize: 12.5,
              fontWeight: 500,
              cursor: 'default',
              transition: 'background 0.16s var(--ol-motion-quick), border-color 0.16s var(--ol-motion-quick)',
            }}
          >
            {t('shell.hotkeyModePrompt.later')}
          </button>
          <button
            onClick={onOpenSettings}
            style={{
              height: 32,
              padding: '0 14px',
              borderRadius: 8,
              border: 0,
              background: 'var(--ol-ink)',
              color: '#fff',
              fontFamily: 'inherit',
              fontSize: 12.5,
              fontWeight: 500,
              cursor: 'default',
              transition: 'background 0.16s var(--ol-motion-quick), transform 0.12s var(--ol-motion-quick)',
            }}
          >
            {t('shell.hotkeyModePrompt.openSettings')}
          </button>
        </div>
      </div>
    </div>
  );
}
