import { Button, Card, Sparkles } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { isSummaryActive, type SummaryJob } from '../../lib/ai-types'

interface SummaryOfferProps {
  chapterId: string
  /** The newest summary of this chapter, if there is one worth showing (a draft, a running job). */
  job: SummaryJob | null | undefined
}

/** A quiet card on the chapter page: write an exam summary from your own notes, or go back to the one in progress. */
export function SummaryOffer({ chapterId, job }: SummaryOfferProps) {
  const open = job && (isSummaryActive(job.status) || job.status === 'ready')
  return (
    <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
      <div className="min-w-0 space-y-1">
        <h2 className="flex items-center gap-2 font-semibold">
          <Sparkles aria-hidden className="size-4 text-primary" /> Exam summary
        </h2>
        <p className="text-sm text-muted-foreground">
          {open
            ? job.status === 'ready'
              ? 'A draft is ready for you to check.'
              : 'Your summary is being written.'
            : 'Turn your notes and highlights for this chapter into a short revision summary. You check it before it is saved.'}
        </p>
      </div>
      <Button variant={open ? 'default' : 'outline'} asChild>
        {open ? (
          <Link to="/app/notes/summary/$jobId" params={{ jobId: job.id }}>
            {job.status === 'ready' ? 'Review the draft' : 'See progress'}
          </Link>
        ) : (
          <Link to="/app/notes/summary/new" search={{ chapter: chapterId }}>
            Write a summary
          </Link>
        )}
      </Button>
    </Card>
  )
}
