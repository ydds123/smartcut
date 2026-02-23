import { clamp, formatMsFull } from './reviewUtils'

interface ReviewPlaybackControlsProps {
  playheadMs: number
  durationMs: number
  isPlaying: boolean
  playbackRate: number
  playbackRateOptions: number[]
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
  onSeek,
  onStepSecondBack,
  onStepSecondForward,
  onTogglePlay,
  onPlaybackRateChange,
}: ReviewPlaybackControlsProps) {
  const maxDuration = Math.max(durationMs, 1)

  return (
    <div className="flex items-center gap-2 border-b border-[var(--sc-border-subtle)] bg-[var(--sc-bg-surface)] px-4">
      <button
        type="button"
        onClick={onTogglePlay}
        className="sc-btn sc-btn-secondary h-7 px-2"
      >
        {isPlaying ? '暂停' : '播放'}
      </button>

      <button
        type="button"
        onClick={onStepSecondBack}
        className="sc-btn sc-btn-secondary h-7 px-2 text-[var(--sc-text-secondary)]"
      >
        -1s
      </button>

      <button
        type="button"
        onClick={onStepSecondForward}
        className="sc-btn sc-btn-secondary h-7 px-2 text-[var(--sc-text-secondary)]"
      >
        +1s
      </button>

      <select
        value={playbackRate}
        onChange={(event) => onPlaybackRateChange(Number(event.target.value))}
        className="sc-input h-7 px-2 text-xs"
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
        className="sc-range ml-2 h-1.5 flex-1"
      />

      <span className="w-28 text-right font-mono text-xs text-[var(--sc-text-muted)]">{formatMsFull(playheadMs)}</span>
    </div>
  )
}
