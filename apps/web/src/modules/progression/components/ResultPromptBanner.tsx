import { Button, Sparkles, X } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'

import { useProgressionStatus } from '../hooks/useProgression'

export function ResultPromptBanner() {
  const { data: statusData } = useProgressionStatus()
  const [dismissed, setDismissed] = useState(false)

  const prompt = statusData?.result_prompt
  if (!prompt?.should_prompt || dismissed) {
    return null
  }

  return (
    <div
      role="region"
      aria-label="Exam result announcement banner"
      className="relative mb-4 flex flex-col items-start justify-between gap-3 rounded-xl border border-primary/20 bg-gradient-to-r from-primary/10 via-primary/5 to-background p-4 shadow-sm md:flex-row md:items-center"
    >
      <div className="flex items-center gap-3">
        <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/20 text-primary">
          <Sparkles className="size-5" />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-foreground">
            {prompt.term_name} Results Announced! Did you update your progress?
          </h2>
          <p className="text-xs text-muted-foreground">
            Clear a group, graduate to Final, or record 60+ paper exemptions to recalibrate your daily study plan.
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 self-end md:self-auto">
        <Button asChild size="sm" className="h-8 gap-1.5 shadow-sm">
          <Link to="/app/transition">
            Update My Progress
            <Sparkles className="size-3.5" />
          </Link>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-8 text-muted-foreground hover:text-foreground"
          onClick={() => setDismissed(true)}
          aria-label="Dismiss banner"
        >
          <X className="size-4" />
        </Button>
      </div>
    </div>
  )
}
