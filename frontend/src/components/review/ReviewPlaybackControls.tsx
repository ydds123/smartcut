import { clamp, formatMsFull } from './reviewUtils'

interface ReviewPlaybackControlsProps {
  playheadMs: number
  durationMs: number
  isPlaying: boolean
  onSeek: (targetMs: number) => void
  onStepSecondBack: () => void
  onStepSecondForward: () => void
  onTogglePlay: () => void
}

export function ReviewPlaybackControls({
  playheadMs,
  durationMs,
  isPlaying,
  onSeek,
  onStepSecondBack,
  onStepSecondForward,
  onTogglePlay,
}: ReviewPlaybackControlsProps) {
  const maxDuration = Math.max(durationMs, 1)

  return (
    <div className="flex items-center gap-2 border-b border-[#27272a] bg-[#0f0f0f] px-4">
      <button
        type="button"
        onClick={onTogglePlay}
        className="rounded border border-[#3f3f46] bg-[#18181b] px-2 py-1 text-xs text-[#d4d4d8] hover:bg-[#27272a]"
      >
        {isPlaying ? '暂停' : '播放'}
      </button>

      <button
        type="button"
        onClick={onStepSecondBack}
        className="rounded border border-[#3f3f46] bg-[#18181b] px-2 py-1 text-xs text-[#a1a1aa] hover:bg-[#27272a]"
      >
        -1s
      </button>

      <button
        type="button"
        onClick={onStepSecondForward}
        className="rounded border border-[#3f3f46] bg-[#18181b] px-2 py-1 text-xs text-[#a1a1aa] hover:bg-[#27272a]"
      >
        +1s
      </button>

      <input
        type="range"
        min={0}
        max={maxDuration}
        value={clamp(playheadMs, 0, maxDuration)}
        onChange={(event) => onSeek(Number(event.target.value))}
        className="ml-2 h-1.5 flex-1 accent-[#2563eb]"
      />

      <span className="w-28 text-right font-mono text-xs text-[#a1a1aa]">{formatMsFull(playheadMs)}</span>
    </div>
  )
}
