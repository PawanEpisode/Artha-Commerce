import {
  Alert,
  Button,
  Label,
  LoaderCircle,
  RadioCardItem,
  RadioGroup,
  SelectField,
  TextField,
} from '@artha/design-system'
import type { FormEvent } from 'react'

import type { CourseSummary, ElectiveSlotInfo, ExamTerm } from '~/modules/syllabus'

import { ElectiveChoice } from './ElectiveChoice'

interface CourseLevelProps {
  courses: CourseSummary[]
  course: string
  level: string
  /** Name of the scheme that will be used, or null when the level is not curated yet. */
  schemeName: string | null
  schemeLoading: boolean
  onCourse: (code: string) => void
  onLevel: (code: string) => void
  onNext: () => void
}

/** Step 1: course and level. The scheme is chosen automatically (the current published one). */
export function CourseLevelStep({
  courses,
  course,
  level,
  schemeName,
  schemeLoading,
  onCourse,
  onLevel,
  onNext,
}: CourseLevelProps) {
  const selected = courses.find((c) => c.code === course)
  return (
    <div className="space-y-6">
      <fieldset className="space-y-3">
        <legend className="mb-2 font-display text-lg font-bold">Which course are you preparing for?</legend>
        <RadioGroup value={course} onValueChange={onCourse} className="sm:grid-cols-3">
          {courses.map((c) => (
            <RadioCardItem key={c.code} value={c.code}>
              <span className="block font-semibold">{c.name}</span>
              <span className="text-sm text-muted-foreground">{c.institute_name}</span>
            </RadioCardItem>
          ))}
        </RadioGroup>
      </fieldset>
      {selected ? (
        <fieldset className="space-y-3">
          <legend className="mb-2 font-display text-lg font-bold">Which level?</legend>
          <RadioGroup value={level} onValueChange={onLevel} className="sm:grid-cols-3">
            {selected.levels.map((l) => (
              <RadioCardItem key={l.code} value={l.code}>
                <span className="block font-semibold">{l.name}</span>
              </RadioCardItem>
            ))}
          </RadioGroup>
        </fieldset>
      ) : null}
      {level ? (
        <p role="status" className="text-sm text-muted-foreground">
          {schemeLoading
            ? 'Checking the syllabus…'
            : schemeName
              ? `Syllabus: ${schemeName}`
              : 'The syllabus for this level is not ready yet. Please pick another level.'}
        </p>
      ) : null}
      <Button size="lg" onClick={onNext} disabled={!course || !level || schemeLoading || !schemeName}>
        Continue
      </Button>
    </div>
  )
}

interface TermProps {
  terms: ExamTerm[]
  termId: string
  examDate: string
  dailyHours: string
  pending: boolean
  /** True when the next step is the elective choice, so this one only continues. */
  hasElectives?: boolean
  error?: string
  onTerm: (id: string) => void
  onExamDate: (v: string) => void
  onDailyHours: (v: string) => void
  onBack: () => void
  onSubmit: () => void
}

/** Step 2: exam attempt, optional exact date, optional daily study hours. */
export function TermStep({
  terms,
  termId,
  examDate,
  dailyHours,
  pending,
  hasElectives = false,
  error,
  onTerm,
  onExamDate,
  onDailyHours,
  onBack,
  onSubmit,
}: TermProps) {
  const hours = dailyHours.trim() === '' ? null : Number(dailyHours)
  const hoursError =
    hours !== null && (!Number.isFinite(hours) || hours < 0.5 || hours > 24)
      ? 'Enter hours between 0.5 and 24.'
      : undefined
  function submit(e: FormEvent) {
    e.preventDefault()
    if (!hoursError) onSubmit()
  }
  return (
    <form onSubmit={submit} noValidate className="space-y-6">
      <div className="grid gap-2">
        <Label htmlFor="term">Which attempt are you aiming for?</Label>
        <SelectField
          id="term"
          value={termId}
          onValueChange={onTerm}
          options={[{ value: '', label: 'I am not sure yet' }, ...terms.map((t) => ({ value: t.id, label: t.name }))]}
        />
      </div>
      <TextField
        label="Exam date (optional)"
        type="date"
        value={examDate}
        onChange={(e) => onExamDate(e.target.value)}
        hint="Use this if you know your exact paper dates."
      />
      <TextField
        label="Study hours per day (optional)"
        inputMode="decimal"
        value={dailyHours}
        onChange={(e) => onDailyHours(e.target.value)}
        error={hoursError}
        hint="Helps plan your preparation later."
      />
      {error ? <Alert variant="error">{error}</Alert> : null}
      <div className="flex flex-wrap gap-3">
        <Button type="button" variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button type="submit" size="lg" disabled={pending || Boolean(hoursError)}>
          {pending ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
          {hasElectives ? 'Continue' : 'Create my syllabus map'}
        </Button>
      </div>
    </form>
  )
}

interface ElectiveStepProps {
  slots: ElectiveSlotInfo[]
  choices: Record<string, string>
  pending: boolean
  error?: string
  onChoose: (slotKey: string, subjectId: string | null) => void
  onBack: () => void
  onSubmit: () => void
}

/** Step 3 (only for levels with elective papers): pick the elective you will sit, or decide later. */
export function ElectiveStep({ slots, choices, pending, error, onChoose, onBack, onSubmit }: ElectiveStepProps) {
  return (
    <div className="space-y-6">
      <p className="text-muted-foreground">
        You sit just one option for each elective paper, so only that one should count toward your coverage. You can
        change it any time from your syllabus map.
      </p>
      {slots.map((slot) => (
        <ElectiveChoice
          key={slot.key}
          slot={slot}
          value={choices[slot.key] ?? null}
          disabled={pending}
          onChange={(id) => onChoose(slot.key, id)}
        />
      ))}
      {error ? <Alert variant="error">{error}</Alert> : null}
      <div className="flex flex-wrap gap-3">
        <Button type="button" variant="outline" onClick={onBack} disabled={pending}>
          Back
        </Button>
        <Button size="lg" onClick={onSubmit} disabled={pending}>
          {pending ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
          Create my syllabus map
        </Button>
      </div>
    </div>
  )
}
