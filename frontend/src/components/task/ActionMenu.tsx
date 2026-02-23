import React, { useState, useRef, useEffect } from 'react'

const MoreIcon = () => (
  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
    <circle cx="12" cy="5" r="2" />
    <circle cx="12" cy="12" r="2" />
    <circle cx="12" cy="19" r="2" />
  </svg>
)

export interface ActionMenuItem {
  key: string
  label: string
  icon: React.ComponentType
  action: () => void
  show?: boolean
  danger?: boolean
  divider?: boolean
}

export interface ActionMenuProps {
  menuItems: ActionMenuItem[]
  disabled?: boolean
}

export function ActionMenu({ menuItems, disabled = false }: ActionMenuProps) {
  const [isOpen, setIsOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // 过滤需要显示的菜单项
  const visibleItems = menuItems.filter((item) => item.show !== false)

  // 点击外部关闭菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  const handleItemClick = (item: ActionMenuItem) => {
    item.action()
    setIsOpen(false)
  }

  return (
    <div ref={menuRef} className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled}
        className="sc-btn sc-btn-ghost h-8 w-8 p-1.5 disabled:cursor-not-allowed disabled:opacity-50"
        aria-label="操作菜单"
      >
        <MoreIcon />
      </button>

      {isOpen && (
        <div
          className="sc-menu absolute right-0 top-full z-50 mt-1 w-36 rounded-lg py-1"
        >
          {visibleItems.map((item, index) => {
            const Icon = item.icon

            if (item.divider) {
              return (
                <div key={index} className="my-1 h-px bg-[var(--sc-border-subtle)]" />
              )
            }

            return (
              <button
                key={item.key}
                type="button"
                onClick={() => handleItemClick(item)}
                className={`
                  sc-menu-item w-full px-3 py-2 flex items-center gap-2 text-small
                  ${item.danger ? 'sc-menu-item-danger' : ''}
                `}
              >
                <Icon />
                <span>{item.label}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
