import { useState, type CSSProperties, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { Icon } from './Icon';

export type OS = 'mac' | 'win' | 'linux';

export function detectOS(): OS {
  if (typeof navigator === 'undefined') return 'mac';
  const uaDataPlatform = (
    navigator as Navigator & { userAgentData?: { platform?: string } }
  ).userAgentData?.platform ?? '';
  const hints = `${navigator.userAgent || ''} ${navigator.platform || ''} ${uaDataPlatform}`;
  if (/Mac|iPhone|iPad|iPod/.test(hints)) return 'mac';
  if (/Windows|Win32|Win64/.test(hints)) return 'win';
  if (/Linux|X11|Wayland/.test(hints)) return 'linux';
  return 'mac';
}

const MAC_TITLEBAR_HEIGHT = 28;
const MAC_SYSTEM_CONTROLS_RESERVED_WIDTH = 76;
export const WIN_TITLEBAR_HEIGHT = 56;
export const WIN_WINDOW_RADIUS = 10;
export const WIN_CONSOLE_RADIUS = 10;
const WIN_RESIZE_EDGE = 6;
const WIN_RESIZE_CORNER = 14;

type ResizeDirection =
  | 'East'
  | 'North'
  | 'NorthEast'
  | 'NorthWest'
  | 'South'
  | 'SouthEast'
  | 'SouthWest'
  | 'West';

interface WindowChromeProps {
  os?: OS;
  title?: string;
  children: ReactNode;
  height?: number | string;
}

export function WindowChrome({
  os = 'mac',
  title = 'Whisper Input',
  children,
  height = 800,
}: WindowChromeProps) {
  const shellRadius = os === 'mac' ? 0 : os === 'win' ? WIN_WINDOW_RADIUS : 14;
  const consoleRadius = os === 'mac' ? 20 : os === 'win' ? WIN_CONSOLE_RADIUS : 14;

  return (
    <div
      style={{
        '--ol-window-shell-radius': `${shellRadius}px`,
        '--ol-window-console-radius': `${consoleRadius}px`,
        '--ol-window-titlebar-height': `${os === 'mac' ? MAC_TITLEBAR_HEIGHT : WIN_TITLEBAR_HEIGHT}px`,
        width: '100%',
        height,
        position: 'relative',
        borderRadius: 'var(--ol-window-shell-radius)',
        boxShadow: os === 'win' ? 'none' : 'var(--ol-shadow-xl)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        border: 'none',
        background: 'var(--wi-window)',
        backdropFilter: 'blur(var(--ol-glass-blur-strong))',
        WebkitBackdropFilter: 'blur(var(--ol-glass-blur-strong))',
        animation: os === 'win' ? undefined : 'ol-window-enter 0.42s var(--ol-motion-spring) both',
        transition: 'box-shadow 0.28s var(--ol-motion-soft), backdrop-filter 0.28s var(--ol-motion-soft)',
        willChange: 'opacity, transform, filter',
      } as CSSProperties}
    >
      {os === 'win' && <WinTitleBar title={title} />}
      {os === 'win' && <WindowsResizeHandles />}
      {os === 'mac' && (
        <div
          data-tauri-drag-region
          style={{
            position: 'absolute',
            top: 0,
            left: MAC_SYSTEM_CONTROLS_RESERVED_WIDTH,
            right: 0,
            height: MAC_TITLEBAR_HEIGHT,
            zIndex: 50,
          }}
        />
      )}
      <div style={{ flex: 1, minHeight: 0, display: 'flex', position: 'relative' }}>
        {children}
      </div>
    </div>
  );
}

interface WinTitleBarProps {
  title: string;
}

function WinTitleBar({ title }: WinTitleBarProps) {
  const { t } = useTranslation();
  return (
    <div
      style={{
        height: WIN_TITLEBAR_HEIGHT,
        flexShrink: 0,
        display: 'flex',
        alignItems: 'stretch',
        position: 'relative',
        zIndex: 70,
        borderBottom: '1px solid var(--wi-line)',
        background: 'rgba(255,255,255,.84)',
      }}
    >
      <div
        data-tauri-drag-region
        style={{ flex: 1, display: 'flex', alignItems: 'center', padding: '0 18px 0 22px', gap: 10 }}
      >
        <img src="preview-app-icon.png" alt="" style={{ width: 30, height: 30, borderRadius: 7 }} />
        <span style={{ fontSize: 17, color: 'var(--wi-text)', fontWeight: 500 }}>{title}</span>
      </div>
      <div style={{ display: 'flex', pointerEvents: 'auto' }}>
        <WinTitleButton title={t('windowChrome.minimize')} action="minimize">
          <Icon name="minus" size={12} strokeWidth={1.7} />
        </WinTitleButton>
        <WinTitleButton title={t('windowChrome.maximize')} action="toggleMaximize">
          <Icon name="maximize" size={12} strokeWidth={1.7} />
        </WinTitleButton>
        <WinTitleButton title={t('windowChrome.close')} action="close" tone="danger">
          <Icon name="close" size={12} strokeWidth={1.7} />
        </WinTitleButton>
      </div>
    </div>
  );
}

function WindowsResizeHandles() {
  const handles: Array<{
    direction: ResizeDirection;
    cursor: CSSProperties['cursor'];
    style: CSSProperties;
  }> = [
    { direction: 'North', cursor: 'ns-resize', style: { top: 0, left: WIN_RESIZE_CORNER, right: WIN_RESIZE_CORNER, height: WIN_RESIZE_EDGE } },
    { direction: 'South', cursor: 'ns-resize', style: { bottom: 0, left: WIN_RESIZE_CORNER, right: WIN_RESIZE_CORNER, height: WIN_RESIZE_EDGE } },
    { direction: 'West', cursor: 'ew-resize', style: { top: WIN_RESIZE_CORNER, bottom: WIN_RESIZE_CORNER, left: 0, width: WIN_RESIZE_EDGE } },
    { direction: 'East', cursor: 'ew-resize', style: { top: WIN_RESIZE_CORNER, bottom: WIN_RESIZE_CORNER, right: 0, width: WIN_RESIZE_EDGE } },
    { direction: 'NorthWest', cursor: 'nwse-resize', style: { top: 0, left: 0, width: WIN_RESIZE_CORNER, height: WIN_RESIZE_CORNER } },
    { direction: 'NorthEast', cursor: 'nesw-resize', style: { top: 0, right: 0, width: WIN_RESIZE_CORNER, height: WIN_RESIZE_CORNER } },
    { direction: 'SouthWest', cursor: 'nesw-resize', style: { bottom: 0, left: 0, width: WIN_RESIZE_CORNER, height: WIN_RESIZE_CORNER } },
    { direction: 'SouthEast', cursor: 'nwse-resize', style: { bottom: 0, right: 0, width: WIN_RESIZE_CORNER, height: WIN_RESIZE_CORNER } },
  ];

  return (
    <div aria-hidden style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 60 }}>
      {handles.map(handle => (
        <div
          key={handle.direction}
          onMouseDown={event => {
            if (event.button !== 0) return;
            event.preventDefault();
            event.stopPropagation();
            void startResizeDragging(handle.direction);
          }}
          style={{
            position: 'absolute',
            pointerEvents: 'auto',
            cursor: handle.cursor,
            ...handle.style,
          }}
        />
      ))}
    </div>
  );
}

