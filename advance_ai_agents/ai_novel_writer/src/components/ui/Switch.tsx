/**
 * Vela Switch 开关组件
 *
 * 从 SettingsModal 中提取的通用开关组件，
 * 自动适配双主题、支持 disabled 态。
 *
 * 用法：
 *   import { Switch } from '@/components/ui/Switch'
 *   <Switch checked={enabled} onCheckedChange={setEnabled} />
 */

import * as React from 'react'
import { cn } from '../../lib/utils'

interface SwitchProps {
  /** 当前状态 */
  checked: boolean
  /** 状态变更回调 */
  onCheckedChange: (checked: boolean) => void
  /** 是否禁用 */
  disabled?: boolean
  /** 自定义 className */
  className?: string
  /** 无障碍标签 */
  'aria-label'?: string
}

/**
 * 开关组件 — 40×20px 规格，圆形滑块
 * 使用 CSS 变量适配主题，动画使用 --transition-fast
 */
const Switch = React.forwardRef<HTMLButtonElement, SwitchProps>(
  ({ checked, onCheckedChange, disabled, className, ...props }, ref) => {
    return (
      <button
        ref={ref}
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => !disabled && onCheckedChange(!checked)}
        className={cn(
          'relative inline-flex items-center flex-shrink-0 cursor-pointer',
          'w-10 h-5 rounded-full',
          'transition-colors',
          disabled && 'opacity-50 cursor-not-allowed',
          className
        )}
        style={{
          backgroundColor: checked ? 'var(--color-accent)' : 'var(--color-border)',
          transitionDuration: 'var(--transition-fast)',
        }}
        {...props}
      >
        {/* 滑块圆点 */}
        <span
          className="inline-block w-4 h-4 rounded-full bg-white shadow-sm"
          style={{
            transform: checked ? 'translateX(22px)' : 'translateX(2px)',
            transition: `transform var(--transition-fast)`,
          }}
        />
      </button>
    )
  }
)
Switch.displayName = 'Switch'

export { Switch }
