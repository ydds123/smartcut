const counters: Record<string, number> = {}

export function incrementClientCounter(name: string, by = 1): number {
  counters[name] = (counters[name] || 0) + by
  return counters[name]
}

export function getClientCountersSnapshot(): Record<string, number> {
  return { ...counters }
}
