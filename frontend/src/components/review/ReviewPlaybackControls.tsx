import { clamp, formatMsAdaptive } from './reviewUtils'

interface ReviewPlaybackControlsProps {
  playheadMs: number
  durationMs: number
  isPlaying: boolean
  playbackRate: number
  playbackRateOptions: number[]
  variant?: 'inline' | 'overlay'
  className?: string
  onSeek: (targetMs: number) => void
  onStepSecondBack: () => void
  onStepSecondForward: () => void
  onTogglePlay: () => void
  onPlaybackRateChange: (rate: number) => void
}

export function ReviewPlaybackControls({
  playheadMs,
  durationMs,
  isPlaying,
  playbackRate,
  playbackRateOptions,
  variant = 'inline',
  className,
  onSeek,
  onStepSecondBack,
  onStepSecondForward,
  onTogglePlay,
  onPlaybackRateChange,
}: ReviewPlaybackControlsProps) {
  const safeDurationMs = Math.max(0, durationMs)
  const maxDuration = Math.max(safeDurationMs, 1)
  const safePlayheadMs = clamp(playheadMs, 0, safeDurationMs)
  const displayTimeText = `${formatMsAdaptive(safePlayheadMs)}/${formatMsAdaptive(safeDurationMs)}`
  const isOverlay = variant === 'overlay'
  const rootClassName = [
    'flex items-center gap-2',
    isOverlay
      ? 'rounded-lg border border-white/15 bg-black/65 px-3 py-2 backdrop-blur-sm shadow-[0_10px_30px_rgba(0,0,0,0.35)]'
      : 'border-b border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)] px-4',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={rootClassName}>
      <button
        type="button"
        onClick={onTogglePlay}
        className={`sc-btn sc-btn-secondary h-7 px-2 ${isOverlay ? 'border-white/20 bg-black/25 text-white hover:bg-black/40' : ''}`}
      >
        {isPlaying ? '暂停' : '播放'}
      </button>

      <button
        type="button"
        onClick={onStepSecondBack}
        className={`sc-btn sc-btn-secondary h-7 px-2 ${isOverlay ? 'border-white/20 bg-black/25 text-white/90 hover:bg-black/40' : 'text-[var(--sc-text-secondary)]'}`}
      >
        -1s
      </button>

      <button
        type="button"
        onClick={onStepSecondForward}
        className={`sc-btn sc-btn-secondary h-7 px-2 ${isOverlay ? 'border-white/20 bg-black/25 text-white/90 hover:bg-black/40' : 'text-[var(--sc-text-secondary)]'}`}
      >
        +1s
      </button>

      <select
        value={playbackRate}
        onChange={(event) => onPlaybackRateChange(Number(event.target.value))}
        className={`sc-input h-7 px-2 text-xs ${isOverlay ? 'border-white/20 bg-black/35 text-white' : ''}`}
        aria-label="预览播放速度"
      >
        {playbackRateOptions.map((rate) => (
          <option key={rate} value={rate}>
            {rate}x
          </option>
        ))}
      </select>

      <input
        type="range"
        min={0}
        max={maxDuration}
        value={clamp(playheadMs, 0, maxDuration)}
        onChange={(event) => onSeek(Number(event.target.value))}
        className={`sc-range ml-2 h-1.5 flex-1 ${isOverlay ? 'min-w-[180px]' : ''}`}
      />

      <span className={`w-36 text-right font-mono text-xs ${isOverlay ? 'text-white/85' : 'text-[var(--sc-text-muted)]'}`}>{displayTimeText}</span>
    </div>
  )
}
