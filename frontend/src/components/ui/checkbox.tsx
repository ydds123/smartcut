import React from 'react'

export type CheckboxProps = React.InputHTMLAttributes<HTMLInputElement>

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className = '', ...props }, ref) => {
    return (
      <input
        ref={ref}
        type="checkbox"
        className={`relative h-4 w-4 cursor-pointer appearance-none rounded border border-[var(--sc-border-strong)] bg-[var(--sc-bg-contrast)] transition-[background-color,border-color,box-shadow] outline-none focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--sc-focus-ring)] focus-visible:ring-offset-0 checked:border-[var(--sc-accent)] checked:bg-[var(--sc-accent)] checked:before:absolute checked:before:left-[4px] checked:before:top-[1px] checked:before:h-[8px] checked:before:w-[4px] checked:before:rotate-45 checked:before:border-b-2 checked:before:border-r-2 checked:before:border-white checked:before:content-[''] disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
        {...props}
      />
    )
  }
)

Checkbox.displayName = 'Checkbox'
