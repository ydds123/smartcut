import React from 'react'

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number
  max?: number
  showLabel?: boolean
}

export const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  (
    { className = '', value, max = 100, showLabel = false, ...props },
    ref
  ) => {
    const percentage = Math.min(Math.max((value / max) * 100, 0), 100)

    return (
      <div ref={ref} className={`w-full ${className}`} {...props}>
        {showLabel && (
          <div className="flex justify-between text-sm mb-1">
            <span className="text-gray-600">进度</span>
            <span className="font-medium">{Math.round(percentage)}%</span>
          </div>
        )}
        <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
          <div
            className="bg-blue-600 h-2.5 rounded-full transition-all duration-300 ease-out"
            style={{ width: `${percentage}%` }}
            role="progressbar"
            aria-valuenow={value}
            aria-valuemin={0}
            aria-valuemax={max}
          />
        </div>
      </div>
    )
  }
)

Progress.displayName = 'Progress'
