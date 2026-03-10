import { useState } from 'react'
import type { ReactNode } from 'react'
import {
  useFloating, autoUpdate, offset, flip, shift,
  useHover, useFocus, useDismiss, useRole, useInteractions,
  FloatingPortal,
} from '@floating-ui/react'

interface TooltipProps {
  content: ReactNode
  children: ReactNode
  width?: string
  placement?: 'top' | 'bottom'
  align?: 'center' | 'right'
}

export function Tooltip({ content, children, width = 'w-64', placement = 'top' }: TooltipProps) {
  const [open, setOpen] = useState(false)

  const { refs, floatingStyles, context } = useFloating({
    open,
    onOpenChange: setOpen,
    placement,
    middleware: [offset(8), flip(), shift({ padding: 8 })],
    whileElementsMounted: autoUpdate,
  })

  const hover = useHover(context, { move: false })
  const focus = useFocus(context)
  const dismiss = useDismiss(context)
  const role = useRole(context, { role: 'tooltip' })
  const { getReferenceProps, getFloatingProps } = useInteractions([hover, focus, dismiss, role])

  return (
    <>
      <span ref={refs.setReference} className="inline-flex items-center" {...getReferenceProps()}>
        {children}
      </span>
      {open && (
        <FloatingPortal>
          <div
            ref={refs.setFloating}
            style={floatingStyles}
            className={`z-50 ${width} rounded-lg border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-panel)] px-3 py-2 text-xs text-[var(--sc-text-secondary)] shadow-lg`}
            {...getFloatingProps()}
          >
            {content}
          </div>
        </FloatingPortal>
      )}
    </>
  )
}
