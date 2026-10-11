import { ButtonLink, CircleCheck, EmptyState, Skeleton } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { ChapterRemapRow } from '../components/ChapterRemapList'
import { LoadError, RecallShell } from '../components/RecallShell'
import { useChapterRemaps, useChooseChapter } from '../hooks/useUpdates'
import { errorText } from '../lib/errors'
import { remapSummary } from '../lib/updates'

function Remaps() {
  const q = useChapterRemaps()
  const choose = useChooseChapter()
  return (
    <>
      <header className="space-y-1">
        <h1 className="text-3xl font-extrabold">Needs a new chapter</h1>
        <p className="text-muted-foreground">
          You moved to a new syllabus. Pick a chapter for each card that did not move by itself. Nothing about your
          memory changes.
        </p>
      </header>
      {q.isPending ? (
        <div aria-busy="true" className="space-y-3">
          <span className="sr-only" role="status">
            Loading…
          </span>
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : q.isError ? (
        <LoadError what="your cards" onRetry={() => void q.refetch()} />
      ) : q.data.items.length === 0 ? (
        <EmptyState
          icon={<CircleCheck aria-hidden />}
          title="Every card has a chapter"
          description="Nothing is waiting for a chapter of your new syllabus."
          action={
            <ButtonLink variant="outline" asChild>
              <Link to="/app/recall">Back to revision</Link>
            </ButtonLink>
          }
        />
      ) : (
        <>
          <p className="text-sm font-medium">{remapSummary(q.data.items)}</p>
          <ul aria-label="Cards waiting for a chapter" className="space-y-3">
            {q.data.items.map((item) => (
              <ChapterRemapRow
                key={item.id}
                item={item}
                chapters={q.data.chapters}
                pending={choose.isPending && choose.variables?.remapId === item.id}
                error={
                  choose.isError && choose.variables?.remapId === item.id
                    ? errorText(choose.error, 'Could not move this card. Please try again.')
                    : null
                }
                onChoose={(chapterId) => choose.mutate({ remapId: item.id, chapterId, relation: item.relation })}
              />
            ))}
          </ul>
        </>
      )}
    </>
  )
}

export function ChapterRemapContainer() {
  return (
    <RecallShell>
      <Remaps />
    </RecallShell>
  )
}
