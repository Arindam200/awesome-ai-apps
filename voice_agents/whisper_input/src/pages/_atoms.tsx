// _atoms.tsx — shared display atoms used across the page bodies.

import { useState, type CSSProperties, type ReactNode } from 'react';
import { Icon } from '../components/Icon';

interface PageHeaderProps {
  kicker?: string;
  title: string;
  desc?: string;
  right?: ReactNode;
}

export function PageHeader({ kicker, title, desc, right }: PageHeaderProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 24, marginBottom: 24 }}>
      <div style={{ minWidth: 0 }}>
        {kicker && (
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '.08em', textTransform: 'uppercase', color: 'var(--ol-ink-4)', marginBottom: 8 }}>{kicker}</div>
        )}
        <h1 style={{ margin: 0, fontSize: 28, lineHeight: 1.16, fontWeight: 720, letterSpacing: 0, color: 'var(--ol-ink)', textWrap: 'balance' }}>{title}</h1>
        {desc && <p style={{ margin: '9px 0 0', fontSize: 13, color: 'var(--ol-ink-3)', maxWidth: 660, lineHeight: 1.6, textWrap: 'pretty' }}>{desc}</p>}
      </div>
      {right}
    </div>
  );
}

interface CardProps {
  children: ReactNode;
  style?: CSSProperties;
  padding?: number;
  glassy?: boolean;
  className?: string;
}

export function Card({ children, style, padding = 18, glassy = false, className }: CardProps) {
  return (
    <div
      className={className}
      style={{
        background: glassy ? 'rgba(255,255,255,0.64)' : 'var(--ol-card-bg, var(--ol-surface))',
        backdropFilter: glassy ? 'blur(20px) saturate(160%)' : undefined,
        WebkitBackdropFilter: glassy ? 'blur(20px) saturate(160%)' : undefined,
        border: '0 solid transparent',
        borderRadius: '18px',
        padding,
        boxShadow: 'var(--ol-card-shadow, var(--ol-shadow-sm))',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

export type PillTone = 'default' | 'blue' | 'ok' | 'outline' | 'dark';
export type PillSize = 'sm' | 'md';

interface PillProps {
  children: ReactNode;
  tone?: PillTone;
  size?: PillSize;
  style?: CSSProperties;
}

export function Pill({ children, tone = 'default', size = 'md', style }: PillProps) {
  const tones: Record<PillTone, { bg: string; color: string; bd: string }> = {
    default: { bg: 'rgba(0,0,0,0.05)',   color: 'var(--ol-ink-2)',  bd: 'transparent' },
    blue:    { bg: 'var(--ol-blue-soft)',color: 'var(--ol-blue)',   bd: 'transparent' },
    ok:      { bg: 'var(--ol-ok-soft)',  color: 'var(--ol-ok)',     bd: 'transparent' },
    outline: { bg: 'transparent',        color: 'var(--ol-ink-3)',  bd: 'var(--ol-line-strong)' },
    dark:    { bg: 'var(--ol-ink)',      color: '#fff',             bd: 'transparent' },
  };
  const t = tones[tone];
  const sz = size === 'sm'
    ? { padding: '2px 8px', fontSize: 10.5 }
    : { padding: '4px 10px', fontSize: 11.5 };
  return (
    <span
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        borderRadius: 999,
        background: t.bg,
        color: t.color,
        border: t.bd === 'transparent' ? '0.5px solid transparent' : `0.5px solid ${t.bd}`,
        fontWeight: 500,
        ...sz,
        ...style,
      }}
    >
      {children}
    </span>
  );
}

export type BtnVariant = 'primary' | 'blue' | 'ghost' | 'soft';
export type BtnSize = 'sm' | 'md';

interface BtnProps {
  children: ReactNode;
  variant?: BtnVariant;
  size?: BtnSize;
  icon?: string;
  style?: CSSProperties;
  onClick?: () => void;
  disabled?: boolean;
}

export function Btn({ children, variant = 'ghost', size = 'md', icon, style, onClick, disabled = false }: BtnProps) {
  const variants: Record<BtnVariant, { bg: string; color: string; bd: string; sh: string }> = {
    primary: { bg: 'var(--ol-ink)',     color: '#fff',                bd: 'transparent', sh: '0 1px 2px rgba(0,0,0,.08)' },
    blue:    { bg: 'var(--ol-blue)',    color: '#fff',                bd: 'transparent', sh: '0 1px 2px rgba(37,99,235,.18)' },
    ghost:   { bg: 'transparent',       color: 'var(--ol-ink-2)',     bd: 'var(--ol-line-strong)', sh: 'none' },
    soft:    { bg: 'rgba(0,0,0,0.04)',  color: 'var(--ol-ink-2)',     bd: 'transparent', sh: 'none' },
  };
  const v = variants[variant];
  const sizes: Record<BtnSize, { padding: string; fontSize: number }> = {
    sm: { padding: '5px 10px', fontSize: 12 },
    md: { padding: '7px 14px', fontSize: 12.5 },
  };
  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        background: v.bg, color: v.color,
        border: v.bd === 'transparent' ? '0.5px solid transparent' : `0.5px solid ${v.bd}`,
        borderRadius: 8,
        boxShadow: v.sh,
        fontFamily: 'inherit', fontWeight: 500,
        cursor: disabled ? 'not-allowed' : 'default',
        opacity: disabled ? 0.55 : 1,
        transition: 'background 0.16s var(--ol-motion-quick), color 0.16s var(--ol-motion-quick), border-color 0.16s var(--ol-motion-quick), box-shadow 0.18s var(--ol-motion-soft), transform 0.12s var(--ol-motion-quick)',
        ...sizes[size],
        ...style,
      }}
    >
      {icon && <Icon name={icon} size={13} />}
      {children}
    </button>
  );
}

