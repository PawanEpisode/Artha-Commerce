import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, type Mock, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  api: {} as Record<string, Mock<(...args: unknown[]) => unknown>>,
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), dismiss: vi.fn() },
}))
vi.mock('@artha/design-system', () => ({ toast: mocks.toast }))
vi.mock('../lib/api', () => ({
  newClientId: () => 'client-1',
  errorCode: (e: { code?: string }) => e?.code ?? null,
  errorDetails: (e: { details?: object }) => e?.details ?? {},
  errorMessage: (_e: unknown, fallback: string) => fallback,
  completeTask: (...a: unknown[]) => mocks.api.completeTask!(...a),
  skipTask: (...a: unknown[]) => mocks.api.skipTask!(...a),
  undoTask: (...a: unknown[]) => mocks.api.undoTask!(...a),
  swapTask: (...a: unknown[]) => mocks.api.swapTask!(...a),
  startTask: (...a: unknown[]) => mocks.api.startTask!(...a),
  snoozeTask: (...a: unknown[]) => mocks.api.snoozeTask!(...a),
  deleteTask: (...a: unknown[]) => mocks.api.deleteTask!(...a),
  addTask: (...a: unknown[]) => mocks.api.addTask!(...a),
  editTask: (...a: unknown[]) => mocks.api.editTask!(...a),
}))

import { plan, task } from '../lib/fixtures'
import { todayKeys } from '../lib/keys'
import type { OpenResult, Plan } from '../lib/types'
import { useTaskActions } from './useTaskActions'

const counts = (p: Plan) => p.counts
const response = (t: ReturnType<typeof task>, p: Plan) => ({ version: 1, server_time: '', task: t, counts: counts(p) })

function setup(initial: Plan) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  qc.setQueryData<OpenResult>(todayKeys.plan, initial)
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
  const hook = renderHook(() => useTaskActions(), { wrapper })
  const read = () => qc.getQueryData<OpenResult>(todayKeys.plan) as Plan
  return { hook, read, qc }
}

const fresh = () => plan([task('a', 'suggested'), task('b', 'suggested'), task('c', 'accepted')])

beforeEach(() => {
  vi.clearAllMocks()
  mocks.api = {
    completeTask: vi.fn(),
    skipTask: vi.fn(),
    undoTask: vi.fn(),
    swapTask: vi.fn(),
    startTask: vi.fn(),
    snoozeTask: vi.fn(),
    deleteTask: vi.fn(),
    addTask: vi.fn(),
    editTask: vi.fn(),
  }
})

