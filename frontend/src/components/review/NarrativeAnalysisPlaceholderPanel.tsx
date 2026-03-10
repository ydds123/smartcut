export function NarrativeAnalysisPlaceholderPanel() {
  return (
    <div className="sc-panel flex h-full min-h-0 flex-col rounded-xl p-3">
      <div className="sc-surface rounded-lg border border-[var(--sc-border-subtle)] px-3 py-2.5">
        <h3 className="text-sm font-semibold text-[var(--sc-text-primary)]">叙事单元分析（规划中）</h3>
        <p className="mt-1 text-xs leading-5 text-[var(--sc-text-muted)]">
          后续将按“第几幕”组织镜头，并在此展示每幕的主题、叙事推进与镜头作用分析。
        </p>
      </div>

      <div className="mt-3 min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        <section className="rounded-lg border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)] px-3 py-3">
          <p className="text-xs font-semibold text-[var(--sc-text-secondary)]">示例结构</p>
          <ul className="mt-2 space-y-1.5 text-xs text-[var(--sc-text-muted)]">
            <li>第一幕：世界与冲突建立</li>
            <li>第二幕：冲突升级与转折</li>
            <li>第三幕：高潮与结局收束</li>
          </ul>
        </section>

        <section className="rounded-lg border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)] px-3 py-3">
          <p className="text-xs font-semibold text-[var(--sc-text-secondary)]">内容占位</p>
          <div className="mt-2 space-y-2">
            <div className="h-3 w-1/2 animate-pulse rounded bg-[var(--sc-bg-elevated)]" />
            <div className="h-3 w-full animate-pulse rounded bg-[var(--sc-bg-elevated)]" />
            <div className="h-3 w-11/12 animate-pulse rounded bg-[var(--sc-bg-elevated)]" />
            <div className="h-3 w-5/6 animate-pulse rounded bg-[var(--sc-bg-elevated)]" />
          </div>
        </section>
      </div>
    </div>
  )
}
