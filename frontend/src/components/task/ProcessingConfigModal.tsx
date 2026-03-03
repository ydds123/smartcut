import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Tooltip } from '@/components/ui/tooltip'
import type {
  DetectionMode,
  DetectorMode,
  ProcessingConfig,
  ProcessingConfigFieldMeta,
  ProcessingConfigMeta,
  ProcessingFieldGroup,
} from '@/types/task'
import { useDraggableModal } from '@/hooks/useDraggableModal'
import {
  buildDefaultProcessingSettings,
  persistProcessingSettings,
  type ProcessingPanelSettings,
} from './processingConfigSettings'

interface ProcessingConfigModalProps {
  isOpen: boolean
  initialSettings: ProcessingPanelSettings
  configMeta: ProcessingConfigMeta | null
  onClose: () => void
  onSave: (settings: ProcessingPanelSettings) => void
}

const FALLBACK_GROUPS: { id: ProcessingFieldGroup; label: string; description: string }[] = [
  { id: 'sensitivity', label: '切多 vs 切少', description: '控制触发切点的核心灵敏度，直接决定切出多少镜头' },
  { id: 'min-scene', label: '防碎片 / 最短镜头', description: '合并过短的镜头，减少碎片化切分' },
  { id: 'stability', label: '检测稳定性', description: '降低噪点和闪烁对检测的干扰，同时影响速度' },
  { id: 'transnet', label: 'TransNet 精度复核', description: '仅 Precision 模式下生效，二阶段精度提升' },
  { id: 'misc', label: '其他', description: '预览图和淡入淡出相关，不影响主要切分结果' },
]

function isNumericField(field: ProcessingConfigFieldMeta): boolean {
  return field.type === 'int' || field.type === 'float'
}

function isEnabledByBoolScope(
  field: ProcessingConfigFieldMeta,
  overrideConfig: Partial<ProcessingConfig>
): boolean {
  if (!field.boolScope) return true
  return Boolean(overrideConfig[field.boolScope])
}

function formatRangeNumber(value: number): string {
  if (Number.isInteger(value)) {
    return String(value)
  }
  return String(Number(value.toFixed(6)))
}

function formatActualRange(min?: number, max?: number): string {
  const hasMin = typeof min === 'number'
  const hasMax = typeof max === 'number'

  if (hasMin && hasMax) {
    return `${formatRangeNumber(min)} ~ ${formatRangeNumber(max)}`
  }
  if (hasMin) {
    return `>= ${formatRangeNumber(min)}（无上限）`
  }
  if (hasMax) {
    return `<= ${formatRangeNumber(max)}（无下限）`
  }
  return '未限制'
}

