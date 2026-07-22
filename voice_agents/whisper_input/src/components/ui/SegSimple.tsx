// SegSimple — segmented control used in the Settings modal sub-sections.

import { useState } from 'react';

interface SegSimpleProps {
  options: string[];
  active: string;
}

export function SegSimple({ options, active }: SegSimpleProps) {
  const [v, setV] = useState(active);
  return (
    <div style={{ display: 'inline-flex', padding: 2, borderRadius: 8, background: 'rgba(0,0,0,0.05)' }}>
      {options.map((o) => (
        <button
          key={o}
          onClick={() => setV(o)}
          style={{
            padding: '5px 12px', fontSize: 12, fontWeight: 500, border: 0, borderRadius: 6,
            fontFamily: 'inherit',
            background: v === o ? '#fff' : 'transparent',
            color: v === o ? 'var(--ol-ink)' : 'var(--ol-ink-3)',
            boxShadow: v === o ? '0 1px 2px rgba(0,0,0,.08)' : 'none',
            cursor: 'default',
          }}
        >
          {o}
        </button>
      ))}
    </div>
  );
}
