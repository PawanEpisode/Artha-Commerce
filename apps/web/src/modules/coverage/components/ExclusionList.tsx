import { Card, Label, Switch } from '@artha/design-system'

import type { SubjectRow } from '../lib/types'

/** Exclude a whole paper (for example an optional paper you are not taking). Chapters are excluded on their own page. */
export function ExclusionList({
  subjects,
  pending,
  onChange,
}: {
  subjects: SubjectRow[]
  pending: boolean
  onChange: (s: SubjectRow, excluded: boolean) => void
}) {
  return (
    <Card className="space-y-4 p-6">
      <div>
        <h2 className="font-display text-xl font-bold">Papers you are not taking</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Excluded papers are left out of your percentages. Your progress is kept, and comes back if you include them
          again. Elective papers are not listed here: choose yours on the syllabus map.
        </p>
      </div>
      <ul className="divide-y">
        {subjects
          .filter((s) => !s.elective_slot)
          .map((s) => {
            const excluded = s.chapters_total === 0 && s.excluded_chapters > 0
            return (
              <li key={s.id} className="flex items-center justify-between gap-4 py-3">
                <Label htmlFor={`exclude-${s.id}`} className="min-w-0 flex-1 font-medium">
                  {s.name}
                </Label>
                <span className="text-sm text-muted-foreground">{excluded ? 'Excluded' : 'Counted'}</span>
                <Switch
                  id={`exclude-${s.id}`}
                  checked={excluded}
                  disabled={pending}
                  onCheckedChange={(v) => onChange(s, v)}
                  aria-label={`Exclude ${s.name}`}
                />
              </li>
            )
          })}
      </ul>
    </Card>
  )
}
