export const backendBase = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

function normalizeToDataPath(pathValue: string): string {
  const normalized = pathValue.replace(/\\/g, '/')
  const dataMarker = '/data/'
  const markerIndex = normalized.indexOf(dataMarker)
  if (markerIndex >= 0) {
    return normalized.slice(markerIndex)
  }
  return normalized
}

function encodePathSegment(segment: string): string {
  if (!segment) {
    return segment
  }
  try {
    return encodeURIComponent(decodeURIComponent(segment))
  } catch {
    return encodeURIComponent(segment)
  }
}

function splitKnownQuery(pathValue: string): { path: string; query: string } {
  const apiTokenMatch = pathValue.match(/([?&]api_token=[^#]*)$/)
  if (!apiTokenMatch) {
    return { path: pathValue, query: '' }
  }

  const rawQuery = apiTokenMatch[1]
  const path = pathValue.slice(0, -rawQuery.length)
  const query = rawQuery.startsWith('&') ? `?${rawQuery.slice(1)}` : rawQuery
  return { path, query }
}

function encodePath(pathValue: string): string {
  return pathValue
    .split('/')
    .map((segment, index) => (index === 0 ? segment : encodePathSegment(segment)))
    .join('/')
}

export function resolveAssetUrl(pathValue: string | null): string | null {
  if (!pathValue) {
    return null
  }

  const normalized = normalizeToDataPath(pathValue.trim())
  if (!normalized) {
    return null
  }

  if (normalized.startsWith('http://') || normalized.startsWith('https://')) {
    return normalized
  }

  const withLeadingSlash = normalized.startsWith('/') ? normalized : `/${normalized}`
  const { path, query } = splitKnownQuery(withLeadingSlash)
  const encodedPath = encodePath(path)
  return `${backendBase}${encodedPath}${query}`
}
