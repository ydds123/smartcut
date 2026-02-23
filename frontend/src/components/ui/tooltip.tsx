import type { ReactNode } from 'react'

interface TooltipProps {
  content: ReactNode
  children: ReactNode
  width?: string
  placement?: 'top' | 'bottom'
  align?: 'center' | 'right'
}

export function Tooltip({ content, children, width = 'w-64', placement = 'top', align = 'center' }: TooltipProps) {
  const isTop = placement === 'top'
  const alignClass = align === 'right'
    ? 'right-0'
    : 'left-1/2 -translate-x-1/2'
  const arrowAlignClass = align === 'right'
    ? 'right-2'
    : 'left-1/2 -translate-x-1/2'
  return (
    <span className="group relative inline-flex items-center">
      {children}
      <span
        className={`pointer-events-none absolute ${alignClass} z-50 ${width} rounded-lg border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-panel)] px-3 py-2 text-xs text-[var(--sc-text-secondary)] opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100 ${isTop ? 'bottom-full mb-2' : 'top-full mt-2'}`}
      >
        {content}
        <span
          className={`absolute ${arrowAlignClass} border-4 border-transparent ${isTop ? 'top-full border-t-[var(--sc-border-subtle)]' : 'bottom-full border-b-[var(--sc-border-subtle)]'}`}
        />
      </span>
    </span>
  )
}
