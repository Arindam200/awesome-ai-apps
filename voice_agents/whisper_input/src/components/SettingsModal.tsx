import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { Icon } from './Icon';
import { Settings as SettingsContent, type SettingsSectionId } from '../pages/Settings';
import { Row } from './ui/Row';
import { SavedToast } from './SavedToast';
import { useSavedToastListener } from '../lib/savedEvent';
import { readFontScale, setFontScale, type FontScaleId } from '../lib/fontScale';
import { openExternal } from '../lib/ipc';
import {
  FOLLOW_SYSTEM,
  getLocalePreference,
  setLocalePreference,
  type SupportedLocale,
} from '../i18n';
import type { OS } from './WindowChrome';

interface SettingsModalProps {
  os: OS;
  onClose: () => void;
  initialSettingsSection?: SettingsSectionId;
}

type ModalSectionId = 'settings' | 'personalize' | 'about';

interface ModalNavItem {
  id: string;
  icon: string;
}

interface ModalGroup {
  items: ModalNavItem[];
}

export function SettingsModal({ os: _os, onClose, initialSettingsSection }: SettingsModalProps) {
  const { t } = useTranslation();
  const [section, setSection] = useState<ModalSectionId>('settings');
  const savedToast = useSavedToastListener();
  const groups: ModalGroup[] = [
    {
      items: [
        { id: 'settings', icon: 'settings' },
        { id: 'personalize', icon: 'sparkle' },
        { id: 'about', icon: 'info' },
      ],
    },
  ];

  const firstGroupRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const [pillRect, setPillRect] = useState<{ top: number; height: number } | null>(null);
  useLayoutEffect(() => {
    const idx = groups[0].items.findIndex(it => it.id === section);
    const el = firstGroupRefs.current[idx];
    if (!el) return;
    setPillRect({ top: el.offsetTop, height: el.offsetHeight });
  }, [section]);

  return (
    <div
      onClick={onClose}
      style={{
        position: 'absolute', inset: 0,
        background: 'rgba(15,17,22,0.32)',
        backdropFilter: 'blur(8px) saturate(140%)',
        WebkitBackdropFilter: 'blur(8px) saturate(140%)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 28,
        zIndex: 50,
        animation: 'ol-modal-fade .2s var(--ol-motion-soft)',
      }}>

      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: 880, height: '100%', maxHeight: 600,
          background: 'var(--ol-surface)',
          borderRadius: 14,
          border: '0.5px solid rgba(0,0,0,.08)',
          boxShadow: '0 30px 80px -20px rgba(15,17,22,.35), 0 0 0 0.5px rgba(0,0,0,.06)',
          display: 'flex', overflow: 'hidden',
          animation: 'ol-modal-pop .28s var(--ol-motion-spring)',
          position: 'relative',
        }}>

        <aside
          style={{
            width: 200, flexShrink: 0,
            background: 'rgba(247,247,250,0.7)',
            borderRight: '0.5px solid var(--ol-line-soft)',
            padding: '18px 12px',
            display: 'flex', flexDirection: 'column', gap: 14,
          }}>

          {groups.map((g, gi) => (
            <div key={gi} style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: 1, paddingTop: gi === 1 ? 8 : 0, borderTop: gi === 1 ? '0.5px solid var(--ol-line-soft)' : 'none' }}>
              {gi === 0 && pillRect && (
                <div
                  aria-hidden
                  style={{
                    position: 'absolute',
                    left: 0,
                    right: 0,
                    top: pillRect.top,
                    height: pillRect.height,
                    background: '#fff',
                    borderRadius: 8,
                    boxShadow: '0 1px 2px rgba(0,0,0,.05), 0 0 0 0.5px rgba(0,0,0,.06)',
                    transition: 'top 0.36s var(--ol-motion-spring), height 0.36s var(--ol-motion-spring)',
                    pointerEvents: 'none',
                    zIndex: 0,
                  }}
                />
              )}
              {g.items.map((it, idx) => {
                const active = section === it.id;
                return (
                  <button
                    key={it.id}
                    ref={gi === 0 ? (el => { firstGroupRefs.current[idx] = el; }) : undefined}
                    onClick={() => {
                      setSection(it.id as ModalSectionId);
                    }}
                    className={active ? 'ol-nav-btn ol-nav-btn-active' : 'ol-nav-btn'}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '7px 10px',
                      borderRadius: 8, border: 0,
                      background: 'transparent',
                      fontFamily: 'inherit', fontSize: 13,
                      cursor: 'default', textAlign: 'left',
                      position: 'relative',
                      zIndex: 1,
                      transition: 'color 0.16s var(--ol-motion-quick), background 0.16s var(--ol-motion-quick)',
                    }}>

                    <Icon name={it.icon} size={14} />
                    <span style={{ flex: 1 }}>{t(`modal.sections.${it.id}`)}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </aside>

        <div style={{ flex: 1, minWidth: 0, overflow: 'hidden', position: 'relative', display: 'flex', flexDirection: 'column' }}>
          <SavedToast
            saveState={savedToast.state}
            message={savedToast.message}
            offsetStyle={{ top: 16, right: 54 }}
          />
          <button
            onClick={onClose}
            style={{
              position: 'absolute', top: 14, right: 14, zIndex: 2,
              width: 28, height: 28, border: 0, borderRadius: 999,
              background: 'transparent', color: 'var(--ol-ink-3)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'default',
              transition: 'background 0.16s var(--ol-motion-quick)',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(0,0,0,0.05)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            title={t('common.close')}>

            <Icon name="close" size={14} />
          </button>

          <h2 style={{ margin: 0, padding: '22px 28px 8px', fontSize: 22, fontWeight: 650, letterSpacing: 0, flexShrink: 0, textWrap: 'balance' }}>{t(`modal.sections.${section}`)}</h2>

          {section === 'settings' ? (
            <div style={{ flex: 1, minHeight: 0, padding: '10px 28px 28px', display: 'flex', flexDirection: 'column' }}>
              <SettingsContent embedded initialSection={initialSettingsSection} />
            </div>
          ) : (
            <div className="ol-thinscroll" style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '10px 28px 28px' }}>
              {section === 'personalize' && <PersonalizeSection />}
              {section === 'about' && <AboutMini />}
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes ol-modal-fade {
          from { opacity: 0; backdrop-filter: blur(0); -webkit-backdrop-filter: blur(0); }
          to   { opacity: 1; backdrop-filter: blur(8px) saturate(140%); -webkit-backdrop-filter: blur(8px) saturate(140%); }
        }
        @keyframes ol-modal-pop {
          from { opacity: 0; transform: translateY(8px) scale(.98); filter: blur(8px); }
          to   { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
        }
      `}</style>
    </div>
  );
}

function PersonalizeSection() {
  const { t } = useTranslation();
  const [blur, setBlur] = useState<number>(() => {
    const saved = window.localStorage.getItem('ol.glassBlur');
    return saved ? Number(saved) : 22;
  });

  useEffect(() => {
    document.documentElement.style.setProperty('--ol-glass-blur', `${blur}px`);
    window.localStorage.setItem('ol.glassBlur', String(blur));
  }, [blur]);

  const [fontScale, setFontScaleState] = useState<FontScaleId>(() => readFontScale());
  const applyFontScaleChoice = (next: FontScaleId) => {
    setFontScaleState(next);
    setFontScale(next);
  };
  const fontOptions: Array<[FontScaleId, string]> = [
    ['small', t('modal.personalize.fontSmall')],
    ['medium', t('modal.personalize.fontMedium')],
    ['large', t('modal.personalize.fontLarge')],
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Row label={t('modal.personalize.language')}>
        <LanguagePicker />
      </Row>
      <Row label={t('modal.personalize.font')} desc={t('modal.personalize.fontDesc')}>
        <div style={{ display: 'flex', gap: 4, padding: 2, background: 'rgba(0,0,0,0.04)', borderRadius: 8 }}>
          {fontOptions.map(([id, label]) => {
            const selected = fontScale === id;
            return (
              <button
                key={id}
                onClick={() => applyFontScaleChoice(id)}
                style={{
                  minWidth: 64,
                  height: 28,
                  border: 0,
                  borderRadius: 6,
                  background: selected ? '#fff' : 'transparent',
                  color: selected ? 'var(--ol-ink)' : 'var(--ol-ink-3)',
                  fontFamily: 'inherit',
                  fontSize: 12,
                  fontWeight: selected ? 600 : 500,
                  cursor: 'default',
                  boxShadow: selected ? '0 1px 2px rgba(0,0,0,.06), 0 0 0 0.5px rgba(0,0,0,.06)' : 'none',
                  transition: 'background 0.16s var(--ol-motion-quick), color 0.16s var(--ol-motion-quick), box-shadow 0.18s var(--ol-motion-soft)',
                  padding: '0 12px',
                }}
              >
                {label}
              </button>
            );
          })}
        </div>
      </Row>
      <Row label={t('modal.personalize.blur')} desc={t('modal.personalize.blurDesc')}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
          <input
            type="range"
            min="0"
            max="48"
            value={blur}
            onChange={e => setBlur(Number(e.target.value))}
            style={{ width: 200, accentColor: 'var(--ol-blue)' }}
          />
          <span style={{ fontSize: 12, fontFamily: 'var(--ol-font-mono)', color: 'var(--ol-ink-3)', minWidth: 36 }}>
            {blur}px
          </span>
        </div>
      </Row>
    </div>
  );
}

function AboutMini() {
  const { t } = useTranslation();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Row label={t('settings.about.websiteLabel')} desc={t('settings.about.websiteDesc')}>
        <button
          style={btnGhost}
          onClick={() => openExternal('https://whisperinput.app')}
        >
          {t('settings.about.websiteBtn')}
        </button>
      </Row>
      <Row label={t('settings.about.githubStarLabel')} desc={t('settings.about.githubStarDesc')}>
        <button
          style={btnGhost}
          onClick={() => openExternal('https://whisperinput.app/github')}
        >
          {t('settings.about.githubStarBtn')}
        </button>
      </Row>
      <Row label={t('settings.about.feedbackLabel')} desc={t('settings.about.feedbackDesc')}>
        <button
          style={btnGhost}
          onClick={() => openExternal('https://whisperinput.app/feedback')}
        >
          {t('settings.about.feedbackBtn')}
        </button>
      </Row>
    </div>
  );
}

const btnGhost: CSSProperties = {
  padding: '5px 10px', fontSize: 12, borderRadius: 6,
  border: '0.5px solid var(--ol-line-strong)',
  background: '#fff', color: 'var(--ol-ink-2)',
  cursor: 'default', fontFamily: 'inherit',
  transition: 'background 0.16s var(--ol-motion-quick), border-color 0.16s var(--ol-motion-quick)',
};

function LanguagePicker() {
  const { t } = useTranslation();
  const [pref, setPref] = useState<SupportedLocale | typeof FOLLOW_SYSTEM>(getLocalePreference());

  const apply = async (next: SupportedLocale | typeof FOLLOW_SYSTEM) => {
    setPref(next);
    await setLocalePreference(next);
  };

  return (
    <select
      value={pref}
      onChange={e => apply(e.target.value as SupportedLocale | typeof FOLLOW_SYSTEM)}
      style={{
        height: 32, padding: '0 10px',
        border: '0.5px solid var(--ol-line-strong)',
        borderRadius: 8, fontSize: 12.5,
        fontFamily: 'inherit', outline: 'none',
        background: 'var(--ol-surface-2)',
        minWidth: 200, cursor: 'default',
      }}
    >
      <option value={FOLLOW_SYSTEM}>{t('settings.language.followSystem')}</option>
      <option value="zh-CN">{t('settings.language.zh')}</option>
      <option value="zh-TW">{t('settings.language.zhTW')}</option>
      <option value="en">{t('settings.language.en')}</option>
      <option value="ja">{t('settings.language.ja')}</option>
      <option value="ko">{t('settings.language.ko')}</option>
    </select>
  );
}
