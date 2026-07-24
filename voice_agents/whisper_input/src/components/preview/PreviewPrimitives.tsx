import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  ReactNode,
  TableHTMLAttributes,
} from 'react';

type PreviewButtonVariant = 'default' | 'primary' | 'danger';
type PreviewPillTone = 'default' | 'green' | 'blue' | 'purple' | 'orange';

interface PreviewCardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

interface PreviewButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: PreviewButtonVariant;
}

interface PreviewPageHeaderProps {
  title: ReactNode;
  desc?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

interface PreviewPillProps extends HTMLAttributes<HTMLSpanElement> {
  children: ReactNode;
  tone?: PreviewPillTone;
}

interface PreviewTableProps extends TableHTMLAttributes<HTMLTableElement> {
  headers?: ReactNode[];
  children: ReactNode;
}

export interface PreviewTabItem {
  id: string;
  label: ReactNode;
  desc?: ReactNode;
}

interface PreviewSettingsTabsProps {
  tabs: PreviewTabItem[];
  activeId: string;
  onChange: (id: string) => void;
  className?: string;
}

export interface PreviewModeOption {
  id: string;
  label: ReactNode;
  desc?: ReactNode;
}

interface PreviewModeSwitchProps {
  options: PreviewModeOption[];
  activeId: string;
  onChange: (id: string) => void;
  className?: string;
}

interface PreviewFieldRowProps extends HTMLAttributes<HTMLDivElement> {
  label: ReactNode;
  desc?: ReactNode;
  control: ReactNode;
}

interface PreviewHelpCardProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  title: ReactNode;
  children: ReactNode;
}

function joinClassNames(...classes: Array<string | false | undefined>) {
  return classes.filter(Boolean).join(' ');
}

export function PreviewCard({ children, className = '', ...props }: PreviewCardProps) {
  return (
    <div {...props} className={joinClassNames('wi-card', className)}>
      {children}
    </div>
  );
}

export function PreviewButton({ children, variant = 'default', className = '', type = 'button', ...props }: PreviewButtonProps) {
  const variantClass =
    variant === 'primary' ? 'wi-btn-primary' : variant === 'danger' ? 'wi-btn-danger' : undefined;

  return (
    <button {...props} type={type} className={joinClassNames('wi-btn', variantClass, className)}>
      {children}
    </button>
  );
}

export function PreviewPageHeader({ title, desc, actions, className = '' }: PreviewPageHeaderProps) {
  return (
    <header className={joinClassNames('wi-page-head', className)}>
      <div className="wi-page-title-block">
        <h1>{title}</h1>
        {desc && <p>{desc}</p>}
      </div>
      {actions && <div className="wi-page-actions">{actions}</div>}
    </header>
  );
}

export function PreviewPill({ children, tone = 'default', className = '', ...props }: PreviewPillProps) {
  const toneClass = tone === 'default' ? undefined : `wi-pill-${tone}`;

  return (
    <span {...props} className={joinClassNames('wi-pill', toneClass, className)}>
      {children}
    </span>
  );
}

export function PreviewTable({ headers, children, className = '', ...props }: PreviewTableProps) {
  return (
    <table {...props} className={joinClassNames('wi-table', className)}>
      {headers && (
        <thead>
          <tr>
            {headers.map((header, index) => (
              <th key={index}>{header}</th>
            ))}
          </tr>
        </thead>
      )}
      <tbody>{children}</tbody>
    </table>
  );
}

export function PreviewSettingsTabs({ tabs, activeId, onChange, className = '' }: PreviewSettingsTabsProps) {
  return (
    <div className={joinClassNames('wi-settings-tabs', className)} role="group">
      {tabs.map((tab) => {
        const active = tab.id === activeId;

        return (
          <button
            key={tab.id}
            type="button"
            className={joinClassNames('wi-settings-tab', active && 'wi-settings-tab-active')}
            aria-pressed={active}
            onClick={() => onChange(tab.id)}
          >
            <span className="wi-ellipsis">{tab.label}</span>
            {tab.desc && <span className="wi-settings-tab-desc wi-ellipsis">{tab.desc}</span>}
          </button>
        );
      })}
    </div>
  );
}

export function PreviewModeSwitch({ options, activeId, onChange, className = '' }: PreviewModeSwitchProps) {
  return (
    <div className={joinClassNames('wi-mode-switch', className)} role="group">
      {options.map((option) => {
        const active = option.id === activeId;

        return (
          <button
            key={option.id}
            type="button"
            className={joinClassNames('wi-mode-option', active && 'wi-mode-option-active')}
            aria-pressed={active}
            onClick={() => onChange(option.id)}
          >
            <span className="wi-ellipsis">{option.label}</span>
            {option.desc && <span className="wi-mode-option-desc wi-ellipsis">{option.desc}</span>}
          </button>
        );
      })}
    </div>
  );
}

export function PreviewFieldRow({ label, desc, control, className = '', ...props }: PreviewFieldRowProps) {
  return (
    <div {...props} className={joinClassNames('wi-field-row', className)}>
      <div>
        <div className="wi-field-label">{label}</div>
        {desc && <div className="wi-field-desc">{desc}</div>}
      </div>
      <div className="wi-field-control">{control}</div>
    </div>
  );
}

export function PreviewHelpCard({ title, children, className = '', ...props }: PreviewHelpCardProps) {
  return (
    <PreviewCard {...props} className={joinClassNames('wi-help-card', className)}>
      <h2 className="wi-help-card-title">{title}</h2>
      {children}
    </PreviewCard>
  );
}
