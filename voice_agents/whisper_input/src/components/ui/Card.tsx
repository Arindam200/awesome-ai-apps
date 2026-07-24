import type { CSSProperties, ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  style?: CSSProperties;
  padding?: number;
  glassy?: boolean;
  className?: string;
}

export function Card({ children, style, padding = 18, glassy = false, className }: CardProps) {
  return (
    <section
      className={['ol-card', className].filter(Boolean).join(' ')}
      style={{
        background: glassy ? 'rgba(255,255,255,0.64)' : 'var(--ol-card-bg, var(--ol-surface))',
        backdropFilter: glassy ? 'blur(20px) saturate(160%)' : undefined,
        WebkitBackdropFilter: glassy ? 'blur(20px) saturate(160%)' : undefined,
        border: '0 solid transparent',
        borderRadius: 18,
        padding,
        boxShadow: 'var(--ol-card-shadow, var(--ol-shadow-sm))',
        ...style,
      }}
    >
      {children}
    </section>
  );
}
