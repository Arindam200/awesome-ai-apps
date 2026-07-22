import React from 'react'

interface Props extends React.HTMLAttributes<HTMLDivElement> {
  icon?: React.ReactNode
  message: string
  opacity?: number
}

export function EmptyState({ icon, message, opacity = 0.3, className, ...props }: Props) {
  return (
    <div
      className={`flex flex-col items-center justify-center h-full gap-3 ${className || ''}`}
      style={{ opacity, ...props.style }}
      {...props}
    >
      {icon}
      <span className="text-sm">{message}</span>
      {props.children}
    </div>
  )
}
