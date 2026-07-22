/**
 * Vela Tooltip 组件
 *
 * 基于 @radix-ui/react-tooltip 封装，自动适配深色/浅色主题。
 * 深色主题下显示浅色 Tooltip，浅色主题下显示深色 Tooltip。
 *
 * 用法：
 *   import { Tooltip, TooltipProvider, TooltipTrigger, TooltipContent } from '@/components/ui/Tooltip'
 *
 *   <TooltipProvider>
 *     <Tooltip>
 *       <TooltipTrigger asChild>
 *         <button>悬停查看</button>
 *       </TooltipTrigger>
 *       <TooltipContent>提示文字</TooltipContent>
 *     </Tooltip>
 *   </TooltipProvider>
 */

import * as React from 'react'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import { cn } from '../../lib/utils'

/** 全局 Provider（建议在 App.tsx 包裹一次即可） */
const TooltipProvider = TooltipPrimitive.Provider

/** Tooltip 根 */
const Tooltip = TooltipPrimitive.Root

/** 触发元素 */
const TooltipTrigger = TooltipPrimitive.Trigger

/**
 * Tooltip 内容气泡
 * 使用 CSS 变量 --color-tooltip-bg / --color-tooltip-text 自动适配主题
 */
const TooltipContent = React.forwardRef<
  React.ComponentRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 8, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        'z-[9999] overflow-hidden px-3 py-2 text-xs font-medium leading-relaxed',
        'rounded-xl border border-[var(--color-border)]',
        'bg-[var(--color-tooltip-bg)] text-[var(--color-tooltip-text)]',
        'shadow-xl shadow-black/15',
        /* 进出场动画 - 缩放 + 渐显 */
        'animate-in fade-in-0 zoom-in-95 duration-150',
        'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=closed]:duration-100',
        /* 根据方向微调偏移 */
        'data-[side=bottom]:slide-in-from-top-2',
        'data-[side=left]:slide-in-from-right-2',
        'data-[side=right]:slide-in-from-left-2',
        'data-[side=top]:slide-in-from-bottom-2',
        className
      )}
      style={{
        backdropFilter: 'blur(12px)',
      }}
      {...props}
    />
  </TooltipPrimitive.Portal>
))
TooltipContent.displayName = TooltipPrimitive.Content.displayName

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }
