import { Alert, Button, Select, TextField, useToast } from '@artha/design-system'
import { useEffect, useState } from 'react'

import { GoalRings } from '../components/GoalRings'
import { useSaveGoals } from '../hooks/useSessionActions'
import { useSubjectOptions } from '../hooks/useTagOptions'
import { useGoals } from '../hooks/useTrackerQueries'
import { errorMessage } from '../lib/api'
import { GOAL_DAILY_MAX, GOAL_DAILY_MIN, GOAL_WEEKLY_MAX, GOAL_WEEKLY_MIN } from '../lib/limits'
import type { GoalEntry } from '../lib/types'
import { TrackerShell } from './TrackerShell'

interface Draft {
  daily: string
  weekly: string
  subjects: Array<{ subject_id: string; minutes: string }>
}

function GoalsForm() {
  const goals = useGoals()
  const save = useSaveGoals()
  const subjects = useSubjectOptions()
  const toast = useToast()
  const [draft, setDraft] = useState<Draft>({ daily: '', weekly: '', subjects: [] })
  const [errors, setErrors] = useState<Record<string, string>>({})

  const loaded = goals.data
  useEffect(() => {
    if (!loaded) return
    const find = (period: string, subject: boolean) =>
      loaded.goals.filter((g) => g.period === period && !!g.subject_id === subject)
    setDraft({
      daily: String(find('daily', false)[0]?.target_minutes ?? ''),
      weekly: String(find('weekly', false)[0]?.target_minutes ?? ''),
      subjects: find('weekly', true).map((g) => ({
        subject_id: g.subject_id as string,
        minutes: String(g.target_minutes),
      })),
    })
  }, [loaded])

  const submit = () => {
    const found: Record<string, string> = {}
    const entries: GoalEntry[] = []
    const add = (
      key: string,
      raw: string,
      period: 'daily' | 'weekly',
      min: number,
      max: number,
      subject_id: string | null,
    ) => {
      if (raw.trim() === '') return
      const n = Number(raw)
      if (!Number.isInteger(n) || n < min || n > max) found[key] = `Enter whole minutes from ${min} to ${max}.`
      else entries.push({ period, subject_id, target_minutes: n })
    }
    add('daily', draft.daily, 'daily', GOAL_DAILY_MIN, GOAL_DAILY_MAX, null)
    add('weekly', draft.weekly, 'weekly', GOAL_WEEKLY_MIN, GOAL_WEEKLY_MAX, null)
    draft.subjects.forEach((s, i) => {
      if (!s.subject_id) return
      add(`subject-${i}`, s.minutes, 'weekly', GOAL_WEEKLY_MIN, GOAL_WEEKLY_MAX, s.subject_id)
    })
    setErrors(found)
    if (Object.keys(found).length > 0) return
    save.mutate(entries, { onSuccess: () => toast.show({ message: 'Goals saved.' }) })
  }

  return (
    <>
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold">Goals</h1>
        <p className="text-muted-foreground">
          Goals are in minutes. Leave a goal empty to remove it. Without a daily goal we use 2 hours.
        </p>
      </header>
      {loaded ? <GoalRings progress={loaded.progress} /> : null}
      <form
        className="space-y-5 rounded-2xl border border-border bg-card p-6"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            label="Daily goal (minutes)"
            type="number"
            inputMode="numeric"
            value={draft.daily}
            onChange={(e) => setDraft({ ...draft, daily: e.target.value })}
            error={errors.daily}
          />
          <TextField
            label="Weekly goal (minutes)"
            type="number"
            inputMode="numeric"
            value={draft.weekly}
            onChange={(e) => setDraft({ ...draft, weekly: e.target.value })}
            error={errors.weekly}
          />
        </div>
        <fieldset className="space-y-3">
          <legend className="text-sm font-semibold">Weekly goals by subject</legend>
          {draft.subjects.map((s, i) => (
            <div key={i} className="grid items-start gap-3 sm:grid-cols-[1fr_10rem_auto]">
              <Select
                aria-label={`Subject for goal ${i + 1}`}
                value={s.subject_id}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    subjects: draft.subjects.map((x, j) => (j === i ? { ...x, subject_id: e.target.value } : x)),
                  })
                }
              >
                <option value="">Choose a subject</option>
                {subjects.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
              </Select>
              <TextField
                label="Minutes"
                className="[&>label]:sr-only"
                type="number"
                inputMode="numeric"
                value={s.minutes}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    subjects: draft.subjects.map((x, j) => (j === i ? { ...x, minutes: e.target.value } : x)),
                  })
                }
                error={errors[`subject-${i}`]}
              />
              <Button
                type="button"
                variant="ghost"
                onClick={() => setDraft({ ...draft, subjects: draft.subjects.filter((_, j) => j !== i) })}
              >
                Remove
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={subjects.length === 0}
            onClick={() => setDraft({ ...draft, subjects: [...draft.subjects, { subject_id: '', minutes: '' }] })}
          >
            Add a subject goal
          </Button>
          {subjects.length === 0 ? (
            <p className="text-sm text-muted-foreground">Set up My Coverage to choose subjects.</p>
          ) : null}
        </fieldset>
        {save.isError ? (
          <Alert variant="error">
            <span role="alert">{errorMessage(save.error)}</span>
          </Alert>
        ) : null}
        <Button type="submit" disabled={save.isPending}>
          Save goals
        </Button>
      </form>
    </>
  )
}

export function GoalsContainer() {
  return <TrackerShell>{() => <GoalsForm />}</TrackerShell>
}
