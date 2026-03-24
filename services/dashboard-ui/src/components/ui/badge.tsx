import * as React from 'react'
import { cn } from '@/lib/utils'

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: string
}

function Badge({ className, variant, children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        variant ? `badge-${variant}` : 'bg-zinc-100 text-zinc-600 border border-zinc-200',
        className
      )}
      {...props}
    >
      {children}
    </span>
  )
}

export { Badge }
