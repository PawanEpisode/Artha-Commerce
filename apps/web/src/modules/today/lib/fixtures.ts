/** Test builders for plans and tasks. Test support only: nothing in the app imports this file. */
import type { Plan, Task } from './types'

export const task = (id: string, state: Task['state'], extra: Partial<Task> = {}): Task => ({
  id,
  origin: 'provider',
  kind: 'mcq',
  slot: 'mcq',
  title: `Task ${id}`,
  reason: 'Due for revision',
  reason_code: 'custom',
  why: { modifiers: [], signals: {} },
  est_minutes: 10,
  progress: null,
  target: null,
  state,
  link: { path: '/app/recall', search: {} },
  subject_id: null,
  chapter_id: null,
  manual_action: null,
  is_must_do: false,
  version: 1,
  ...extra,
})

const PLANNED = ['suggested', 'accepted', 'done', 'skipped']

export const plan = (tasks: Task[], extra: Partial<Plan> = {}): Plan => ({
  version: 1,
  date: '2026-10-14',
  tz: 'Asia/Kolkata',
  server_time: '2026-10-14T03:00:00Z',
  state: 'ready',
  phase: 'steady',
  days_to_exam: 100,
  generation_no: 1,
  partial: false,
  failed_providers: [],
  budget_minutes: 60,
  budget_source: 'auto',
  planned_minutes: tasks.filter((t) => PLANNED.includes(t.state)).reduce((s, t) => s + t.est_minutes, 0),
  counts: {
    planned: tasks.filter((t) => PLANNED.includes(t.state)).length,
    done: tasks.filter((t) => t.state === 'done').length,
    open: tasks.filter((t) => t.state === 'suggested' || t.state === 'accepted').length,
    skipped: tasks.filter((t) => t.state === 'skipped').length,
    snoozed: tasks.filter((t) => t.state === 'snoozed').length,
  },
  starter_task_id: null,
  backlog: [],
  tiles: [],
  tasks,
  streak: 0,
  goal: { target_minutes: 120, done_seconds: 0, percent: 0 },
  celebrate: false,
  closing: null,
  tomorrow: null,
  ...extra,
})
