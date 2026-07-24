// SelectLite — dropdown-styled display used in the Settings modal sub-sections.

import { Icon } from '../Icon';

interface SelectLiteProps {
  value: string;
}

export function SelectLite({ value }: SelectLiteProps) {
  return (
    <div
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 8,
        padding: '6px 10px', fontSize: 12.5,
        borderRadius: 8, border: '0.5px solid var(--ol-line-strong)',
        background: 'var(--ol-surface-2)',
        minWidth: 200, justifyContent: 'space-between',
      }}
    >
      <span>{value}</span>
      <Icon name="chevDown" size={11} />
    </div>
  );
}
