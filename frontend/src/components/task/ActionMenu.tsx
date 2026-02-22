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

/**
 * 飞书风格操作菜单
 *
 * 特性：
 * - 三点图标触发
 * - 下拉菜单
 * - 危险操作红色高亮
 * - 分隔线支持
 */
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
        className={`
          p-1.5 rounded hover:bg-bg-hover text-text-tertiary hover:text-text-secondary
          transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed
        `}
        aria-label="操作菜单"
      >
        <MoreIcon />
      </button>

      {isOpen && (
        <div
          className="
            absolute right-0 top-full mt-1 w-36 bg-white rounded-lg shadow-lg
            border border-border-light py-1 z-50
          "
        >
          {visibleItems.map((item, index) => {
            const Icon = item.icon

            if (item.divider) {
              return (
                <div key={index} className="h-px bg-border-light my-1" />
              )
            }

            return (
              <button
                key={item.key}
                type="button"
                onClick={() => handleItemClick(item)}
                className={`
                  w-full px-3 py-2 flex items-center gap-2 text-small
                  hover:bg-bg-hover transition-colors duration-150
                  ${item.danger ? 'text-danger hover:bg-danger/10' : 'text-text-primary'}
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
