import type { ReactNode } from 'react'

interface TooltipProps {
  content: ReactNode
  children: ReactNode
  width?: string
  placement?: 'top' | 'bottom'
}

export function Tooltip({ content, children, width = 'w-64', placement = 'top' }: TooltipProps) {
  const isTop = placement === 'top'
  return (
    <span className="group relative inline-flex items-center">
      {children}
      <span
        className={`pointer-events-none absolute left-1/2 z-50 ${width} -translate-x-1/2 rounded-lg border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-panel)] px-3 py-2 text-xs text-[var(--sc-text-secondary)] opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100 ${isTop ? 'bottom-full mb-2' : 'top-full mt-2'}`}
      >
        {content}
        <span
          className={`absolute left-1/2 -translate-x-1/2 border-4 border-transparent ${isTop ? 'top-full border-t-[var(--sc-border-subtle)]' : 'bottom-full border-b-[var(--sc-border-subtle)]'}`}
        />
      </span>
    </span>
  )
}
