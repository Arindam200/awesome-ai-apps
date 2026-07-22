// Row — two-column row used in the Settings modal sub-sections.

import type { ReactNode } from 'react';

interface RowProps {
  label: string;
  desc?: string;
  children: ReactNode;
}

export function Row({ label, desc, children }: RowProps) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr', gap: 16, padding: '12px 0', borderTop: '0.5px solid var(--ol-line-soft)' }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--ol-ink)' }}>{label}</div>
        {desc && <div style={{ fontSize: 12.5, color: 'var(--ol-ink-4)', marginTop: 4, lineHeight: 1.55 }}>{desc}</div>}
      </div>
      <div style={{ display: 'flex', alignItems: 'center' }}>{children}</div>
    </div>
  );
}
