import { describe, expect, it } from 'vitest'

import { plan, task } from './fixtures'
import {
  addOwnTask,
  applyAction,
  applySwap,
  mergeTask,
  minutesLeft,
  nextOpenTaskId,
  recount,
  removeTask,
  restoreTask,
} from './optimistic'

const base = () => plan([task('a', 'suggested'), task('b', 'accepted'), task('c', 'done'), task('d', 'snoozed')])

describe('optimistic plan updates', () => {
  it('recounts like the API (snoozed and expired are outside the day)', () => {
    expect(recount(base().tasks)).toEqual({ planned: 3, done: 1, open: 2, skipped: 0, snoozed: 1 })
    expect(recount([task('x', 'expired')]).planned).toBe(0)
  })

  it('ticks, skips and snoozes along the shared state machine and recounts', () => {
    const ticked = applyAction(base(), 'a', 'complete_manual')!
    expect(ticked.tasks[0]?.state).toBe('done')
    expect(ticked.counts).toMatchObject({ done: 2, open: 1 })
    const skipped = applyAction(base(), 'b', 'skip')!
    expect(skipped.counts).toMatchObject({ skipped: 1, open: 1, planned: 3 })
    const snoozed = applyAction(base(), 'a', 'snooze')!
    expect(snoozed.counts).toMatchObject({ snoozed: 2, planned: 2 })
  })

  it('refuses moves the table forbids and unknown tasks', () => {
    expect(applyAction(base(), 'c', 'skip')).toBeNull() // a stale skip cannot reopen a done task
    expect(applyAction(base(), 'd', 'complete_manual')).toBeNull()
    expect(applyAction(base(), 'nope', 'skip')).toBeNull()
  })

  it('undo returns to the state the caller names', () => {
    const undone = applyAction(base(), 'c', 'undo', 'accepted')!
    expect(undone.tasks[2]?.state).toBe('accepted')
    expect(undone.counts.open).toBe(3)
  })

  it('merges a server task and its counters, and restores one task without touching the others', () => {
    const p = applyAction(applyAction(base(), 'a', 'complete_manual')!, 'b', 'skip')!
    const back = restoreTask(p, task('a', 'suggested'))
    expect(back.tasks.map((t) => t.state)).toEqual(['suggested', 'skipped', 'done', 'snoozed'])
    const merged = mergeTask(base(), task('a', 'done', { version: 5 }), {
      planned: 3,
      done: 2,
      open: 1,
      skipped: 0,
      snoozed: 1,
    })
    expect(merged.tasks[0]?.version).toBe(5)
    expect(merged.counts.done).toBe(2)
    expect(mergeTask(base(), task('zzz', 'done')).tasks).toHaveLength(4)
  })

  it('a swap skips the old task and puts the new one next to it, in the same tile', () => {
    const p = { ...base(), tiles: [{ subject_id: 's', subject_key: 'fr', name: 'FR', tasks: ['a', 'b'] }] }
    const swapped = applySwap(p, task('a', 'skipped'), task('n', 'suggested'))
    expect(swapped.tasks.map((t) => t.id)).toEqual(['a', 'n', 'b', 'c', 'd'])
    expect(swapped.tiles[0]?.tasks).toEqual(['a', 'n', 'b'])
    expect(swapped.counts).toMatchObject({ skipped: 1, open: 2 })
  })

  it('adds and removes own tasks', () => {
    const added = addOwnTask(base(), task('own', 'suggested', { origin: 'user' }))
    expect(added.counts.open).toBe(3)
    expect(addOwnTask(added, task('own', 'suggested', { origin: 'user' })).tasks).toHaveLength(5)
    expect(removeTask(added, 'own').tasks).toHaveLength(4)
  })

  it('sums the minutes still open', () => {
    expect(minutesLeft(base())).toBe(20)
  })

  it('finds where focus goes after an action', () => {
    const open = [task('a', 'suggested'), task('b', 'suggested'), task('c', 'suggested')]
    expect(nextOpenTaskId(open, 'a')).toBe('b')
    expect(nextOpenTaskId(open, 'c')).toBe('b')
    expect(nextOpenTaskId([task('a', 'suggested')], 'a')).toBeNull()
    expect(nextOpenTaskId(open, 'zzz')).toBeNull()
  })
})
