export const backendBase = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export function formatMs(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60

  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }

  return `${m}:${String(s).padStart(2, '0')}`
}

export function formatMsFull(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  const frac = Math.floor((ms % 1000) / 100)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${frac}`
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function resolveAssetUrl(pathValue: string | null): string | null {
  if (!pathValue) {
    return null
  }

  const normalized = pathValue.trim()
  if (!normalized) {
    return null
  }

  if (normalized.startsWith('http://') || normalized.startsWith('https://')) {
    return normalized
  }

  const withLeadingSlash = normalized.startsWith('/') ? normalized : `/${normalized}`
  return `${backendBase}${encodeURI(withLeadingSlash)}`
}
