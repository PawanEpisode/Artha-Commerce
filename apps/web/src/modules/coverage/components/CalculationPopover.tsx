import { Button, CircleHelp, Popover, PopoverContent, PopoverTrigger } from '@artha/design-system'

import type { CoverageSettings } from '../lib/types'

/** "How is this calculated?" (PRD FR-16): the real formula with the student's own weights. */
export function CalculationPopover({
  weights,
}: {
  weights: Pick<CoverageSettings, 'w_read' | 'w_practice' | 'w_revise' | 'w_mock'>
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm">
          <CircleHelp aria-hidden /> How is this calculated?
        </Button>
      </PopoverTrigger>
      <PopoverContent className="space-y-2">
        <p className="font-semibold">Chapter coverage</p>
        <p>
          Reading {weights.w_read}% + practice {weights.w_practice}% + revision {weights.w_revise}% + mock tests{' '}
          {weights.w_mock}%.
        </p>
        <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
          <li>Reading is topics ticked out of all topics.</li>
          <li>
            Practice, revision and mocks fill up as you reach each chapter&apos;s target (for example 2 revisions).
          </li>
          <li>A part with no target is left out and its share goes to the others.</li>
          <li>Subject and level percentages average their chapters. Chapters you exclude are not counted.</li>
        </ul>
        <p className="text-muted-foreground">You can change the weights in Coverage settings.</p>
      </PopoverContent>
    </Popover>
  )
}
