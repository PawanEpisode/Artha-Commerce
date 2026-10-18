import {
  Button,
  Play,
  SegmentedControl,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@artha/design-system'
import { useState } from 'react'

import { defaultPracticeCount, practiceCountOptions } from '../lib/practice-options'
import type { PracticeFeedback } from '../lib/types'

interface ChapterPracticeBarProps {
  /** Choice questions in the chapter. */
  available: number
  isStarting: boolean
  onStart: (count: number, feedback: PracticeFeedback) => void
}

/** Pick how many questions and when to see the markings, then start a practice session on this chapter. */
export function ChapterPracticeBar({ available, isStarting, onStart }: ChapterPracticeBarProps) {
  const options = practiceCountOptions(available)
  const [count, setCount] = useState<number | undefined>(() => defaultPracticeCount(options))
  const [feedback, setFeedback] = useState<PracticeFeedback>('instant')

  if (options.length === 0) return null
  // The chapter can shrink between visits; never submit a count it no longer has.
  const chosen = options.some((o) => o.value === count) ? count : defaultPracticeCount(options)

  return (
    <div
      role="group"
      aria-label="Practise this chapter"
      className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card px-3 py-2"
    >
      <span className="text-[13px] font-medium text-foreground">Practise this chapter</span>
      <Select value={String(chosen)} onValueChange={(v) => setCount(Number(v))}>
        <SelectTrigger aria-label="Number of questions" className="w-36">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((o) => (
            <SelectItem key={o.value} value={String(o.value)}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <SegmentedControl<PracticeFeedback>
        label="When to see answers"
        value={feedback}
        onValueChange={setFeedback}
        options={[
          { value: 'instant', label: 'Answers as I go' },
          { value: 'at_end', label: 'Check at the end' },
        ]}
      />
      <Button
        size="sm"
        disabled={isStarting || chosen === undefined}
        onClick={() => chosen !== undefined && onStart(chosen, feedback)}
        className="ml-auto"
      >
        <Play aria-hidden className="size-3.5 fill-current" />
        Start practice
      </Button>
    </div>
  )
}