export function ProcessingConfigModal({
  isOpen,
  initialSettings,
  configMeta,
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

  const fieldGroups = useMemo(
    () => (configMeta?.groups?.length ? configMeta.groups : FALLBACK_GROUPS),
    [configMeta]
  )

  const numericFields = useMemo(
    () =>
      (configMeta?.fields || [])
        .filter((field): field is ProcessingConfigFieldMeta => isNumericField(field))
        .filter((field) => field.uiVisible !== false),
    [configMeta]
  )

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

  const resetToDefault = () => setDraft(buildDefaultProcessingSettings(configMeta))

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--sc-modal-overlay)] p-4">
      <div
        ref={modalRef}
        style={modalStyle}
        className="sc-modal-shell max-h-[85vh] w-full max-w-3xl overflow-hidden"
      >
        <div
          className={`sc-modal-header flex items-center justify-between ${dragging ? 'cursor-grabbing' : 'cursor-move'}`}
          onPointerDown={onHandlePointerDown}
        >
          <h2 className="text-sm font-semibold text-[var(--sc-text-primary)]">参数配置</h2>
          <button type="button" onClick={onClose} data-drag-ignore="true" className="sc-btn sc-btn-ghost h-7 px-2">
            关闭
          </button>
        </div>

        <div className="max-h-[68vh] overflow-y-auto px-5 py-4">
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
                  <div className="mt-1 text-[var(--sc-text-muted)]">适合：叙事片、对话、纪录片等大多数场景。</div>
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
                  <div>在 Content 基础上加入滚动平均，可减少抖动和闪烁导致的误切。</div>
                  <div className="mt-1 text-[var(--sc-text-muted)]">适合：运动镜头、快切、手持拍摄等不稳定素材。</div>
                </div>
              }>
                <span className="cursor-default select-none text-[11px] text-[var(--sc-text-muted)] hover:text-[var(--sc-text-secondary)]">ⓘ</span>
              </Tooltip>
            </label>
          </div>

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

          <div className="mb-4 flex flex-wrap items-center gap-4">
            <div className="w-16 text-sm font-medium text-[var(--sc-text-primary)]">后处理</div>
            <label className="inline-flex items-center gap-2 text-sm text-[var(--sc-text-primary)]">
              <Checkbox
                checked={Boolean(draft.overrideConfig.useThresholdDetector)}
                onChange={(event) => updateBoolField('useThresholdDetector', event.currentTarget.checked)}
              />
              启用淡入淡出检测
            </label>
          </div>

          <div className="mb-4 flex flex-wrap items-center gap-4">
            <div className="w-16 text-sm font-medium text-[var(--sc-text-primary)]">切分选项</div>
            <label className="inline-flex items-center gap-2 text-sm text-[var(--sc-text-primary)]">
              <Checkbox
                checked={Boolean(draft.overrideConfig.splitCopyMode)}
                onChange={(event) => updateBoolField('splitCopyMode', event.currentTarget.checked)}
              />
              使用 Copy 模式（不重编码，速度更快）
            </label>
          </div>

          {numericFields.length === 0 ? (
            <div className="rounded border border-[var(--sc-border-subtle)] bg-[var(--sc-bg-contrast)] px-3 py-2 text-xs text-[var(--sc-text-muted)]">
              参数元数据暂不可用，当前仅可使用已保存配置。
            </div>
          ) : (
            <div className="space-y-5">
              {fieldGroups.map((group) => {
                const fields = numericFields.filter((field) => {
                  if (field.group !== group.id) return false
                  if (field.detectorScope === 'adaptive' && draft.overrideConfig.detector !== 'adaptive') return false
                  if (field.detectorScope === 'content' && draft.overrideConfig.detector !== 'content') return false
                  if (field.modeScope === 'precision' && currentDetectionMode !== 'precision') return false
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
                      {fields.map((field) => {
                        const minValue = typeof field.min === 'number' ? field.min : undefined
                        const maxValue = typeof field.max === 'number' ? field.max : undefined
                        const stepValue = typeof field.step === 'number'
                          ? field.step
                          : (field.type === 'int' ? 1 : 0.1)
                        const actualRange = formatActualRange(minValue, maxValue)
                        const currentValue = draft.overrideConfig[field.key]
                        return (
                          <label key={String(field.key)} className="block rounded border border-[var(--sc-border-subtle)] px-3 py-2">
                            <div className="mb-1 flex items-baseline justify-between gap-2">
                              <span className="text-xs font-semibold text-[var(--sc-text-primary)]">
                                {field.label || field.key}
                              </span>
                              <span className="shrink-0 text-[10px] text-[var(--sc-text-muted)]">
                                范围：{actualRange}
                              </span>
                            </div>
                            <input
                              type="number"
                              value={currentValue === undefined || currentValue === null ? '' : String(currentValue)}
                              min={minValue}
                              max={maxValue}
                              step={stepValue}
                              disabled={!isEnabledByBoolScope(field, draft.overrideConfig)}
                              onChange={(event) => updateNumericField(field.key, event.currentTarget.value)}
                              className="sc-input w-full px-2 py-1 text-sm disabled:bg-[var(--sc-bg-contrast)]"
                            />
                            {field.description ? (
                              <div className="mt-1 text-[11px] text-[var(--sc-text-muted)]">{field.description}</div>
                            ) : null}
                          </label>
                        )
                      })}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <div className="sc-modal-footer flex items-center justify-between">
          <button
            type="button"
            onClick={resetToDefault}
            className="sc-btn sc-btn-ghost h-7 px-2 text-sm"
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
