// Icon.tsx — preview.html stroke icons. Navigation paths must stay aligned with the prototype.
// Usage: <Icon name="overview" size={16} />

import type { CSSProperties } from 'react';

export const ICONS: Record<string, string | string[]> = {
  overview: [
    'M3 11.5 12 4l9 7.5',
    'M6 10.5V20h12v-9.5',
    'M10 20v-6h4v6',
  ],
  history: [
    'M3 12a9 9 0 1 0 3-6.7',
    'M3 4v5h5',
    'M12 7v6l4 2',
  ],
  vocab: [
    'M5 4h10a3 3 0 0 1 3 3v14H7a2 2 0 0 1-2-2z',
    'M8 8h6M8 12h5',
  ],
  style: [
    'M4 20c4-1 7-3 9-7',
    'M12 13 20 5l-1-1-8 8',
    'M14 5l5 5',
  ],
  translate:'M3 5h7M6 4v2M5 8c0 4 3 6 5 6M9 8c0 4-3 6-5 6M13 20l4-10 4 10M14.5 17h5',
  selectionAsk:'M4 6h11M4 10h11M4 14h7M17 14a3 3 0 1 1 3 3v1M20 22h.01',
  settings: [
    'M12 15.5A3.5 3.5 0 1 0 12 8a3.5 3.5 0 0 0 0 7.5z',
    'M19.4 15a7.6 7.6 0 0 0 .1-1.2 7.6 7.6 0 0 0-.1-1.2l2-1.5-2-3.5-2.4 1a7.5 7.5 0 0 0-2-1.2L14.7 5h-4l-.4 2.5a7.5 7.5 0 0 0-2 1.2l-2.4-1-2 3.5 2 1.5a7.6 7.6 0 0 0-.1 1.2c0 .4 0 .8.1 1.2l-2 1.5 2 3.5 2.4-1a7.5 7.5 0 0 0 2 1.2l.4 2.5h4l.4-2.5a7.5 7.5 0 0 0 2-1.2l2.4 1 2-3.5-2-1.5z',
  ],
  help:    'M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z',
  sun:     'M12 4V2M12 22v-2M4.93 4.93L3.52 3.52M20.48 20.48l-1.41-1.41M4 12H2M22 12h-2M4.93 19.07l-1.41 1.41M20.48 3.52l-1.41 1.41M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z',
  moon:    'M21 14.5A8.5 8.5 0 0 1 9.5 3a7 7 0 1 0 11.5 11.5z',
  mic:     'M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3zM19 11a7 7 0 0 1-14 0M12 18v3M8 21h8',
  search:  'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-4.5-4.5',
  plus:    'M12 5v14M5 12h14',
  minus:   'M5 12h14',
  maximize:'M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3',
  check:   'M5 12l4 4 10-10',
  x:       'M6 6l12 12M6 18L18 6',
  pin:     'M12 17v5M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4a1 1 0 0 1 1 1z',
  copy:    'M9 9h10v10H9zM5 15V5h10',
  eye:     'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zM12 9.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5z',
  trash:   'M4 7h16M9 7V4h6v3M6 7v13a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7M10 11v7M14 11v7',
  refresh: 'M4 4v6h6M20 20v-6h-6M4 10a8 8 0 0 1 14-3l2 3M20 14a8 8 0 0 1-14 3l-2-3',
  sparkle: 'M12 3v3M12 18v3M5 12H2M22 12h-3M6 6l-2-2M20 20l-2-2M6 18l-2 2M20 4l-2 2M12 8a4 4 0 0 0 4 4 4 4 0 0 0-4 4 4 4 0 0 0-4-4 4 4 0 0 0 4-4z',
  bolt:    'M13 2L4 14h7l-1 8 9-12h-7l1-8z',
  clock:   'M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z',
  hash:    'M5 9h14M5 15h14M10 3l-2 18M16 3l-2 18',
  chevDown:'M6 9l6 6 6-6',
  chevRight:'M9 6l6 6-6 6',
  chevLeft:'M15 6l-6 6 6 6',
  chevLR:  'M8 5l-3 7 3 7M16 5l3 7-3 7',
  collapse:'M9 4h11v16H9M14 9l-3 3 3 3M4 4v16',
  expand:  'M4 4h16v16H4zM10 9l-3 3 3 3M14 9l3 3-3 3',
  layout:  'M3 4h18v6H3zM3 14h7v6H3zM14 14h7v6h-7z',
  cmd:     'M9 6a3 3 0 1 0 0 6h6a3 3 0 1 0 0-6 3 3 0 0 0-3 3v6a3 3 0 1 0 3-3H9a3 3 0 1 0 3 3z',
  option:  'M5 6h4l5 12h5M14 6h5',
  esc:     'M3 7h18v10H3zM7 10l3 4M7 14l3-4M14 10v4M14 14h3M14 10h3M14 12h3',
  enter:   'M21 7v4a3 3 0 0 1-3 3H5M9 18l-4-4 4-4',
  inserted:'M5 12l4 4 10-10',
  cloud:   'M7 18h11a4 4 0 0 0 .5-8A6 6 0 0 0 7 11a4 4 0 0 0 0 7z',
  mac:     'M16 4a4 4 0 0 0-4 4 4 4 0 0 0-4-4C5 4 3 7 3 11s2 9 5 9c1.5 0 2-1 4-1s2.5 1 4 1c3 0 5-5 5-9s-2-7-5-7zM13 4c0-1 1-2 2-2',
  win:     'M3 5l8-1v8H3zM12 4l9-1v9h-9zM3 13h8v8l-8-1zM12 13h9v8l-9-1z',
  doc:     'M6 3h8l5 5v13H6zM14 3v5h5',
  link:    'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 1 0-5.7-5.7L11 7M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 1 0 5.7 5.7L13 17',
  filter:  'M3 5h18l-7 9v6l-4-2v-4z',
  archive: 'M3 4h18v4H3zM5 8v12h14V8M9 12h6',
  tag:     'M3 11V3h8l10 10-8 8L3 11zM7 7h.01',
  user:    'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0',
  mail:    'M3 6h18v12H3zM3 6l9 7 9-7',
  info:    'M12 8h.01M11 12h1v4h1M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z',
  external:'M9 5h10v10M19 5L9 15M5 9v10h10',
  close:   'M6 6l12 12M6 18L18 6',
};

export interface IconProps {
  name: string;
  size?: number;
  stroke?: string;
  strokeWidth?: number;
  fill?: string;
  style?: CSSProperties;
  className?: string;
}

export function Icon({
  name,
  size = 16,
  stroke = 'currentColor',
  strokeWidth = 1.5,
  fill = 'none',
  style,
  className,
}: IconProps) {
  const d = ICONS[name];
  if (!d) return null;
  const paths = Array.isArray(d) ? d : [d];
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={fill}
      stroke={stroke}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={style}
      className={className}
      aria-hidden="true"
    >
      {paths.map(path => <path key={path} d={path} />)}
    </svg>
  );
}
