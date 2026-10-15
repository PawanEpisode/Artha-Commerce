/** View model of a plan: pure functions the components render from. No fetching, no clock. */
import type { EmptyPlan, OpenResult, Plan, Task, Tile } from './types'

export type ScreenState = 'not_enrolled' | 'post_exam' | 'nothing_due' | 'not_started' | 'in_progress' | 'all_done'

export function screenState(result: OpenResult): ScreenState {
  if (result.state !== 'ready') return (result as EmptyPlan).state
  const { planned, done, open } = result.counts
  if (result.tasks.length === 0 || planned === 0) return 'nothing_due'
  if (open === 0) return 'all_done'
  return done > 0 ? 'in_progress' : 'not_started'
}

export const OTHER_KEY = 'other'

export interface TileView {
  key: string
  name: string
  subjectId: string | null
  tasks: Task[]
  done: number
  total: number
}

const counts = (tasks: Task[]) => ({
  done: tasks.filter((t) => t.state === 'done').length,
  // snoozed and expired tasks are not part of the day's plan, so they are not in the paper's "x of y"
  total: tasks.filter((t) => t.state !== 'snoozed' && t.state !== 'expired').length,
})

/** One tile per paper in the server's order, then "Other" for tasks no paper owns (own tasks, general work). */
export function tileViews(plan: Plan): TileView[] {
  const byId = new Map(plan.tasks.map((t) => [t.id, t]))
  const claimed = new Set<string>()
  const views: TileView[] = plan.tiles.map((tile: Tile) => {
    const tasks = tile.tasks.map((id) => byId.get(id)).filter((t): t is Task => t !== undefined)
    tasks.forEach((t) => claimed.add(t.id))
    return { key: tile.subject_key || OTHER_KEY, name: tile.name, subjectId: tile.subject_id, tasks, ...counts(tasks) }
  })
  const rest = plan.tasks.filter((t) => !claimed.has(t.id))
  if (rest.length) {
    const existing = views.find((v) => v.key === OTHER_KEY)
    if (existing) {
      existing.tasks.push(...rest)
      Object.assign(existing, counts(existing.tasks))
    } else
      views.push({
        key: OTHER_KEY,
        name: rest.every((t) => t.origin === 'user') ? 'Yours' : 'Other',
        subjectId: null,
        tasks: rest,
        ...counts(rest),
      })
  }
  return views
}

/** The paper the `?paper` search names, or null for "all papers" (also for a key that no longer exists). */
export function selectedTile(views: TileView[], paper: string | undefined): TileView | null {
  return paper ? (views.find((v) => v.key === paper) ?? null) : null
}

export interface TaskGroups {
  open: Task[]
  done: Task[]
  parked: Task[]
}

/** Open work first in the plan's order, finished work after it, skipped and snoozed work last and quiet. */
export function groupTasks(tasks: Task[]): TaskGroups {
  const out: TaskGroups = { open: [], done: [], parked: [] }
  for (const t of tasks) {
    if (t.state === 'suggested' || t.state === 'accepted') out.open.push(t)
    else if (t.state === 'done') out.done.push(t)
    else if (t.state === 'skipped' || t.state === 'snoozed') out.parked.push(t)
  }
  out.open.sort((a, b) => Number(b.state === 'accepted') - Number(a.state === 'accepted')) // started work first (stable)
  return out
}

/** The "Start here" task, only while it is still open. */
export function starterTask(plan: Plan): Task | null {
  const t = plan.starter_task_id ? plan.tasks.find((x) => x.id === plan.starter_task_id) : undefined
  return t && (t.state === 'suggested' || t.state === 'accepted') ? t : null
}

/** "12 of 30" for a task with a target, else null. */
export function progressText(task: Task): string | null {
  const p = task.progress
  if (!p || !p.target) return null
  return `${Math.min(p.done, p.target)} of ${p.target}`
}

export const taskCountLabel = (done: number, total: number) =>
  `${done} of ${total} ${total === 1 ? 'task' : 'tasks'} done`

/** A planned day above this many minutes gets the "long day" note (PRD 7.3). Web only, so it is not in `limits.ts`. */
export const LONG_DAY_MINUTES = 180
