/**
 * 通用图标按钮
 * 统一替换 AgentHeader.HeaderIconBtn 和 AgentConversation.ToolbarIconBtn
 *
 * 尺寸规范：
 * - 22: 活动栏图标 (22x22px)
 * - 18: 工具窗口栏图标 (18x18px)
 * - 14: 树形项目图标 (14x14px)
 * - 12: 状态栏图标 (12x12px)
 */
export interface IconBtnProps {
  children: React.ReactNode
  title: string
  onClick?: () => void
  disabled?: boolean
  /** 高亮激活态（背景 + 颜色加深） */
  active?: boolean
  /** 数字徽标（>0 时显示蓝色小圆点） */
  badge?: number
  /** 图标按钮尺寸 (px)，默认为 22 */
  size?: 12 | 18 | 22
}

export function IconBtn({ children, title, onClick, disabled, active, badge, size = 22 }: IconBtnProps) {
  return (
    <button
      title={title}
      disabled={disabled}
      onClick={onClick}
      className="group relative flex items-center justify-center rounded transition-colors"
      style={{
        width: `${size}px`,
        height: `${size}px`,
        color: active ? 'var(--color-text)' : 'var(--color-text-secondary)',
        opacity: disabled ? 0.4 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        backgroundColor: active ? 'var(--color-hover)' : 'transparent',
      }}
      onMouseEnter={e => {
        if (!disabled && !active) {
          e.currentTarget.style.backgroundColor = 'var(--color-hover)'
          e.currentTarget.style.color = 'var(--color-text)'
        }
      }}
      onMouseLeave={e => {
        if (!active) {
          e.currentTarget.style.backgroundColor = 'transparent'
          e.currentTarget.style.color = 'var(--color-text-secondary)'
        }
      }}
    >
      {children}
      {/* 数字徽标小圆点 */}
      {badge !== undefined && badge > 0 && (
        <span
          className="absolute top-0.5 right-0.5 w-2 h-2 rounded-full"
          style={{ backgroundColor: 'var(--color-accent)' }}
        />
      )}
    </button>
  )
}
