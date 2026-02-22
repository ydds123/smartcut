import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

interface UseDraggableModalOptions {
  isOpen: boolean
  disabled?: boolean
  margin?: number
}

interface DragState {
  startClientX: number
  startClientY: number
  startOffsetX: number
  startOffsetY: number
  width: number
  height: number
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function useDraggableModal({
  isOpen,
  disabled = false,
  margin = 16,
}: UseDraggableModalOptions) {
  const modalRef = useRef<HTMLDivElement | null>(null)
  const dragStateRef = useRef<DragState | null>(null)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const [dragging, setDragging] = useState(false)

  useEffect(() => {
    if (!isOpen) {
      return
    }
    dragStateRef.current = null
    setDragging(false)
    setOffset({ x: 0, y: 0 })
  }, [isOpen])

  const onHandlePointerDown = useCallback(
    (event: React.PointerEvent<HTMLElement>) => {
      if (disabled || event.button !== 0) {
        return
      }

      const target = event.target as HTMLElement
      if (target.closest('[data-drag-ignore="true"]')) {
        return
      }

      const modalElement = modalRef.current
      if (!modalElement) {
        return
      }

      const rect = modalElement.getBoundingClientRect()
      dragStateRef.current = {
        startClientX: event.clientX,
        startClientY: event.clientY,
        startOffsetX: offset.x,
        startOffsetY: offset.y,
        width: rect.width,
        height: rect.height,
      }
      setDragging(true)
      event.preventDefault()
    },
    [disabled, offset.x, offset.y]
  )

  useEffect(() => {
    if (!dragging) {
      return
    }

    const onPointerMove = (event: PointerEvent) => {
      const state = dragStateRef.current
      if (!state) {
        return
      }

      const rawX = state.startOffsetX + (event.clientX - state.startClientX)
      const rawY = state.startOffsetY + (event.clientY - state.startClientY)

      const maxX = Math.max(margin, (window.innerWidth - state.width) / 2)
      const maxY = Math.max(margin, (window.innerHeight - state.height) / 2)

      setOffset({
        x: Math.round(clamp(rawX, -maxX + margin, maxX - margin)),
        y: Math.round(clamp(rawY, -maxY + margin, maxY - margin)),
      })
    }

    const onPointerUp = () => {
      setDragging(false)
      dragStateRef.current = null
    }

    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    window.addEventListener('pointercancel', onPointerUp)

    return () => {
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
      window.removeEventListener('pointercancel', onPointerUp)
    }
  }, [dragging, margin])

  const modalStyle = useMemo(
    () => ({
      transform: `translate3d(${offset.x}px, ${offset.y}px, 0)`,
    }),
    [offset.x, offset.y]
  )

  return {
    modalRef,
    modalStyle,
    onHandlePointerDown,
    dragging,
  }
}
