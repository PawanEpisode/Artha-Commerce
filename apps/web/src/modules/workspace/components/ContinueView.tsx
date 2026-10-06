import { ArrowRight, Button, buttonVariants, ProgressBar } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import type { ContinueChapter } from '~/modules/coverage'

/** The last chapter studied, with its percent, or the way into the syllabus map on day one. */
export function ContinueView({
  chapter,
  onReturn,
}: {
  chapter: ContinueChapter | null
  /** When no chapter was studied yet but the student left a restorable page, a way back to it. */
  onReturn?: () => void
}) {
  if (!chapter) {
    return (
      <>
        <p className="text-sm text-muted-foreground">Your syllabus map shows every paper and chapter you can start.</p>
        {onReturn ? (
          <Button variant="outline" className="self-start" onClick={onReturn}>
            Return to your last page
          </Button>
        ) : null}
        <Link to="/app/syllabus" className={`mt-auto self-start ${buttonVariants({ variant: 'cta' })}`}>
          Open the syllabus map
          <ArrowRight aria-hidden />
        </Link>
      </>
    )
  }
  return (
    <>
      <div className="min-w-0 space-y-2">
        <p className="text-sm text-muted-foreground">{chapter.subject.name}</p>
        <p className="text-lg font-semibold break-words">{chapter.name}</p>
        <ProgressBar value={chapter.coverage_pct} label={`${chapter.name} coverage`} />
        <p className="text-sm text-muted-foreground tabular-nums">{chapter.coverage_pct}% covered</p>
      </div>
      <Link
        to="/app/syllabus/$subject/$chapter"
        params={{ subject: chapter.subject.id, chapter: chapter.id }}
        className={`mt-auto self-start ${buttonVariants({ variant: 'cta' })}`}
      >
        Continue <span className="sr-only">{chapter.name}</span>
        <ArrowRight aria-hidden />
      </Link>
    </>
  )
}
