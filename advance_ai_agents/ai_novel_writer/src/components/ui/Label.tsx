import * as React from 'react'
import { cn } from '../../lib/utils'

const Label = React.forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => {
    return (
      <label
        className={cn(
          'text-xs font-medium leading-none text-[var(--color-text-muted)] mb-1 block',
          'peer-disabled:cursor-not-allowed peer-disabled:opacity-70',
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Label.displayName = 'Label'

export { Label }
