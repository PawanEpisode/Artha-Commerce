/**
 * Optimistic updates for the plan cache. Pure: each function takes a plan and returns a new one, so the hooks stay thin and
 * the rules can be tested. The server stays the authority: every answer is merged back with `mergeTask`, and a failed action
 * restores only its own task (`restoreTask`), so a slow request for one task never undoes a quick tick on another.
 */
import { transition } from './transitions'
import type { ActionName, Counts, Plan, Task, TaskState } from './types'

const PLANNED: readonly TaskState[] = ['suggested', 'accepted', 'done', 'skipped']
const OPEN: readonly TaskState[] = ['suggested', 'accepted']

/** The plan's counters from its tasks (the same rule as the API's `recount`: expired tasks are not in the day). */
export function recount(tasks: readonly Task[]): Counts {
  const live = tasks.filter((t) => t.state !== 'expired')
  return {
    planned: live.filter((t) => PLANNED.includes(t.state)).length,
    done: live.filter((t) => t.state === 'done').length,
    open: live.filter((t) => OPEN.includes(t.state)).length,
    skipped: live.filter((t) => t.state === 'skipped').length,
    snoozed: live.filter((t) => t.state === 'snoozed').length,
  }
}

const withTasks = (plan: Plan, tasks: Task[], counts?: Counts): Plan => ({
  ...plan,
  tasks,
  counts: counts ?? recount(tasks),
  planned_minutes: tasks.filter((t) => PLANNED.includes(t.state)).reduce((sum, t) => sum + t.est_minutes, 0),
})

export const findTask = (plan: Plan, id: string): Task | undefined => plan.tasks.find((t) => t.id === id)

/** Moves a task along the shared state machine. Returns null when the move is not allowed from where the task is. */
export function applyAction(plan: Plan, id: string, action: ActionName, to?: TaskState): Plan | null {
  const current = findTask(plan, id)
  if (!current) return null
  let next: TaskState
  if (to) next = to
  else {
    const result = transition(current.state, action, { origin: current.origin })
    if ('error' in result) return null
    next = result.to
  }
  if (next === current.state) return plan
  return withTasks(
    plan,
    plan.tasks.map((t) => (t.id === id ? { ...t, state: next } : t)),
  )
}

/** The server's answer for one task (and, when given, its counters) replaces the local copy. */
export function mergeTask(plan: Plan, task: Task, counts?: Counts): Plan {
  if (!findTask(plan, task.id)) return plan
  return withTasks(
    plan,
    plan.tasks.map((t) => (t.id === task.id ? task : t)),
    counts,
  )
}

/** Puts one task back to a snapshot (after a failed action) without touching any other task. */
export function restoreTask(plan: Plan, snapshot: Task): Plan {
  return findTask(plan, snapshot.id) ? mergeTask(plan, snapshot) : plan
}

/** A swap: the old task is skipped and the new one takes its place in the plan order and in the same paper tile. */
export function applySwap(plan: Plan, oldTask: Task, newTask: Task, counts?: Counts): Plan {
  const index = plan.tasks.findIndex((t) => t.id === oldTask.id)
  if (index < 0) return plan
  const tasks = [...plan.tasks]
  tasks[index] = oldTask
  tasks.splice(index + 1, 0, newTask)
  const tiles = plan.tiles.map((tile) =>
    tile.tasks.includes(oldTask.id)
      ? { ...tile, tasks: tile.tasks.flatMap((id) => (id === oldTask.id ? [id, newTask.id] : [id])) }
      : tile,
  )
  return { ...withTasks(plan, tasks, counts), tiles }
}

/** Id prefix of an own task made offline: it exists only on this device until the queue replays it. */
export const LOCAL_PREFIX = 'local-'
export const isLocalTask = (task: Pick<Task, 'id'>) => task.id.startsWith(LOCAL_PREFIX)

/** The row an offline "Add your own task" shows until the server makes the real one. It cannot be ticked or edited yet. */
export function localOwnTask(body: { client_id: string; title: string; est_minutes: number }): Task {
  return {
    id: `${LOCAL_PREFIX}${body.client_id}`,
    origin: 'user',
    kind: 'own',
    slot: 'own',
    title: body.title,
    reason: '',
    reason_code: 'custom',
    why: { modifiers: [], signals: {} },
    est_minutes: body.est_minutes,
    progress: null,
    target: null,
    state: 'suggested',
    link: null,
    subject_id: null,
    chapter_id: null,
    manual_action: null,
    is_must_do: false,
    is_bonus: false,
    stuck: false,
    version: 1,
  }
}

/** An own task the server just created joins the plan (and the "Yours" tile is built from unclaimed tasks, so no tile edit). */
export function addOwnTask(plan: Plan, task: Task, counts?: Counts): Plan {
  if (findTask(plan, task.id)) return mergeTask(plan, task, counts)
  return withTasks(plan, [...plan.tasks, task], counts)
}

export function removeTask(plan: Plan, id: string, counts?: Counts): Plan {
  return withTasks(
    plan,
    plan.tasks.filter((t) => t.id !== id),
    counts,
  )
}

/** Minutes still open ("about 35 min left"). */
export const minutesLeft = (plan: Plan): number =>
  plan.tasks.filter((t) => OPEN.includes(t.state)).reduce((sum, t) => sum + t.est_minutes, 0)

/** The open task after `id` in the list as shown (or the one before it, or null): where focus goes after an action. */
export function nextOpenTaskId(shown: readonly Task[], id: string): string | null {
  const open = shown.filter((t) => OPEN.includes(t.state) || t.id === id)
  const index = open.findIndex((t) => t.id === id)
  if (index < 0) return null
  return open[index + 1]?.id ?? open[index - 1]?.id ?? null
}
