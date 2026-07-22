import type { ReactNode } from 'react';

interface PageContainerProps {
  children: ReactNode;
  phase: 'idle' | 'exiting';
}

export function PageContainer({ children, phase }: PageContainerProps) {
  return (
    <main
      className="ol-thinscroll ol-page-container"
      style={{
        flex: 1,
        minHeight: 0,
        overflow: 'auto',
        overflowX: 'hidden',
        padding: 0,
        position: 'relative',
        animation: phase === 'exiting' ? 'ol-page-fadeout 0.12s linear forwards' : undefined,
        willChange: 'opacity, transform, filter',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {children}
    </main>
  );
}
