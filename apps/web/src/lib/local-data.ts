/**
 * A registry of "forget this student's data on this device" hooks. A module that keeps its own local copies (IndexedDB,
 * a queue) registers one at load; account deletion runs them all without importing those modules (which would be a cycle).
 */
type Clearer = (userId: string) => Promise<void> | void

const clearers = new Map<string, Clearer>()

/** Registers (or replaces, by `name`) a clearer. Safe to call twice, for example on hot reload. */
export function registerLocalDataClearer(name: string, clear: Clearer): void {
  clearers.set(name, clear)
}

/** Runs every clearer. One failing never stops the others; the failures are returned for the caller to log. */
export async function clearAllLocalData(userId: string): Promise<string[]> {
  const failed: string[] = []
  for (const [name, clear] of clearers) {
    try {
      await clear(userId)
    } catch {
      failed.push(name)
    }
  }
  return failed
}
