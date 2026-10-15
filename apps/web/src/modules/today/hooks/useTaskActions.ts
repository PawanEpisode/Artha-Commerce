import { toast } from '@artha/design-system'
import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useRef, useState } from 'react'

import { pendingCount } from '~/lib/offline-queue'

import { minutesBucket, trackToday } from '../lib/analytics'
import * as api from '../lib/api'
import { todayKeys } from '../lib/keys'
import { UNDO_WINDOW_SECONDS } from '../lib/limits'
import {
  addOwnTask,
  applyAction,
  applySwap,
  findTask,
  localOwnTask,
  mergeTask,
  removeTask,
  restoreTask,
} from '../lib/optimistic'
import type {
  AddTaskBody,
  EditFields,
  OpenResult,
  Plan,
  SkipReason,
  SnoozeUntil,
  Task,
  TaskLink,
  TaskResponse,
  TaskState,
  UndoFrom,
} from '../lib/types'

interface UndoEntry {
  from: UndoFrom
  /** The state to show again when the undo is applied. */
  back: TaskState
  until: number
}

const UNDO_TOAST_MS = 10_000
const NO_COUNTS = { planned: 0, done: 0, open: 0, skipped: 0, snoozed: 0 }
const SNOOZE_WORDS: Record<string, string> = { tomorrow: 'tomorrow', in_3_days: 'in 3 days', next_week: 'next week' }

/**
 * Every task action of the Today screen. Each one changes the cached plan at once, sends the request, then merges the server's
 * answer. Requests for one task run in order (a tick and its undo can never overtake each other); different tasks run side by
 * side. A failure puts back only the task it belongs to. The server stays the authority (409 and 422 show its current state).
 */
