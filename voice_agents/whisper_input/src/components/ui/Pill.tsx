import type { CSSProperties, ReactNode } from 'react';

export type PillTone = 'default' | 'blue' | 'ok' | 'outline' | 'dark';
export type PillSize = 'sm' | 'md';

interface PillProps {
  children: ReactNode;
  tone?: PillTone;
  size?: PillSize;
  style?: CSSProperties;
}

export function Pill({ children, tone = 'default', size = 'md', style }: PillProps) {
  const tones: Record<PillTone, { bg: string; color: string; bd: string }> = {
    default: { bg: 'rgba(0,0,0,0.05)', color: 'var(--ol-ink-2)', bd: 'transparent' },
    blue: { bg: 'var(--ol-blue-soft)', color: 'var(--ol-blue)', bd: 'transparent' },
    ok: { bg: 'var(--ol-ok-soft)', color: 'var(--ol-ok)', bd: 'transparent' },
    outline: { bg: 'transparent', color: 'var(--ol-ink-3)', bd: 'var(--ol-line-strong)' },
    dark: { bg: 'var(--ol-ink)', color: '#fff', bd: 'transparent' },
  };
  const colors = tones[tone];
  const sizing = size === 'sm'
    ? { padding: '2px 8px', fontSize: 10.5 }
    : { padding: '4px 10px', fontSize: 11.5 };

  return (
    <span
      className="ol-pill"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        borderRadius: 999,
        background: colors.bg,
        color: colors.color,
        border: colors.bd === 'transparent' ? '0.5px solid transparent' : `0.5px solid ${colors.bd}`,
        fontWeight: 500,
        ...sizing,
        ...style,
      }}
    >
      {children}
    </span>
  );
}
