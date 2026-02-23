import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Tooltip } from '@/components/ui/tooltip'
import type { DetectionMode, DetectorMode, ProcessingConfig } from '@/types/task'
import { useDraggableModal } from '@/hooks/useDraggableModal'
import {
  DEFAULT_PROCESSING_SETTINGS,
  persistProcessingSettings,
  type ProcessingPanelSettings,
} from './processingConfigSettings'

interface ProcessingConfigModalProps {
  isOpen: boolean
  initialSettings: ProcessingPanelSettings
  onClose: () => void
  onSave: (settings: ProcessingPanelSettings) => void
}

type FieldGroup = 'sensitivity' | 'min-scene' | 'stability' | 'transnet' | 'misc'

const FIELD_GROUPS: { id: FieldGroup; label: string; description: string }[] = [
  { id: 'sensitivity', label: '切多 vs 切少', description: '控制触发切点的核心灵敏度，直接决定切出多少镜头' },
  { id: 'min-scene', label: '防碎片 / 最短镜头', description: '合并过短的镜头，减少碎片化切分' },
  { id: 'stability', label: '检测稳定性', description: '降低噪点和闪烁对检测的干扰，同时影响速度' },
  { id: 'transnet', label: 'TransNet 精度复核', description: '仅 Precision 模式下生效，二阶段精度提升' },
  { id: 'misc', label: '其他', description: '预览图和淡入淡出相关，不影响主要切分结果' },
]

interface NumericFieldConfig {
  key: keyof ProcessingConfig
  label: string
  description: string
  lowEffect: string
  highEffect: string
  qualityTradeoff: string
  speedTradeoff: string
  recommendedRange: string
  group: FieldGroup
  detectorScope?: 'both' | 'adaptive'
  modeScope?: 'both' | 'precision'
  boolScope?: keyof ProcessingConfig
  min: number
  max: number
  step?: number
}