interface CollapsibleProps {
  /// 标题行内容（短文案，居左）。
  title: ReactNode;
  /// 可选的副标题 / 描述（小字，居标题下方）。
  desc?: ReactNode;
  /// 默认是否展开。默认 false（折叠，符合"默认只显示标题 + 右箭头"语义）。
  defaultOpen?: boolean;
  /// 嵌在 Card padding=0 容器里时设为 true：移除上下 margin，仅靠 Card 的 borderBottom 分割。
  embedded?: boolean;
  children: ReactNode;
}

/// 折叠栏：默认收起，标题行右侧显示一个 `›` 箭头，点击切换展开/收起。展开时箭头
/// 旋转 90°。内容区域用 `grid-template-rows: 0fr ↔ 1fr` 过渡——浏览器把 `1fr`
/// 解析为内容实际高度，过渡到真实高度，避免 max-height 固定大值时短内容也走完
/// 整段动画 / 短内容关闭时延迟生效的"卡卡"感。要求 Chromium 117+（Tauri 自带），
/// 现代版本完全支持。
///
/// `embedded=true`：嵌在 `<Card padding={0}>` 里、与其他 Collapsible 共享一张 Card 时使用，
/// 底部加一道 0.5px 分隔。
/// `embedded=false`：独立 block，自带 Card 同款外观（border / radius / shadow）。
export function Collapsible({ title, desc, defaultOpen = false, embedded = false, children }: CollapsibleProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      style={{
        borderBottom: embedded ? '1px solid rgba(148,163,184,0.18)' : undefined,
        border: embedded ? undefined : '0 solid transparent',
        borderRadius: embedded ? 0 : 18,
        background: embedded ? 'transparent' : 'var(--ol-card-bg, var(--ol-surface))',
        boxShadow: embedded ? 'none' : 'var(--ol-card-shadow, var(--ol-shadow-sm))',
        overflow: 'hidden',
        // 父级 flex column 带 minHeight:0 + overflow:auto 时，所有 flex 子项默认
        // shrink:1，会把 header 按钮也压成一条线。锁住不压缩，溢出走父容器滚动。
        flexShrink: 0,
      }}
    >
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        // 让屏幕阅读器朗读折叠状态；键盘 focus 保留浏览器默认 outline 而不是
        // outline: 'none'，避免 Tab 切换时丢失视觉焦点指示（pr-agent #407 反馈）。
        style={{
          width: '100%',
          padding: '14px 18px',
          background: 'transparent',
          border: 0,
          textAlign: 'left',
          fontFamily: 'inherit',
          color: 'inherit',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          cursor: 'pointer',
        }}
      >
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{title}</div>
          {desc && (
            <div style={{ fontSize: 11.5, color: 'var(--ol-ink-4)', marginTop: 3, lineHeight: 1.5 }}>{desc}</div>
          )}
        </div>
        <span
          aria-hidden="true"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 18,
            height: 18,
            color: 'var(--ol-ink-4)',
            transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
            transition: 'transform 0.18s var(--ol-motion-quick)',
          }}
        >
          <Icon name="chevRight" size={14} />
        </span>
      </button>
      <div
        style={{
          display: 'grid',
          // grid-template-rows: 0fr → 1fr 让浏览器把 1fr 解析为内容实际高度。
          gridTemplateRows: open ? '1fr' : '0fr',
          transition: 'grid-template-rows 0.22s var(--ol-motion-soft)',
        }}
        // inert 把内部交互元素从 tab 顺序 + a11y 树移除，避免折叠后键盘用户
        // 仍能 tab 到不可见的输入框 / 按钮 / Toggle（pr-agent #407 反馈）。
        // 受支持范围：Chromium 102+（Tauri WebView 远高于此）/ Safari 15.4+。
        // React 18 类型没收 `inert`，用 spread 传 string-boolean 绕过编译器。
        {...(!open ? { inert: '' } : {})}
        aria-hidden={!open}
      >
        {/* minHeight: 0 必填：默认 grid item 不允许收缩到小于内容固有高度，
            没这条 trick 不生效，行高动画也跟着失败。 */}
        <div style={{ overflow: 'hidden', minHeight: 0 }}>
          <div style={{ padding: '0 18px 18px' }}>{children}</div>
        </div>
      </div>
    </div>
  );
}
