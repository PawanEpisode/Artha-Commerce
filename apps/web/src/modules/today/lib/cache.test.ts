import { beforeEach, describe, expect, it } from 'vitest'

import { clearCachedPlan, loadCachedPlan, resetPlanCache, saveCachedPlan } from './cache'
import { plan, task } from './fixtures'

beforeEach(() => resetPlanCache())

describe('plan cache', () => {
  it('returns what was saved for the same student, with the time of the save', async () => {
    const p = plan([task('a', 'suggested')])
    await saveCachedPlan('u1', p, 1234)
    const got = await loadCachedPlan('u1')
    expect(got?.savedAt).toBe(1234)
    expect(got?.plan.tasks[0].id).toBe('a')
  })
  it("never shows another student's plan", async () => {
    await saveCachedPlan('u1', plan([task('a', 'suggested')]))
    expect(await loadCachedPlan('u2')).toBeNull()
  })
  it('is gone after a clear (account deletion on this device)', async () => {
    await saveCachedPlan('u1', plan([]))
    await clearCachedPlan('u1')
    expect(await loadCachedPlan('u1')).toBeNull()
  })
  it('reads as nothing stored when nothing was saved', async () => {
    expect(await loadCachedPlan('nobody')).toBeNull()
  })
})
