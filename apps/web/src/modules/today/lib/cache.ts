/**
 * The last plan this device saw, kept in IndexedDB (memory when storage is unavailable) so a returning student sees it at once and
 * an offline one still has a list (FR-F13-39, FR-F13-41). One entry per student; a plan of another account is never shown.
 */
import { createKvDatabase } from '~/lib/kv-store'
import { registerLocalDataClearer } from '~/lib/local-data'

import type { Plan } from './types'

export interface CachedPlan {
  userId: string
  savedAt: number
  plan: Plan
}

const db = createKvDatabase('artha-today', 1, ['plans'])
const store = db.store<CachedPlan>('plans')

export async function saveCachedPlan(userId: string, plan: Plan, now = Date.now()): Promise<void> {
  try {
    await store.put(userId, { userId, savedAt: now, plan })
  } catch {
    /* a cache that cannot be written is only a missing cache */
  }
}

export async function loadCachedPlan(userId: string): Promise<CachedPlan | null> {
  try {
    const entry = await store.get(userId)
    return entry && entry.userId === userId && entry.plan?.state === 'ready' ? entry : null
  } catch {
    return null
  }
}

export const clearCachedPlan = (userId: string) => store.remove(userId)

/** Test hook. */
export const resetPlanCache = () => db.reset()

registerLocalDataClearer('today-plan-cache', clearCachedPlan)
