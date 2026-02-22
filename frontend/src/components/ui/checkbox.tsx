import React from 'react'

export type CheckboxProps = React.InputHTMLAttributes<HTMLInputElement>

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className = '', ...props }, ref) => {
    return (
      <input
        ref={ref}
        type="checkbox"
        className={`h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-2 focus:ring-blue-500 focus:ring-offset-0 ${className}`}
        {...props}
      />
    )
  }
)

Checkbox.displayName = 'Checkbox'
