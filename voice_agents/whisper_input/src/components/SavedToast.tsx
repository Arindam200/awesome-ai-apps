// SavedToast.tsx — 控制台卡右上角的"正在保存 / 已保存 / 失败"小 pill。
// 父级 scroll wrapper（FloatingShell main 区）已设 position:relative，
// 此 pill 用 absolute 锚到右上角，避免在页面顶部撑成一条难看的长横幅。

import type { CSSProperties } from 'react';

export type SaveToastState = 'idle' | 'saving' | 'saved' | 'failed';

interface SavedToastProps {
  saveState: SaveToastState;
  message: string;
  /** 覆盖默认 top:16 right:16 偏移，例如 SettingsModal 里要避开 28×28 的关闭按钮。 */
  offsetStyle?: Pick<CSSProperties, 'top' | 'right' | 'left' | 'bottom'>;
}

export function SavedToast({ saveState, message, offsetStyle }: SavedToastProps) {
  if (saveState === 'idle') return null;
  const failed = saveState === 'failed';
  const style: CSSProperties = {
    position: 'absolute',
    top: 16,
    right: 16,
    ...offsetStyle,
    zIndex: 5,
    padding: '5px 12px',
    borderRadius: 999,
    border: failed
      ? '0.5px solid rgba(239,68,68,0.22)'
      : '0.5px solid rgba(37,99,235,0.16)',
    background: failed ? 'rgba(239,68,68,0.10)' : 'rgba(37,99,235,0.10)',
    color: failed ? 'var(--ol-red, #ef4444)' : 'var(--ol-blue)',
    fontSize: 11.5,
    fontWeight: 500,
    lineHeight: 1.4,
    boxShadow: '0 4px 12px -4px rgba(15,17,22,0.18), 0 0 0 0.5px rgba(0,0,0,0.04)',
    backdropFilter: 'blur(12px) saturate(160%)',
    WebkitBackdropFilter: 'blur(12px) saturate(160%)',
    pointerEvents: 'none',
    animation: 'ol-toast-pop 0.22s var(--ol-motion-spring)',
    whiteSpace: 'nowrap',
  };
  return (
    <div role={failed ? 'alert' : 'status'} style={style}>
      {message}
      <style>{`
        @keyframes ol-toast-pop {
          from { opacity: 0; transform: translateY(-6px) scale(.96); filter: blur(4px); }
          to   { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
        }
      `}</style>
    </div>
  );
}
