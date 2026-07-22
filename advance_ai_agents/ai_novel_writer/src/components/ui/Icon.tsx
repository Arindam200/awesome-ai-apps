/**
 * Vela Icon 组件
 *
 * 统一 lucide-react 图标封装，提供标准化的尺寸系统。
 *
 * 图标尺寸规范：
 * - 12px: 状态栏、徽章指示器
 * - 14px: 按钮图标前缀、树形项目图标
 * - 16px: 菜单项图标
 * - 18px: 工具窗口栏图标
 * - 22px: 活动栏图标
 *
 * 用法：
 *   import { Icon } from '@/components/ui/Icon'
 *   import { Sparkles } from 'lucide-react'
 *
 *   <Icon icon={Sparkles} size={14} />
 *   <Icon icon={Settings} size={18} />
 */

import { type LucideProps, type LucideIcon } from 'lucide-react'

export type IconSize = 12 | 14 | 16 | 18 | 22

interface IconProps extends Omit<LucideProps, 'ref'> {
  /** 图标名称 */
  icon: LucideIcon
  /** 图标尺寸 (px)，默认为 14 */
  size?: IconSize
}

// Size mapping: pixel size -> Tailwind class
const sizeClasses: Record<IconSize, string> = {
  12: 'w-3 h-3',
  14: 'w-3.5 h-3.5',
  16: 'w-4 h-4',
  18: 'w-[18px] h-[18px]',
  22: 'w-[22px] h-[22px]',
}

export function Icon({ icon: IconComponent, size = 14, className, ...props }: IconProps) {
  return (
    <IconComponent
      className={sizeClasses[size] + (className ? ` ${className}` : '')}
      {...props}
    />
  )
}

// Re-export lucide-react types for convenience
export type { LucideProps, LucideIcon }