const NUMERIC_FIELDS: NumericFieldConfig[] = [
  {
    key: 'sceneThreshold',
    label: '切换灵敏度',
    description: '数值越小切得越多，越大切得越少。大多数视频用默认值 27 即可。',
    lowEffect: '更敏感，更容易切出新镜头，漏切更少。',
    highEffect: '更保守，误切更少，但可能漏掉轻微边界。',
    qualityTradeoff: '低值偏向防漏切，高值偏向防误切。',
    speedTradeoff: '对速度影响很小，主要影响切分密度。',
    recommendedRange: '24 - 32（叙事片常用 27 - 30）',
    group: 'sensitivity',
    min: 8,
    max: 60,
    step: 0.5,
  },
  {
    key: 'minSceneLenFrames',
    label: '最短镜头帧数',
    description: '短于这个帧数的镜头会被合并掉。调大可减少碎片化切分，调小可保留快速切换。',
    lowEffect: '允许更短镜头，能保留快速切换。',
    highEffect: '抑制碎片化，减少闪白/噪声造成的短镜头误切。',
    qualityTradeoff: '低值偏向防漏切，高值偏向防误切。',
    speedTradeoff: '速度影响很小，但高值会降低镜头数量。',
    recommendedRange: '10 - 30（当前默认 15）',
    group: 'min-scene',
    min: 4,
    max: 300,
    step: 1,
  },
  {
    key: 'minSceneDurationMsFloor',
    label: '最短镜头时长(ms)',
    description: '短于这个时长（毫秒）的镜头会被合并。1000 = 1 秒，调大可减少碎片镜头。',
    lowEffect: '允许更短镜头通过，快切片段保留更多。',
    highEffect: '强制合并短镜头，切分更稳定。',
    qualityTradeoff: '低值防漏切，高值防误切和碎片化。',
    speedTradeoff: '对检测速度影响小，但高值会降低镜头数量。',
    recommendedRange: '600 - 1200（默认 1000）',
    group: 'min-scene',
    min: 200,
    max: 3000,
    step: 50,
  },
  {
    key: 'downscale',
    label: '降采样倍数',
    description: '检测前缩小画面的倍数。设为 2 可减少噪点干扰，速度也更快；设为 1 保留最多细节。',
    lowEffect: '保留细节，更容易捕捉微小变化。',
    highEffect: '更抗噪声和闪烁，误触发更少。',
    qualityTradeoff: '低值细节更敏感，高值稳定性更高。',
    speedTradeoff: '高值通常更快（计算量更小）。',
    recommendedRange: '1 - 2（噪声多可用 2）',
    group: 'stability',
    min: 1,
    max: 8,
    step: 1,
  },
  {
    key: 'frameSkip',
    label: '跳帧数',
    description: '每隔几帧检测一次。0 = 逐帧最精准；1 = 隔帧更快但可能漏掉极短切点。',
    lowEffect: '逐帧检测，边界精度更高。',
    highEffect: '检测更快，但短时切点更容易漏掉。',
    qualityTradeoff: '低值质量更稳，高值漏切风险升高。',
    speedTradeoff: '高值提速明显。',
    recommendedRange: '0 - 1（质量优先建议 0）',
    group: 'stability',
    min: 0,
    max: 10,
    step: 1,
  },
  {
    key: 'adaptiveThreshold',
    label: '自适应判定阈值',
    description: 'Adaptive 检测器的核心灵敏度。越小越容易触发切点（防漏切），越大越保守（防误切）。',
    lowEffect: '更敏感，更容易触发切点。',
    highEffect: '更保守，减少误切。',
    qualityTradeoff: '低值防漏切，高值防误切。',
    speedTradeoff: '速度影响小，主要影响触发频率。',
    recommendedRange: '2.2 - 3.8（默认 3.0）',
    group: 'sensitivity',
    min: 0.8,
    max: 8,
    step: 0.1,
  },
  {
    key: 'adaptiveMinContentVal',
    label: '自适应最小变化量',
    description: '忽略小于此值的画面变化，可减少闪烁、噪点造成的误切。调大更稳定，调小更敏感。',
    lowEffect: '小变化也会被计入，切分更敏感。',
    highEffect: '过滤弱变化，闪烁导致的误切更少。',
    qualityTradeoff: '低值防漏切，高值防误切。',
    speedTradeoff: '速度影响小，主要影响鲁棒性。',
    recommendedRange: '12 - 20（默认 15）',
    group: 'sensitivity',
    min: 5,
    max: 60,
    step: 0.5,
  },
  {
    key: 'adaptiveFrameWindow',
    label: '自适应平滑窗口',
    description: '平滑计算的帧范围。越大边界越稳定，越小对瞬时变化越灵敏。',
    lowEffect: '响应快，对瞬时变化更灵敏。',
    highEffect: '平滑更强，边界更稳定。',
    qualityTradeoff: '低值更敏感，高值更稳健。',
    speedTradeoff: '速度影响小，主要影响稳定性。',
    recommendedRange: '2 - 4（默认 2）',
    group: 'stability',
    min: 1,
    max: 8,
    step: 1,
  },
  {
    key: 'thumbnailRetry',
    label: '缩略图重试次数',
    description: '缩略图生成失败时的重试次数，不影响切分结果，只影响预览图是否显示完整。',
    lowEffect: '失败后快速跳过，整体更快。',
    highEffect: '预览成功率更高，但耗时增加。',
    qualityTradeoff: '不影响镜头边界质量，只影响预览完整性。',
    speedTradeoff: '高值会增加处理耗时。',
    recommendedRange: '0 - 1（若不依赖缩略图可设 0）',
    group: 'misc',
    min: 0,
    max: 3,
    step: 1,
  },
  {
    key: 'thresholdDetectorThreshold',
    label: '淡出亮度阈值',
    description: '判定淡入淡出的亮度门槛。越小越容易触发，越大只捕捉非常明显的淡黑/淡白。',
    lowEffect: '更容易触发淡入淡出切点。',
    highEffect: '仅捕捉明显的淡黑/淡白。',
    qualityTradeoff: '低值防漏切，高值防误切。',
    speedTradeoff: '对速度影响很小。',
    recommendedRange: '8 - 20（默认 12）',
    group: 'misc',
    boolScope: 'useThresholdDetector',
    min: 0,
    max: 255,
    step: 1,
  },
  {
    key: 'thresholdDetectorFadeBias',
    label: '淡入淡出位置偏移(%)',
    description: '淡入淡出切点在过渡区间中的偏移百分比。-100 更靠前，+100 更靠后，0 在中点。',
    lowEffect: '更偏向过渡起始帧。',
    highEffect: '更偏向过渡结束帧。',
    qualityTradeoff: '低值可提前切点，高值可延后切点。',
    speedTradeoff: '对速度影响几乎没有。',
    recommendedRange: '-20 - 20（默认 0）',
    group: 'misc',
    boolScope: 'useThresholdDetector',
    min: -100,
    max: 100,
    step: 1,
  },
  {
    key: 'mergeGapFrames',
    label: '合并碎镜头间隔(帧)',
    description: '相邻切点间隔小于此帧数时自动合并，减少过于密集的切分。0 = 不启用合并。',
    lowEffect: '不合并或仅合并极短间隔。',
    highEffect: '合并更多相邻碎镜头，镜头数减少。',
    qualityTradeoff: '高值防碎片化，但可能合并真实切点。',
    speedTradeoff: '对速度影响极小。',
    recommendedRange: '0（不启用）或 3 - 8',
    group: 'min-scene',
    min: 0,
    max: 600,
    step: 1,
  },
  {
    key: 'transnetThreshold',
    label: 'TransNet 确认阈值',
    description: 'TransNetV2 确认切点的最低置信度（0~1）。越小保留越多切点，越大越严格。',
    lowEffect: '更多候选边界会被保留，漏切更少。',
    highEffect: '仅保留高置信边界，误切更少。',
    qualityTradeoff: '低值防漏切，高值防误切。',
    speedTradeoff: '主要影响边界筛选，不显著影响推理耗时。',
    recommendedRange: '0.30 - 0.45（默认 0.30）',
    group: 'transnet',
    modeScope: 'precision',
    boolScope: 'useTransnet',
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    key: 'transnetSoftCandidateMultiplier',
    label: 'TransNet 软保留倍率',
    description: '候选切点的软保留倍率，与确认阈值相乘得到软阈值。越小保留越多候选，越大越严格。',
    lowEffect: '更容易保留候选边界，减少漏切。',
    highEffect: '候选保留更严格，减少误切。',
    qualityTradeoff: '低值防漏切，高值防误切。',
    speedTradeoff: '仅影响后处理筛选，性能影响很小。',
    recommendedRange: '0.65 - 0.85（默认 0.75）',
    group: 'transnet',
    modeScope: 'precision',
    boolScope: 'useTransnet',
    min: 0.5,
    max: 1,
    step: 0.01,
  },
  {
    key: 'transnetAdditionalBoundaryThreshold',
    label: 'TransNet 补边阈值',
    description: 'TransNetV2 新增补充切点所需的最低置信度。越小补得越多，越大补得越保守。',
    lowEffect: '更容易新增补边，减少漏切。',
    highEffect: '补边更保守，减少过切风险。',
    qualityTradeoff: '低值偏补边，高值偏稳健。',
    speedTradeoff: '仅影响后处理逻辑，性能影响很小。',
    recommendedRange: '0.50 - 0.70（默认 0.55）',
    group: 'transnet',
    modeScope: 'precision',
    boolScope: 'useTransnet',
    min: 0,
    max: 1,
    step: 0.01,
  },
  {
    key: 'transnetToleranceFrames',
    label: 'TransNet 匹配容差(帧)',
    description: '候选切点与 TransNetV2 峰值匹配的容差帧数。越大匹配越宽松，越小越严格。',
    lowEffect: '匹配更严格，可能漏保留边界。',
    highEffect: '匹配更宽松，更多候选会被保留。',
    qualityTradeoff: '低值防误切，高值防漏切。',
    speedTradeoff: '性能影响小。',
    recommendedRange: '8 - 16（默认 12）',
    group: 'transnet',
    modeScope: 'precision',
    boolScope: 'useTransnet',
    min: 1,
    max: 100,
    step: 1,
  },
  {
    key: 'transnetOnlyMinGapFrames',
    label: 'TransNet 最小间隔(帧)',
    description: 'TransNetV2 补充切点与已有切点的最小间隔帧数，防止切点过于密集。',
    lowEffect: '允许更密集边界，容易切碎。',
    highEffect: '抑制近邻补边，边界更平滑。',
    qualityTradeoff: '低值防漏切，高值防误切。',
    speedTradeoff: '性能影响很小。',
    recommendedRange: '10 - 20（默认 12）',
    group: 'transnet',
    modeScope: 'precision',
    boolScope: 'useTransnet',
    min: 1,
    max: 300,
    step: 1,
  },
  {
    key: 'transnetWindowSize',
    label: 'TransNet 滑动窗口(帧)',
    description: 'TransNetV2 每次分析的滑动窗口大小。越大上下文越充分，边界越稳健；越小越灵敏。',
    lowEffect: '窗口更小，对瞬时边界更灵敏。',
    highEffect: '上下文更充分，边界更稳健。',
    qualityTradeoff: '低值灵敏，高值稳健。',
    speedTradeoff: '高值会增加推理计算量。',
    recommendedRange: '80 - 140（默认 100）',
    group: 'transnet',
    modeScope: 'precision',
    boolScope: 'useTransnet',
    min: 50,
    max: 400,
    step: 5,
  },
  {
    key: 'scenedetectTimeoutSec',
    label: '检测超时(秒)',
    description: 'PySceneDetect 命令最长执行时长。超时后会自动回退默认检测并最终降级为整片单场景。',
    lowEffect: '更快触发超时回退，防止任务长时间卡住。',
    highEffect: '允许更长检测时间，减少慢机器上的误超时。',
    qualityTradeoff: '主要影响任务可用性，不改变算法本身质量。',
    speedTradeoff: '高值会延后超时判定时机。',
    recommendedRange: '300 - 900（默认 600）',
    group: 'misc',
    min: 30,
    max: 3600,
    step: 30,
  },
]