interface WinTitleButtonProps {
  title: string;
  action: 'minimize' | 'toggleMaximize' | 'close';
  tone?: 'default' | 'danger';
  children: ReactNode;
}

function WinTitleButton({ title, action, tone = 'default', children }: WinTitleButtonProps) {
  const [hovered, setHovered] = useState(false);
  const [pressed, setPressed] = useState(false);
  const danger = tone === 'danger';
  const background = pressed
    ? danger ? '#c42b1c' : 'rgba(0, 0, 0, 0.12)'
    : hovered ? danger ? '#e81123' : 'rgba(0, 0, 0, 0.08)'
      : 'transparent';
  const color = danger && (hovered || pressed) ? '#fff' : 'var(--wi-muted)';

  return (
    <button
      style={{ ...winBtnStyle, background, color }}
      title={title}
      onClick={() => runWindowsWindowAction(action)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => {
        setHovered(false);
        setPressed(false);
      }}
      onMouseDown={() => setPressed(true)}
      onMouseUp={() => setPressed(false)}
    >
      {children}
    </button>
  );
}

async function startResizeDragging(direction: ResizeDirection) {
  try {
    await getCurrentWindow().startResizeDragging(direction);
  } catch (error) {
    console.warn(`[window] Windows resize ${direction} failed`, error);
  }
}

async function runWindowsWindowAction(action: 'minimize' | 'toggleMaximize' | 'close') {
  try {
    const currentWindow = getCurrentWindow();
    if (action === 'minimize') {
      await currentWindow.minimize();
    } else if (action === 'toggleMaximize') {
      await currentWindow.toggleMaximize();
    } else {
      await currentWindow.hide();
    }
  } catch (error) {
    console.warn(`[window] Windows title button ${action} failed`, error);
  }
}

const winBtnStyle: CSSProperties = {
  width: 48,
  height: '100%',
  border: 0,
  background: 'transparent',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: 'var(--wi-muted)',
  cursor: 'default',
  transition: 'background 0.16s var(--ol-motion-quick), color 0.16s var(--ol-motion-quick)',
};
