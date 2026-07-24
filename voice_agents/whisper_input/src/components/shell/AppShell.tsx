import type { ReactNode } from 'react';
import type { OS } from '../WindowChrome';

interface AppShellProps {
  os: OS;
  sidebar: ReactNode;
  commandBar?: ReactNode;
  footer?: ReactNode;
  overlays?: ReactNode;
  children: ReactNode;
}

export function AppShell({ sidebar, commandBar, footer, overlays, children }: AppShellProps) {
  return (
    <div className="wi-stage">
      <div className="wi-shell">
        {sidebar}
        <div className="wi-main">
          {commandBar && <div className="wi-top-tools">{commandBar}</div>}
          <section className="wi-content">
            {children}
          </section>
        </div>
      </div>
      {footer}
      {overlays}
    </div>
  );
}