export function ProcessingConfigModal({
  isOpen,
  initialSettings,
  onClose,
  onSave,
}: ProcessingConfigModalProps) {
  const [draft, setDraft] = useState<ProcessingPanelSettings>(initialSettings)
  const { modalRef, modalStyle, onHandlePointerDown, dragging } = useDraggableModal({ isOpen })

  useEffect(() => {
    if (isOpen) {
      setDraft(initialSettings)
    }
  }, [isOpen, initialSettings])

  if (!isOpen) return null

  const updateNumericField = (key: keyof ProcessingConfig, value: string) => {
    const parsed = Number(value)
    setDraft((previous) => ({
      ...previous,
      overrideConfig: {
        ...previous.overrideConfig,
        [key]: Number.isFinite(parsed) ? parsed : previous.overrideConfig[key],
      },
    }))
  }

  const updateDetector = (detector: DetectorMode) => {
    setDraft((previous) => ({
      ...previous,
      overrideConfig: { ...previous.overrideConfig, detector },
    }))
  }

  const updateDetectionMode = (detectionMode: DetectionMode) => {
    setDraft((previous) => ({
      ...previous,
      overrideConfig: {
        ...previous.overrideConfig,
        detectionMode,
        useTransnet: detectionMode === 'precision',
      },
    }))
  }

  const updateUseTransnet = (checked: boolean) => {
    setDraft((previous) => ({
      ...previous,
      overrideConfig: { ...previous.overrideConfig, useTransnet: checked },
    }))
  }

  const updateBoolField = (key: keyof ProcessingConfig, value: boolean) => {
    setDraft((previous) => ({
      ...previous,
      overrideConfig: { ...previous.overrideConfig, [key]: value },
    }))
  }

  const resetToDefault = () => setDraft(DEFAULT_PROCESSING_SETTINGS)

  const handleSubmit = () => {
    const settings: ProcessingPanelSettings = {
      ...draft,
      enableOverride: true,
    }
    persistProcessingSettings(settings)
    onSave(settings)
    onClose()
  }

  const currentDetectionMode: DetectionMode = draft.overrideConfig.detectionMode ?? 'fast'
  const transnetEnabled = Boolean(draft.overrideConfig.useTransnet) && currentDetectionMode === 'precision'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <div
        ref={modalRef}
        style={modalStyle}
        className="max-h-[85vh] w-full max-w-3xl overflow-hidden rounded-xl border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-panel)] shadow-[0_18px_45px_rgba(7,9,14,0.46)]"
      >
        {/* Header */}
        <div
          className={`flex items-center justify-between border-b border-[var(--sc-border-subtle)] bg-[var(--sc-bg-panel)] px-5 py-3 ${dragging ? 'cursor-grabbing' : 'cursor-move'}`}
          onPointerDown={onHandlePointerDown}
        >
          <h2 className="text-lg font-semibold text-[var(--sc-text-primary)]">参数配置</h2>
          <button type="button" onClick={onClose} data-drag-ignore="true" className="sc-btn sc-btn-ghost h-7 px-2">
            关闭
          </button>
        </div>

        {/* Body */}
        <div className="max-h-[68vh] overflow-y-auto px-5 py-4">
          {/* 检测器 */}
          <div className="mb-3 flex flex-wrap items-center gap-4">
            <div className="w-16 text-sm font-medium text-[var(--sc-text-primary)]">检测器</div>
            <label className="inline-flex items-center gap-2 text-sm text-[var(--sc-text-primary)]">
              <input
                type="radio"
                checked={draft.overrideConfig.detector === 'content'}
                onChange={() => updateDetector('content')}
              />
              Content（稳定叙事）
              <Tooltip width="w-72" placement="bottom" align="right" content={
                <div>
                  <div className="mb-1 font-semibold text-[var(--sc-text-primary)]">Content 检测器</div>
                  <div>逐帧比较色彩（色相、饱和度、亮度、边缘）的变化量，超过阈值就判定为切点。</div>
                  <div className="mt-1 text-[var(--sc-text-muted)]">适合：叙事片、对话、纪录片等大多数场景。是最通用的默认选择。</div>
                </div>
              }>
                <span className="cursor-default select-none text-[11px] text-[var(--sc-text-muted)] hover:text-[var(--sc-text-secondary)]">ⓘ</span>
              </Tooltip>
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-[var(--sc-text-primary)]">
              <input
                type="radio"
                checked={draft.overrideConfig.detector === 'adaptive'}
                onChange={() => updateDetector('adaptive')}
              />
              Adaptive（运动/闪变场景）
              <Tooltip width="w-72" placement="bottom" align="right" content={
                <div>
                  <div className="mb-1 font-semibold text-[var(--sc-text-primary)]">Adaptive 检测器</div>
                  <div>在 Content 基础上加了滚动平均：先算每帧的变化量，再与前后几帧的均值比较，过滤掉摄像机抖动和闪烁造成的误切。</div>
                  <div className="mt-1 text-[var(--sc-text-muted)]">适合：运动镜头、MV、快切、手持拍摄等不稳定素材。系统自动调优也会在误切多时切换到此模式。</div>
                </div>
              }>
                <span className="cursor-default select-none text-[11px] text-[var(--sc-text-muted)] hover:text-[var(--sc-text-secondary)]">ⓘ</span>
              </Tooltip>
            </label>
          </div>

          {/* 运行模式 */}
          <div className="mb-3 flex flex-wrap items-center gap-4">
            <div className="w-16 text-sm font-medium text-[var(--sc-text-primary)]">运行模式</div>
            <label className="inline-flex items-center gap-2 text-sm text-[var(--sc-text-primary)]">
              <input
                type="radio"
                checked={currentDetectionMode === 'fast'}
                onChange={() => updateDetectionMode('fast')}
              />
              Fast
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-[var(--sc-text-primary)]">
              <input
                type="radio"
                checked={currentDetectionMode === 'precision'}
                onChange={() => updateDetectionMode('precision')}
              />
              Precision
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-[var(--sc-text-primary)]">
              <Checkbox
                checked={transnetEnabled}
                onChange={(event) => updateUseTransnet(event.currentTarget.checked)}
                disabled={currentDetectionMode !== 'precision'}
              />
              启用 TransNetV2
            </label>
          </div>

          {/* 后处理 */}
          <div className="mb-4 flex flex-wrap items-center gap-4">
            <div className="w-16 text-sm font-medium text-[var(--sc-text-primary)]">后处理</div>
            <label className="inline-flex items-center gap-2 text-sm text-[var(--sc-text-primary)]">
              <Checkbox
                checked={Boolean(draft.overrideConfig.useThresholdDetector)}
                onChange={(event) => updateBoolField('useThresholdDetector', event.currentTarget.checked)}
              />
              启用淡入淡出检测
              <Tooltip width="w-72" align="right" content={
                <div>
                  <div className="mb-1 font-semibold text-[var(--sc-text-primary)]">Threshold 检测器（叠加）</div>
                  <div>专门检测画面渐黑/渐白的淡入淡出过渡，不检测快切。会与主检测器同时运行，补充主检测器漏掉的淡变切点。</div>
                  <div className="mt-1 text-[var(--sc-text-muted)]">适合：有意使用淡入淡出转场的影片、专业制作内容。普通快切视频无需开启。</div>
                </div>
              }>
                <span className="cursor-default select-none text-[11px] text-[var(--sc-text-muted)] hover:text-[var(--sc-text-secondary)]">ⓘ</span>
              </Tooltip>
            </label>
          </div>

          {/* 切分选项 */}
          <div className="mb-4 flex flex-wrap items-center gap-4">
            <div className="w-16 text-sm font-medium text-[var(--sc-text-primary)]">切分选项</div>
            <label className="inline-flex items-center gap-2 text-sm text-[var(--sc-text-primary)]">
              <Checkbox
                checked={Boolean(draft.overrideConfig.splitCopyMode)}
                onChange={(event) => updateBoolField('splitCopyMode', event.currentTarget.checked)}
              />
              使用 Copy 模式（不重编码，速度更快）
              <Tooltip placement="bottom" width="w-80" align="right" content={
                <div>
                  <div className="mb-1 font-semibold text-[var(--sc-text-primary)]">Copy 模式</div>
                  <div>直接复制视频流，不重新编码，速度快约 10 倍，画质完全无损。</div>
                  <div className="mt-1 text-[var(--sc-text-muted)]">
                    ⚠️ 注意：切点若不在关键帧上，片段开头可能出现上一镜头的残留帧（约 0.5-2 秒）。适合关键帧密集的 H.264 视频，不适合专业格式（ProRes、DNxHD）。
                  </div>
                </div>
              }>
                <span className="cursor-default select-none text-[11px] text-[var(--sc-text-muted)] hover:text-[var(--sc-text-secondary)]">ⓘ</span>
              </Tooltip>
            </label>
          </div>

          {/* 数值字段（按效果分组） */}
          <div className="space-y-5">
            {FIELD_GROUPS.map((group) => {
              const fields = NUMERIC_FIELDS.filter((f) => {
                if (f.group !== group.id) return false
                if (f.detectorScope === 'adaptive' && draft.overrideConfig.detector !== 'adaptive') return false
                if (f.modeScope === 'precision' && currentDetectionMode !== 'precision') return false
                return true
              })
              if (fields.length === 0) return null
              return (
                <div key={group.id}>
                  <div className="mb-2 border-b border-[var(--sc-border-subtle)] pb-1">
                    <span className="text-xs font-semibold text-[var(--sc-text-secondary)]">{group.label}</span>
                    <span className="ml-2 text-[11px] text-[var(--sc-text-muted)]">{group.description}</span>
                  </div>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    {fields.map((field) => (
                      <label key={field.key} className="block rounded border border-[var(--sc-border-subtle)] px-3 py-2">
                        <div className="mb-1 flex items-baseline justify-between gap-2">
                          <span className="text-xs font-semibold text-[var(--sc-text-primary)]">{field.label}</span>
                          <span className="shrink-0 text-[10px] text-[var(--sc-text-muted)]">推荐：{field.recommendedRange}</span>
                        </div>
                        <input
                          type="number"
                          value={String(draft.overrideConfig[field.key] ?? '')}
                          min={field.min}
                          max={field.max}
                          step={field.step ?? 1}
                          disabled={field.boolScope !== undefined && !draft.overrideConfig[field.boolScope]}
                          onChange={(event) => updateNumericField(field.key, event.currentTarget.value)}
                          className="sc-input w-full px-2 py-1 text-sm disabled:bg-[var(--sc-bg-contrast)]"
                        />
                        <div className="mt-1 text-[11px] text-[var(--sc-text-muted)]">{field.description}</div>
                      </label>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-[var(--sc-border-subtle)] px-5 py-3">
          <button
            type="button"
            onClick={resetToDefault}
            className="text-sm text-primary hover:text-primary-hover"
          >
            恢复默认
          </button>
          <Button size="sm" onClick={handleSubmit}>
            开始处理
          </Button>
        </div>
      </div>
    </div>
  )
}
