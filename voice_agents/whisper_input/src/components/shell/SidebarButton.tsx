import { forwardRef, type ButtonHTMLAttributes, type CSSProperties, type ReactNode } from 'react';

interface SidebarButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
  icon: ReactNode;
  label: string;
  style?: CSSProperties;
}

export const SidebarButton = forwardRef<HTMLButtonElement, SidebarButtonProps>(function SidebarButton(
  { active = false, icon, label, className = '', style, ...props },
  ref,
) {
  const classes = [
    active ? 'ol-nav-btn ol-nav-btn-active' : 'ol-nav-btn',
    className,
  ].filter(Boolean).join(' ');

  return (
    <button
      {...props}
      ref={ref}
      type="button"
      className={classes}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '7px 10px',
        borderRadius: 8,
        border: 0,
        background: 'transparent',
        fontFamily: 'inherit',
        fontSize: 13,
        cursor: 'default',
        transition: 'color 0.16s var(--ol-motion-quick), background 0.16s var(--ol-motion-quick)',
        textAlign: 'left',
        position: 'relative',
        zIndex: 1,
        ...style,
      }}
    >
      {icon}
      <span style={{ flex: 1 }}>{label}</span>
    </button>
  );
});
