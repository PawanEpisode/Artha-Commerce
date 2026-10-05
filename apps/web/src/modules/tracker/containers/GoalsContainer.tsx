import { Button, DurationField, Label, Plus, SelectField, Trash2 } from '@artha/design-system'
import { useEffect, useState } from 'react'

import { GoalRings } from '../components/GoalRings'
import { useSaveGoals } from '../hooks/useSessionActions'
import { useSubjectOptions } from '../hooks/useTagOptions'
import { useGoals } from '../hooks/useTrackerQueries'
import { type GoalErrors, type GoalsDraft, validateGoals } from '../lib/goalsForm'
import { GOAL_DAILY_MAX, GOAL_WEEKLY_MAX } from '../lib/limits'
import { notify } from '../lib/notify'
import { TrackerShell } from './TrackerShell'

let rowCounter = 0
const rowKey = () => `r${++rowCounter}`

function GoalsForm() {
  const goals = useGoals()
  const save = useSaveGoals()
  const subjects = useSubjectOptions()
  const [draft, setDraft] = useState<GoalsDraft>({ daily: null, weekly: null, subjects: [] })
  const [errors, setErrors] = useState<GoalErrors>({})

  const loaded = goals.data
  useEffect(() => {
    if (!loaded) return
    const find = (period: string, subject: boolean) =>
      loaded.goals.filter((g) => g.period === period && !!g.subject_id === subject)
    setDraft({
      daily: find('daily', false)[0]?.target_minutes ?? null,
      weekly: find('weekly', false)[0]?.target_minutes ?? null,
      subjects: find('weekly', true).map((g) => ({
        key: rowKey(),
        subject_id: g.subject_id as string,
        minutes: g.target_minutes,
      })),
    })
  }, [loaded])

  const nameOf = (id: string) => subjects.find((s) => s.id === id)?.name
  const patchRow = (key: string, patch: Partial<GoalsDraft['subjects'][number]>) =>
    setDraft((d) => ({ ...d, subjects: d.subjects.map((r) => (r.key === key ? { ...r, ...patch } : r)) }))

  const submit = () => {
    const { entries, errors: found } = validateGoals(draft)
    setErrors(found)
    if (Object.keys(found).length > 0) return
    save.mutate(entries, {
      onSuccess: () => notify.goalsSaved(),
      onError: (e) => notify.error(e, 'Could not save your goals.'),
    })
  }

  return (
    <>
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold">Goals</h1>
        <p className="text-muted-foreground">
          Set targets in hours and minutes. Leave a goal empty to remove it. Without a daily goal we use 2 hours.
        </p>
      </header>
      {loaded ? <GoalRings progress={loaded.progress} /> : null}
      <form
        className="space-y-6 rounded-2xl border border-border bg-card p-6"
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <div className="grid gap-6 sm:grid-cols-2">
          <DurationField
            label="Daily goal"
            valueMinutes={draft.daily}
            onChangeMinutes={(daily) => setDraft((d) => ({ ...d, daily }))}
            maxMinutes={GOAL_DAILY_MAX}
            error={errors.daily}
            hint="How long you want to study each day."
          />
          <DurationField
            label="Weekly goal"
            valueMinutes={draft.weekly}
            onChangeMinutes={(weekly) => setDraft((d) => ({ ...d, weekly }))}
            maxMinutes={GOAL_WEEKLY_MAX}
            error={errors.weekly}
            hint="Your total for the week."
          />
        </div>

        <fieldset className="space-y-3">
          <legend className="text-sm font-semibold">Weekly goals by subject</legend>
          {draft.subjects.length === 0 ? (
            <p className="rounded-xl border border-dashed border-border p-4 text-sm text-muted-foreground">
              {subjects.length === 0
                ? 'Set up My Coverage first, then you can give each subject its own weekly goal.'
                : 'No subject goals yet. Add one to aim for a weekly target in a single subject.'}
            </p>
          ) : (
            <ul className="space-y-3">
              {draft.subjects.map((row, index) => {
                const name = nameOf(row.subject_id)
                const taken = new Set(draft.subjects.filter((r) => r.key !== row.key).map((r) => r.subject_id))
                const selectId = `goal-subject-${row.key}`
                return (
                  <li key={row.key} className="space-y-3 rounded-xl border border-border bg-background p-4">
                    <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                      Subject goal {index + 1}
                    </p>
                    <div className="grid gap-2">
                      <Label htmlFor={selectId}>Subject</Label>
                      <SelectField
                        id={selectId}
                        value={row.subject_id}
                        onValueChange={(subject_id) => patchRow(row.key, { subject_id })}
                        options={[
                          { value: '', label: 'Choose a subject' },
                          ...subjects.map((o) => ({ value: o.id, label: o.name, disabled: taken.has(o.id) })),
                        ]}
                      />
                      {errors[`subject-${row.key}-subject`] ? (
                        <p role="alert" className="text-sm font-medium text-destructive">
                          {errors[`subject-${row.key}-subject`]}
                        </p>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap items-end justify-between gap-3">
                      <DurationField
                        label={name ? `Weekly goal for ${name}` : 'Weekly goal for this subject'}
                        valueMinutes={row.minutes}
                        onChangeMinutes={(minutes) => patchRow(row.key, { minutes })}
                        maxMinutes={GOAL_WEEKLY_MAX}
                        error={errors[`subject-${row.key}`]}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        aria-label={name ? `Remove ${name} goal` : `Remove subject goal ${index + 1}`}
                        onClick={() =>
                          setDraft((d) => ({ ...d, subjects: d.subjects.filter((r) => r.key !== row.key) }))
                        }
                      >
                        <Trash2 aria-hidden /> Remove
                      </Button>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
          <Button
            type="button"
            variant="secondary"
            disabled={subjects.length === 0 || draft.subjects.length >= subjects.length}
            onClick={() =>
              setDraft((d) => ({ ...d, subjects: [...d.subjects, { key: rowKey(), subject_id: '', minutes: null }] }))
            }
          >
            <Plus aria-hidden /> Add a subject goal
          </Button>
        </fieldset>

        <Button type="submit" variant="cta" loading={save.isPending}>
          Save goals
        </Button>
      </form>
    </>
  )
}

export function GoalsContainer() {
  return <TrackerShell>{() => <GoalsForm />}</TrackerShell>
}
