import { useEffect, useState } from 'react';
import { Capsule } from './components/Capsule';
import { FloatingShell } from './components/FloatingShell';
import { Onboarding } from './components/Onboarding';
import { detectOS } from './components/WindowChrome';
import {
  checkAccessibilityPermission,
  checkMicrophonePermission,
  getHotkeyStatus,
  handleWindowHotkeyEvent,
  isTauri,
} from './lib/ipc';
import {
  isWindowHotkeyKeyboardCandidate,
  windowMouseHotkeyCode,
} from './lib/windowHotkeyFallback';
import { PRODUCT_NAME } from './lib/product';
import { QaPanel } from './pages/QaPanel';
import type { SettingsSectionId } from './pages/Settings';
import { HotkeySettingsProvider } from './state/HotkeySettingsContext';

interface AppProps {
  isCapsule: boolean;
  isQa: boolean;
}

type Gate = 'checking' | 'onboarding' | 'ready';

export function App({ isCapsule, isQa }: AppProps) {
  if (isCapsule) {
    return <Capsule />;
  }
  if (isQa) {
    return <QaPanel />;
  }

  const os = detectOS();
  // Windows 启动不应被权限探测阻塞首屏。
  const [gate, setGate] = useState<Gate>(isTauri ? 'checking' : 'ready');
  const [initialSettingsOpen, setInitialSettingsOpen] = useState(false);
  const [initialSettingsSection, setInitialSettingsSection] = useState<SettingsSectionId | undefined>();

  useEffect(() => {
    if (!isTauri) return;
    if (os === 'win' && gate === 'checking') return;
    let cancelled = false;
    requestAnimationFrame(() => {
      if (cancelled) return;
      import('@tauri-apps/api/window')
        .then(async ({ getCurrentWindow }) => {
          const currentWindow = getCurrentWindow();
          if (!(await currentWindow.isVisible())) {
            await currentWindow.show();
          }
        })
        .catch(error => console.warn('[startup] show main window failed', error));
    });
    return () => {
      cancelled = true;
    };
  }, [gate, os]);

  useEffect(() => {
    if (!isTauri) return;
    let cancelled = false;

    if (os === 'win') {
      // 超时保护：50 次 × 200ms = 10s。hotkey hook 永远 starting（被反作弊 / EDR
      // / UAC 拦）时不让 UI 死锁灰屏，过 10s 强 setGate('ready') 让用户进
      // Permissions 页看 hotkey_status.lastError 处理。详见 issue #163。
      const POLL_INTERVAL_MS = 200;
      const POLL_MAX_ATTEMPTS = 50;
      const pollHotkeyStatus = async () => {
        let attempts = 0;
        while (!cancelled && attempts < POLL_MAX_ATTEMPTS) {
          attempts += 1;
          const status = await getHotkeyStatus();
          if (cancelled) return;
          if (status.state !== 'starting') {
            setGate('ready');
            return;
          }
          await new Promise(resolve => window.setTimeout(resolve, POLL_INTERVAL_MS));
        }
        if (!cancelled) {
          console.warn(
            `[startup] hotkey gate timed out after ${POLL_MAX_ATTEMPTS * POLL_INTERVAL_MS}ms; forcing ready so user can reach Permissions page`
          );
          setGate('ready');
        }
      };
      void pollHotkeyStatus().catch(error => {
        console.warn('[startup] hotkey status polling failed', error);
        if (!cancelled) {
          setGate('ready');
        }
      });
      return () => {
        cancelled = true;
      };
    }

    (async () => {
      const [a, m] = await Promise.all([
        checkAccessibilityPermission(),
        checkMicrophonePermission(),
      ]);
      if (cancelled) return;
      const aOk = a === 'granted' || a === 'notApplicable';
      const mOk = m === 'granted' || m === 'notApplicable';
      setGate(aOk && mOk ? 'ready' : 'onboarding');
    })();
    return () => {
      cancelled = true;
    };
  }, [os]);

  useEffect(() => {
    if (!isTauri || os !== 'win') return;
    const forwardKey = (event: KeyboardEvent) => {
      if (!isWindowHotkeyKeyboardCandidate(event)) return;
      void handleWindowHotkeyEvent(
        event.type as 'keydown' | 'keyup',
        event.key,
        event.code,
        event.repeat,
      ).catch(error => console.warn('[window-hotkey] forward failed', error));
    };
    const forwardMouse = (event: MouseEvent) => {
      const code = windowMouseHotkeyCode(event.button);
      if (!code) return;
      void handleWindowHotkeyEvent(
        event.type === 'mousedown' ? 'keydown' : 'keyup',
        code,
        code,
        false,
      ).catch(error => console.warn('[window-hotkey] mouse forward failed', error));
    };
    window.addEventListener('keydown', forwardKey, true);
    window.addEventListener('keyup', forwardKey, true);
    window.addEventListener('mousedown', forwardMouse, true);
    window.addEventListener('mouseup', forwardMouse, true);
    return () => {
      window.removeEventListener('keydown', forwardKey, true);
      window.removeEventListener('keyup', forwardKey, true);
      window.removeEventListener('mousedown', forwardMouse, true);
      window.removeEventListener('mouseup', forwardMouse, true);
    };
  }, [os]);

  if (gate === 'checking') {
    return <StartupShell />;
  }
  const completeOnboarding = () => {
    setInitialSettingsOpen(false);
    setInitialSettingsSection(undefined);
    setGate('ready');
  };
  const openOnboardingSettings = (section: SettingsSectionId) => {
    setInitialSettingsSection(section);
    setInitialSettingsOpen(true);
    setGate('ready');
  };
  return (
    <HotkeySettingsProvider>
      {gate === 'onboarding' ? (
        <Onboarding onComplete={completeOnboarding} onOpenSettings={openOnboardingSettings} />
      ) : (
        <FloatingShell
          initialSettings={initialSettingsOpen}
          initialSettingsSection={initialSettingsSection}
        />
      )}
    </HotkeySettingsProvider>
  );
}

function StartupShell() {
  // 用透明背景：main window 是 transparent + macOSPrivateApi（NSVisualEffectView 磨砂）。
  // 之前用 linear-gradient(rgba(245,245,247,0.96)...) 会盖过 macOS vibrancy，启动时
  // 长时间在 'checking' phase（凭据迁移 / 权限 probe 慢）会让窗口看起来「左侧白屏 +
  // 右侧磨砂」割裂。现在背景全透明，让磨砂统一展开，提示文字 + icon 用一个轻量
  // pill 卡片承载，跟 capsule 视觉一致。
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        background: 'transparent',
        color: 'var(--ol-ink-3)',
        fontFamily: 'var(--ol-font-sans)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          fontSize: 13,
          fontWeight: 500,
          padding: '10px 16px',
          borderRadius: 999,
          background: 'rgba(255, 255, 255, 0.55)',
          backdropFilter: 'blur(20px) saturate(180%)',
          WebkitBackdropFilter: 'blur(20px) saturate(180%)',
          border: '0.5px solid rgba(0, 0, 0, 0.06)',
          boxShadow: '0 4px 14px -6px rgba(0, 0, 0, 0.18), 0 0 0 0.5px rgba(0,0,0,0.04)',
        }}
      >
        <img src="AppIcon.png" alt="" style={{ width: 18, height: 18, borderRadius: 4 }} />
        <span>{PRODUCT_NAME} 正在启动</span>
      </div>
    </div>
  );
}