describe('useTaskActions', () => {
  it('ticks at once, then merges the server answer and offers Undo', async () => {
    const { hook, read } = setup(fresh())
    let resolve!: (v: unknown) => void
    mocks.api.completeTask!.mockReturnValue(new Promise((r) => (resolve = r)))
    let pending!: Promise<unknown>
    act(() => {
      pending = hook.result.current.tick(read().tasks[0]!) as Promise<unknown>
    })
    await waitFor(() => expect(read().tasks[0]?.state).toBe('done')) // optimistic, before the server answers
    expect(read().counts.done).toBe(1)
    const server = plan([task('a', 'done', { version: 2 }), task('b', 'suggested'), task('c', 'accepted')])
    resolve(response(server.tasks[0]!, server))
    await act(async () => void (await pending))
    expect(read().tasks[0]?.version).toBe(2)
    expect(mocks.toast.success).toHaveBeenCalledWith(
      'Marked done',
      expect.objectContaining({ id: 'undo-a', duration: 10_000 }),
    )
    expect(hook.result.current.canUndo('a')).toMatchObject({ from: 'done', back: 'suggested' })
  })

  it('rolls back only the failed task and says so', async () => {
    const { hook, read } = setup(fresh())
    mocks.api.completeTask!.mockRejectedValue({ code: 'internal' })
    mocks.api.skipTask!.mockResolvedValue(response(task('b', 'skipped'), plan([])))
    await act(async () => {
      await Promise.all([hook.result.current.tick(read().tasks[0]!), hook.result.current.skip(read().tasks[1]!)])
    })
    expect(read().tasks.map((t) => t.state)).toEqual(['suggested', 'skipped', 'accepted'])
    expect(mocks.toast.error).toHaveBeenCalled()
  })

  it('runs requests for one task in order', async () => {
    const { hook, read } = setup(fresh())
    const order: string[] = []
    mocks.api.completeTask!.mockImplementation(async () => {
      order.push('complete:start')
      await new Promise((r) => setTimeout(r, 20))
      order.push('complete:end')
      return response(task('a', 'done'), plan([]))
    })
    mocks.api.undoTask!.mockImplementation(async () => {
      order.push('undo')
      return response(task('a', 'suggested'), plan([]))
    })
    await act(async () => {
      const t = read().tasks[0]!
      const first = hook.result.current.tick(t)
      const second = hook.result.current.undo(task('a', 'done'), 'done', 'suggested')
      await Promise.all([first, second])
    })
    expect(order).toEqual(['complete:start', 'complete:end', 'undo'])
  })

  it('a conflict shows the server task instead of the guess', async () => {
    const { hook, read } = setup(fresh())
    mocks.api.skipTask!.mockRejectedValue({ code: 'state_conflict', details: { task: task('a', 'done') } })
    await act(async () => void (await hook.result.current.skip(read().tasks[0]!)))
    expect(read().tasks[0]?.state).toBe('done')
    expect(mocks.toast.info).toHaveBeenCalled()
  })

  it('the third skip says the work is suppressed instead of offering Undo', async () => {
    const { hook, read } = setup(fresh())
    mocks.api.skipTask!.mockResolvedValue({ ...response(task('a', 'skipped'), plan([])), suppressed_days: 14 })
    await act(async () => void (await hook.result.current.skip(read().tasks[0]!)))
    expect(mocks.toast.info).toHaveBeenCalledWith(expect.stringContaining('14 days'))
    expect(mocks.toast.success).not.toHaveBeenCalled()
  })

  it('swap puts the new task in the old one\'s place; "no alternative" only informs', async () => {
    const { hook, read } = setup(fresh())
    mocks.api.swapTask!.mockResolvedValueOnce({
      version: 1,
      server_time: '',
      old: task('a', 'skipped'),
      new: task('n', 'suggested'),
      counts: { planned: 4, done: 0, open: 3, skipped: 1, snoozed: 0 },
    })
    await act(async () => void (await hook.result.current.swap(read().tasks[0]!)))
    expect(read().tasks.map((t) => t.id)).toEqual(['a', 'n', 'b', 'c'])
    mocks.api.swapTask!.mockRejectedValueOnce({ code: 'no_alternative' })
    await act(async () => void (await hook.result.current.swap(read().tasks[1]!)))
    expect(mocks.toast.info).toHaveBeenCalledWith('Nothing else to suggest for this paper')
    expect(read().tasks.map((t) => t.id)).toEqual(['a', 'n', 'b', 'c'])
  })

  it('start marks the task in progress and answers the link', async () => {
    const { hook, read } = setup(fresh())
    mocks.api.startTask!.mockResolvedValue({
      ...response(task('a', 'accepted'), plan([])),
      link: { path: '/app/x', search: {} },
    })
    let link: unknown
    await act(async () => void (link = await hook.result.current.start(read().tasks[0]!)))
    expect(link).toEqual({ path: '/app/x', search: {} })
    expect(read().tasks[0]?.state).toBe('accepted')
  })

  it("start still opens the task's own link when the request fails", async () => {
    const { hook, read } = setup(fresh())
    mocks.api.startTask!.mockRejectedValue({ code: 'internal' })
    let link: unknown
    await act(async () => void (link = await hook.result.current.start(read().tasks[0]!)))
    expect(link).toEqual({ path: '/app/recall', search: {} })
  })

  it('deleting an own task removes it and Undo brings it back', async () => {
    const own = task('o', 'suggested', { origin: 'user' })
    const { hook, read } = setup(plan([task('a', 'suggested'), own]))
    mocks.api.deleteTask!.mockResolvedValue({
      ...response(own, plan([])),
      counts: { planned: 1, done: 0, open: 1, skipped: 0, snoozed: 0 },
      undo_until: 'x',
    })
    await act(async () => void (await hook.result.current.remove(own)))
    expect(read().tasks.map((t) => t.id)).toEqual(['a'])
    mocks.api.undoTask!.mockResolvedValue({
      ...response(own, plan([])),
      counts: { planned: 2, done: 0, open: 2, skipped: 0, snoozed: 0 },
    })
    const options = mocks.toast.success.mock.calls.at(-1)![1] as { action: { onClick: () => void } }
    await act(async () => {
      options.action.onClick()
      await new Promise((r) => setTimeout(r, 10))
    })
    expect(read().tasks.map((t) => t.id)).toEqual(['a', 'o'])
  })

  it('adding an own task for another day leaves today alone and errors reach the caller', async () => {
    const { hook, read } = setup(fresh())
    mocks.api.addTask!.mockResolvedValue(response(task('n', 'suggested', { origin: 'user' }), fresh()))
    await act(
      async () =>
        void (await hook.result.current.add({ client_id: 'c', title: 't', est_minutes: 5, date: '2026-10-20' })),
    )
    expect(read().tasks).toHaveLength(3)
    await act(async () => void (await hook.result.current.add({ client_id: 'c', title: 't', est_minutes: 5 })))
    expect(read().tasks).toHaveLength(4)
    mocks.api.addTask!.mockRejectedValue({ code: 'quota_exceeded' })
    await expect(hook.result.current.add({ client_id: 'c2', title: 't', est_minutes: 5 })).rejects.toBeTruthy()
  })
})