export function useTaskActions() {
  const qc = useQueryClient()
  const queues = useRef(new Map<string, Promise<unknown>>())
  const [undoable, setUndoable] = useState<Record<string, UndoEntry>>({})
  const [busy, setBusy] = useState<ReadonlySet<string>>(new Set())

  const plan = useCallback((): Plan | null => {
    const data = qc.getQueryData<OpenResult>(todayKeys.plan)
    return data && data.state === 'ready' ? data : null
  }, [qc])

  const patch = useCallback(
    (fn: (p: Plan) => Plan) =>
      qc.setQueryData<OpenResult>(todayKeys.plan, (old) => (old && old.state === 'ready' ? fn(old) : old)),
    [qc],
  )

  const refetch = useCallback(() => void qc.invalidateQueries({ queryKey: todayKeys.plan }), [qc])

  const enqueue = useCallback(<T>(taskId: string, job: () => Promise<T>): Promise<T | undefined> => {
    const previous = queues.current.get(taskId) ?? Promise.resolve()
    const next = previous.catch(() => undefined).then(job)
    queues.current.set(taskId, next)
    setBusy((s) => new Set(s).add(taskId))
    const done = () => {
      if (queues.current.get(taskId) === next) {
        queues.current.delete(taskId)
        setBusy((s) => {
          const n = new Set(s)
          n.delete(taskId)
          return n
        })
      }
    }
    next.then(done, done)
    return next.catch(() => undefined) as Promise<T | undefined>
  }, [])

  /** A write was stored for later: the screen keeps the change, says so once, and counts what waits. */
  const queued = useCallback(() => {
    toast.info('Saved on this device. It will sync when you are back online.', { id: 'today-queued' })
    void qc.invalidateQueries({ queryKey: todayKeys.offline })
    void pendingCount(api.TODAY_SCOPE).then((count) => trackToday('today_offline_queued', { count, age_bucket: '<1h' }))
  }, [qc])

  const fail = useCallback(
    (error: unknown, snapshot?: Task) => {
      if (api.isNetworkError(error)) {
        if (snapshot) patch((p) => restoreTask(p, snapshot))
        return void toast.error('You are offline. This one needs a connection.')
      }
      const code = api.errorCode(error)
      const details = api.errorDetails(error)
      if (code === 'state_conflict' && details.task) {
        patch((p) => mergeTask(p, details.task as Task))
        toast.info('This task changed on another device. Showing the latest.')
        refetch()
        return
      }
      if (snapshot) patch((p) => restoreTask(p, snapshot))
      if (code === 'no_alternative') return void toast.info('Nothing else to suggest for this paper')
      if (code === 'undo_expired') {
        refetch()
        return void toast.info('It is too late to undo that.')
      }
      if (code === 'invalid_transition' || code === 'task_not_found' || code === 'plan_changed') {
        refetch()
        return void toast.info('That task has changed. Showing the latest.')
      }
      toast.error(api.errorMessage(error, 'That did not save. Please try again.'))
    },
    [patch, refetch],
  )

  const remember = (id: string, entry: Omit<UndoEntry, 'until'>) =>
    setUndoable((u) => ({ ...u, [id]: { ...entry, until: Date.now() + UNDO_WINDOW_SECONDS * 1000 } }))
  const forget = (id: string) =>
    setUndoable((u) => {
      const { [id]: _gone, ...rest } = u
      return rest
    })

  /** One optimistic action: change the cache, queue the request, merge the answer. */
  const act = useCallback(
    async (
      task: Task,
      local: (p: Plan) => Plan | null,
      call: () => Promise<TaskResponse>,
      ok?: (r: TaskResponse) => void,
    ) => {
      const current = plan()
      const snapshot = current ? findTask(current, task.id) : undefined
      const optimistic = current ? local(current) : null
      if (!current || !optimistic) return
      await qc.cancelQueries({ queryKey: todayKeys.plan })
      patch(() => optimistic)
      return enqueue(task.id, async () => {
        try {
          const res = await call()
          patch((p) => mergeTask(p, res.task, res.counts))
          ok?.(res)
          return res
        } catch (error) {
          if (error instanceof api.QueuedOffline) queued()
          else fail(error, snapshot)
          return undefined
        }
      })
    },
    [enqueue, fail, patch, plan, qc, queued],
  )

  const undo = useCallback(
    (task: Task, from: UndoFrom, back: TaskState, via: 'toast' | 'menu' = 'menu') => {
      trackToday('today_task_undone', { from_state: from, via })
      return act(
        task,
        (p) => applyAction(p, task.id, 'undo', back),
        () => api.undoTask(task.id, api.newClientId(), from),
        () => {
          forget(task.id)
          toast.dismiss(`undo-${task.id}`)
        },
      )
    },
    [act],
  )

  const undoToast = useCallback(
    (task: Task, from: UndoFrom, back: TaskState, title: string) => {
      remember(task.id, { from, back })
      toast.success(title, {
        id: `undo-${task.id}`,
        duration: UNDO_TOAST_MS,
        action: { label: 'Undo', onClick: () => void undo(task, from, back, 'toast') },
      })
    },
    [undo],
  )

  const tick = useCallback(
    (task: Task, runManualAction = false) =>
      act(
        task,
        (p) => applyAction(p, task.id, 'complete_manual'),
        () => api.completeTask(task.id, api.newClientId(), runManualAction),
        () => undoToast(task, 'done', task.state === 'accepted' ? 'accepted' : 'suggested', 'Marked done'),
      ),
    [act, undoToast],
  )

  const skip = useCallback(
    (task: Task, reason?: SkipReason | null) =>
      act(
        task,
        (p) => applyAction(p, task.id, 'skip'),
        () => api.skipTask(task.id, api.newClientId(), reason),
        (res) => {
          if (res.suppressed_days) {
            toast.info(`Skipped. We will not suggest this for ${res.suppressed_days} days.`)
            return
          }
          undoToast(task, 'skipped', 'suggested', 'Skipped')
        },
      ),
    [act, undoToast],
  )

  const snooze = useCallback(
    (task: Task, until: SnoozeUntil) =>
      act(
        task,
        (p) => applyAction(p, task.id, 'snooze'),
        () => api.snoozeTask(task.id, api.newClientId(), until),
        () => toast.success(`Snoozed until ${SNOOZE_WORDS[until] ?? until}`),
      ),
    [act],
  )

  /** Marks the task started and answers the link to open (the task's own link when the request fails: studying comes first). */
  const start = useCallback(
    async (task: Task): Promise<TaskLink | null> => {
      const fallback = task.link
      if (task.state === 'accepted' || !plan()) return fallback
      const current = plan()
      trackToday('today_task_started', {
        kind: task.kind,
        provider: task.origin,
        position: current ? current.tasks.findIndex((t) => t.id === task.id) : -1,
        slot: task.slot,
        was_starter: current?.starter_task_id === task.id,
      })
      const res = await act(
        task,
        (p) => applyAction(p, task.id, 'start'),
        () => api.startTask(task.id, api.newClientId()),
      )
      return (res as TaskResponse | undefined)?.link ?? fallback
    },
    [act, plan],
  )

  const swap = useCallback(
    (task: Task) => {
      const current = plan()
      if (!current) return Promise.resolve()
      return enqueue(task.id, async () => {
        try {
          const res = await api.swapTask(task.id, api.newClientId())
          patch((p) => applySwap(p, res.old, res.new, res.counts))
          toast.success('Swapped for another task')
          return res.new.id
        } catch (error) {
          fail(error)
        }
      })
    },
    [enqueue, fail, patch, plan],
  )

  const remove = useCallback(
    (task: Task) => {
      const current = plan()
      if (!current) return Promise.resolve()
      const snapshot = findTask(current, task.id)
      patch((p) => removeTask(p, task.id))
      return enqueue(task.id, async () => {
        try {
          const res = await api.deleteTask(task.id, api.newClientId())
          patch((p) => removeTask(p, task.id, res.counts))
          toast.success('Task deleted', {
            id: `undo-${task.id}`,
            duration: UNDO_TOAST_MS,
            action: {
              label: 'Undo',
              onClick: () =>
                void enqueue(task.id, async () => {
                  try {
                    const back = await api.undoTask(task.id, api.newClientId(), 'deleted')
                    patch((p) => addOwnTask(p, back.task, back.counts))
                  } catch (error) {
                    fail(error)
                  }
                }),
            },
          })
        } catch (error) {
          if (error instanceof api.QueuedOffline) return void queued() // the row stays gone; the delete replays later
          if (snapshot) patch((p) => addOwnTask(p, snapshot))
          fail(error)
        }
      })
    },
    [enqueue, fail, patch, plan, queued],
  )

  /** Not optimistic (the server makes the id). Throws, so the sheet can show the field errors or the quota message. */
  const add = useCallback(
    async (body: AddTaskBody) => {
      try {
        const res = await api.addTask(body)
        patch((p) => (body.date && body.date !== p.date ? p : addOwnTask(p, res.task, res.counts)))
        trackToday('today_task_added', {
          has_subject: Boolean(body.subject_id),
          est_minutes_bucket: minutesBucket(body.est_minutes),
          offline: false,
        })
        return res
      } catch (error) {
        if (!(error instanceof api.QueuedOffline)) throw error
        // Offline: the task shows at once, marked as waiting, and the server makes the real one when the queue replays.
        const local = localOwnTask(body)
        patch((p) => (body.date && body.date !== p.date ? p : addOwnTask(p, local)))
        queued()
        trackToday('today_task_added', {
          has_subject: Boolean(body.subject_id),
          est_minutes_bucket: minutesBucket(body.est_minutes),
          offline: true,
        })
        return { version: 1, server_time: new Date().toISOString(), task: local, counts: plan()?.counts ?? NO_COUNTS }
      }
    },
    [patch, plan, queued],
  )

  const edit = useCallback(
    async (task: Task, fields: EditFields) => {
      const res = await api.editTask(task.id, { ...fields, version: task.version })
      patch((p) => mergeTask(p, res.task, res.counts))
      return res
    },
    [patch],
  )

  const canUndo = useCallback(
    (id: string): UndoEntry | null => {
      const entry = undoable[id]
      return entry && entry.until > Date.now() ? entry : null
    },
    [undoable],
  )

  return { tick, skip, snooze, swap, start, remove, add, edit, undo, canUndo, busy }
}

export type TaskActions = ReturnType<typeof useTaskActions>
