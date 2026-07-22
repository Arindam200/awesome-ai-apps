/**
 * Vela Skeleton 骨架屏加载组件
 *
 * 用于面板/列表加载时的占位效果，带呼吸动画。
 * 使用 CSS 变量 --color-skeleton 自动适配深色/浅色主题。
 *
 * 用法：
 *   import { Skeleton } from '@/components/ui/Skeleton'
 *   <Skeleton className="h-4 w-[200px]" />
 *   <Skeleton className="h-8 w-full rounded-lg" />
 */

import * as React from 'react'
import { cn } from '../../lib/utils'

type SkeletonProps = React.HTMLAttributes<HTMLDivElement>

/**
 * 骨架屏元素
 * 默认为圆角矩形，通过 className 控制宽高
 */
const Skeleton = React.forwardRef<HTMLDivElement, SkeletonProps>(
  ({ className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          'rounded-[var(--radius-md)]',
          className
        )}
        style={{
          backgroundColor: 'var(--color-skeleton)',
          animation: 'skeleton-pulse 1.8s cubic-bezier(0.4, 0, 0.6, 1) infinite',
          ...props.style,
        }}
        {...props}
      />
    )
  }
)
Skeleton.displayName = 'Skeleton'

export { Skeleton }
