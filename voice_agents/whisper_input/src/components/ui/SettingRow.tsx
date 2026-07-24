import type { ReactNode } from 'react';

interface SettingRowProps {
  label: string;
  desc?: string;
  children: ReactNode;
  controlWidth?: number | string;
}

export function SettingRow({ label, desc, children, controlWidth }: SettingRowProps) {
  return (
    <div
      className="ol-setting-row"
      style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 180px) minmax(0, 1fr)',
        gap: 16,
        padding: '14px 0',
        borderTop: '0.5px solid var(--ol-line-soft)',
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div className="ol-setting-label" style={{ fontSize: 13, fontWeight: 500, color: 'var(--ol-ink)' }}>
          {label}
        </div>
        {desc && (
          <div
            className="ol-setting-desc"
            style={{ fontSize: 12.5, color: 'var(--ol-ink-4)', marginTop: 4, lineHeight: 1.55 }}
          >
            {desc}
          </div>
        )}
      </div>
      <div
        className="ol-setting-control"
        style={{ display: 'flex', alignItems: 'flex-start', minWidth: 0, width: controlWidth ?? 'auto' }}
      >
        {children}
      </div>
    </div>
  );
}
