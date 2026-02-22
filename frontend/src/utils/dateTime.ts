const ISO_WITHOUT_TZ = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/

/**
 * Parse backend datetime safely.
 * Backend currently returns UTC-like datetime strings without timezone suffix,
 * e.g. "2026-02-19T14:32:10.123456". We treat these as UTC.
 */
export function parseBackendDate(raw: string): Date {
  const value = (raw || '').trim()
  if (!value) {
    return new Date(NaN)
  }

  if (ISO_WITHOUT_TZ.test(value)) {
    return new Date(`${value}Z`)
  }

  return new Date(value)
}

export function toTimestamp(raw: string): number {
  const ts = parseBackendDate(raw).getTime()
  return Number.isNaN(ts) ? 0 : ts
}
