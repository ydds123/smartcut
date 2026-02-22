import React from 'react'

export type CheckboxProps = React.InputHTMLAttributes<HTMLInputElement>

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className = '', ...props }, ref) => {
    return (
      <input
        ref={ref}
        type="checkbox"
        className={`h-4 w-4 cursor-pointer rounded border-[#52525b] bg-[#09090b] accent-primary focus:ring-2 focus:ring-primary focus:ring-offset-0 focus:ring-offset-[#0f0f0f] ${className}`}
        {...props}
      />
    )
  }
)

Checkbox.displayName = 'Checkbox'
