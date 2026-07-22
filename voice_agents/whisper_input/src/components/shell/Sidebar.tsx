import { Icon } from '../Icon';
import { APP_VERSION_LABEL } from '../../lib/appVersion';

export interface SidebarItem {
  id: string;
  icon: string;
  label: string;
  active: boolean;
  onClick: () => void;
}

interface SidebarProps {
  items: SidebarItem[];
}

export function Sidebar({ items }: SidebarProps) {
  return (
    <aside className="wi-sidebar">
      <nav className="wi-side-nav">
        {items.map(item => (
          <button
            key={item.id}
            type="button"
            className={item.active ? 'active' : ''}
            aria-current={item.active ? 'page' : undefined}
            onClick={item.onClick}
          >
            <Icon name={item.icon} size={24} strokeWidth={2} />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
      <div className="wi-side-foot">
        <div>版本 {APP_VERSION_LABEL}</div>
        <div><span className="wi-side-dot" />云端语音输入</div>
      </div>
    </aside>
  );
}
