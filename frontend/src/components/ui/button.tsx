import React from 'react'

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  isLoading?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className = '',
      variant = 'primary',
      size = 'md',
      isLoading = false,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--sc-focus-ring)] focus-visible:ring-offset-0 disabled:pointer-events-none disabled:opacity-50'

    const variantStyles = {
      primary:
        'border border-transparent bg-[var(--sc-accent)] text-white hover:bg-[var(--sc-accent-hover)]',
      secondary:
        'border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)] text-[var(--sc-text-primary)] hover:bg-[var(--sc-bg-elevated)]',
      danger:
        'border border-[var(--sc-danger-border)] bg-[var(--sc-danger-bg)] text-[var(--sc-danger-text)] hover:bg-[var(--sc-danger-bg-hover)]',
      ghost: 'text-[var(--sc-text-secondary)] hover:bg-[var(--sc-bg-elevated)] hover:text-[var(--sc-text-primary)]',
    }

    const sizeStyles = {
      sm: 'h-8 px-3 text-sm',
      md: 'h-10 px-4 text-base',
      lg: 'h-12 px-6 text-lg',
    }

    return (
      <button
        ref={ref}
        className={`${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading ? (
          <>
            <svg
              className="animate-spin -ml-1 mr-2 h-4 w-4"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            加载中...
          </>
        ) : (
          children
        )}
      </button>
    )
  }
)

Button.displayName = 'Button'
