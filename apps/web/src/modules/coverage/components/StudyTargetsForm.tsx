import { Alert, Button, Card, LoaderCircle } from '@artha/design-system'
import { useState } from 'react'

import { targetsEqual, targetsValid } from '../lib/targets'
import type { CoverageSettings, Targets } from '../lib/types'
import { TargetsFields } from './TargetsFields'

interface Props {
  settings: Pick<CoverageSettings, 'targets' | 'target_presets' | 'target_limits' | 'targets_confirmed'>
  pending: boolean
  error?: string
  onSave: (next: Targets) => void
}

/** "Study targets" card of the coverage settings (PRD FR-F16-20..24). */
export function StudyTargetsForm({ settings, pending, error, onSave }: Props) {
  const [draft, setDraft] = useState<Targets>(settings.targets)
  const { min, max } = settings.target_limits
  const changed = !targetsEqual(draft, settings.targets)
  const valid = targetsValid(draft, min, max)

  return (
    <Card className="space-y-5 p-6">
      <div>
        <h2 className="font-display text-xl font-bold">Study targets</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          What you aim to finish in every chapter. Chapters count as done when you reach these. Set 0 to leave one out.
        </p>
      </div>
      <TargetsFields
        value={draft}
        presets={settings.target_presets}
        limits={settings.target_limits}
        onChange={setDraft}
        disabled={pending}
      />
      {error ? <Alert variant="error">{error}</Alert> : null}
      <div className="flex flex-wrap items-center gap-3">
        <Button size="lg" disabled={!changed || !valid || pending} onClick={() => onSave(draft)}>
          {pending ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
          Save targets
        </Button>
        {changed ? (
          <Button variant="ghost" size="lg" disabled={pending} onClick={() => setDraft(settings.targets)}>
            Discard changes
          </Button>
        ) : null}
      </div>
    </Card>
  )
}
