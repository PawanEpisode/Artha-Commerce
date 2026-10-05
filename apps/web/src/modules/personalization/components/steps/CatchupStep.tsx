import { Alert, Button, Skeleton } from '@artha/design-system'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { CatchupResult, CatchupStep as CatchupPicker, useCatchupSubjects } from '~/modules/coverage'

import { useSaveStep, useSkipStep } from '../../hooks/useOnboarding'
import { describeStepError } from '../../lib/stepErrors'
import type { StepProps } from './types'

/** Step 5 (optional): tick chapters already finished. The result card is the first "aha": a real starting point. */
export function CatchupStep({ onDone }: StepProps) {
  const qc = useQueryClient()
  const data = useCatchupSubjects()
  const save = useSaveStep('catchup')
  const skip = useSkipStep('catchup')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [alsoRevised, setAlsoRevised] = useState(false)
  const [applied, setApplied] = useState(false)
  const failure = save.error ? describeStepError(save.error) : skip.error ? describeStepError(skip.error) : null

  const toggle = (ids: string[], on: boolean) =>
    setSelected((prev) => {
      const next = new Set(prev)
      for (const id of ids) {
        if (on) next.add(id)
        else next.delete(id)
      }
      return next
    })

  function apply() {
    save.mutate(
      { chapter_ids: [...selected], also_revised: alsoRevised },
      {
        onSuccess: () => {
          // The percentages changed: refresh coverage so the result below reads the new numbers.
          void qc.invalidateQueries({ queryKey: ['coverage'] }).then(() => setApplied(true))
        },
      },
    )
  }

  if (data.loading) return <Skeleton className="h-72 w-full" aria-busy />
  if (data.failed || !data.overview) {
    return (
      <Alert variant="error">
        <div className="space-y-2">
          <p>We could not load your chapters. You can do this later from your syllabus map.</p>
          <Button size="sm" variant="outline" onClick={() => skip.mutate(undefined, { onSuccess: onDone })}>
            Skip for now
          </Button>
        </div>
      </Alert>
    )
  }

  if (applied) {
    const lowest = [...data.overview.subjects]
      .filter((s) => s.chapters_total > 0)
      .sort((a, b) => a.pct_simple - b.pct_simple)[0]
    const chapters = data.subjects.find((s) => s.subject.id === lowest?.id)?.chapters ?? []
    return (
      <div className="space-y-6">
        <CatchupResult
          levelName={`${data.overview.enrollment.course.name} ${data.overview.enrollment.level.name}`}
          percent={data.overview.level.pct_simple}
          startWith={
            lowest ? { name: lowest.name, notStarted: chapters.filter((c) => c.status === 'not_started').length } : null
          }
        />
        <Button size="lg" onClick={onDone}>
          Continue
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <CatchupPicker
        subjects={data.subjects}
        selected={selected}
        alsoRevised={alsoRevised}
        pending={save.isPending}
        error={failure?.message}
        note={
          data.hiddenElectives
            ? 'Elective papers you have not chosen are not listed. You can choose them later from your syllabus map.'
            : undefined
        }
        onToggleChapter={(id, on) => toggle([id], on)}
        onToggleSubject={toggle}
        onAlsoRevised={setAlsoRevised}
        onApply={apply}
        onSkip={() => skip.mutate(undefined, { onSuccess: onDone })}
      />
    </div>
  )
}
