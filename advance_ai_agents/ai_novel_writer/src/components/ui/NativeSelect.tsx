import * as React from 'react'
import { cn } from '../../lib/utils'

/** 原生 select 的统一样式封装（轻量替代 Radix Select） */
const NativeSelect = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => {
    return (
      <select
        className={cn(
          'flex h-7 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-panel)] px-2 py-1 text-xs text-[var(--color-text)]',
          'focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)] focus:border-[var(--color-accent)]',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'appearance-none cursor-pointer',
          className
        )}
        ref={ref}
        {...props}
      >
        {children}
      </select>
    )
  }
)
NativeSelect.displayName = 'NativeSelect'

export { NativeSelect }
