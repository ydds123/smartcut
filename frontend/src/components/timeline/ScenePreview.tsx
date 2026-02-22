import { Card } from '@/components/ui/card'
import type { Scene } from '@/types/task'

interface ScenePreviewProps {
  scene: Scene
}

export function ScenePreview({ scene }: ScenePreviewProps) {
  // 格式化时间码 (毫秒 -> HH:MM:SS.mmm)
  const formatTime = (ms: number): string => {
    const totalSeconds = Math.floor(ms / 1000)
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.floor((totalSeconds % 3600) / 60)
    const seconds = totalSeconds % 60
    const milliseconds = ms % 1000

    return `${hours.toString().padStart(2, '0')}:${minutes
      .toString()
      .padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${milliseconds
      .toString()
      .padStart(3, '0')}`
  }

  return (
    <Card variant="bordered" className="p-4">
      <div className="space-y-2">
        {/* 缩略图 */}
        {scene.thumbnailPath && (
          <div className="aspect-video bg-black rounded overflow-hidden">
            <img
              src={scene.thumbnailPath}
              alt={`Scene ${scene.sequenceIndex + 1}`}
              className="w-full h-full object-cover"
            />
          </div>
        )}

        {/* 时间码 */}
        <div className="text-sm text-[#d4d4d8]">
          <span className="font-mono">{formatTime(scene.startMs)}</span>
          <span className="mx-2">→</span>
          <span className="font-mono">{formatTime(scene.endMs)}</span>
        </div>

        {/* 序号 */}
        <div className="text-xs text-[#71717a]">
          镜头 #{scene.sequenceIndex + 1}
        </div>
      </div>
    </Card>
  )
}
