/* eslint-disable react-refresh/only-export-components */
/**
 * Vela Badge 标签组件
 *
 * 轻量级标签组件，用于状态标识、分类标注等场景。
 * 支持多种语义变体，自动适配双主题。
 *
 * 用法：
 *   import { Badge } from '@/components/ui/Badge'
 *   <Badge variant="success">已完成</Badge>
 *   <Badge variant="default">默认</Badge>
 */

import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const badgeVariants = cva(
  /* 基础样式：内联 flex、圆角胶囊、小号文字、无换行 */
  'inline-flex items-center px-2 py-0.5 text-[0.7rem] font-medium rounded-full whitespace-nowrap leading-none transition-all duration-200',
  {
    variants: {
      variant: {
        /** 默认 — 品牌色底 + 品牌色文字 */
        default:
          'bg-[var(--color-badge-bg)] text-[var(--color-badge-text)]',
        /** 成功 — 绿色系 */
        success:
          'bg-[color-mix(in_srgb,var(--color-success)_15%,transparent)] text-[var(--color-success)]',
        /** 警告 — 橙色系 */
        warning:
          'bg-[color-mix(in_srgb,var(--color-warning)_15%,transparent)] text-[var(--color-warning)]',
        /** 错误 — 红色系 */
        error:
          'bg-[color-mix(in_srgb,var(--color-error)_15%,transparent)] text-[var(--color-error)]',
        /** 轮廓 — 透明底 + 边框 */
        outline:
          'border border-[var(--color-border)] text-[var(--color-text-secondary)] bg-transparent',
        /** 纯色强调 — 白字品牌底（如"默认"标签） */
        solid:
          'bg-[var(--color-accent)] text-white',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant, ...props }, ref) => {
    return (
      <span
        ref={ref}
        className={cn(badgeVariants({ variant }), className)}
        {...props}
      />
    )
  }
)
Badge.displayName = 'Badge'

export { Badge, badgeVariants }
