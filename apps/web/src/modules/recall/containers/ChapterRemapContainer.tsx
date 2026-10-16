import { ButtonLink, CircleCheck, EmptyState, PageHeader, Skeleton } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { ChapterRemapRow, ChapterRemapTable } from '../components/ChapterRemapList'
import { LoadError, RecallShell } from '../components/RecallShell'
import { useChapterRemaps, useChooseChapter } from '../hooks/useUpdates'
import { errorText } from '../lib/errors'
import { remapSummary } from '../lib/updates'

function Remaps() {
  const q = useChapterRemaps()
  const choose = useChooseChapter()
  return (
    <>
      <PageHeader
        title="Needs a new chapter"
        description="You moved to a new syllabus. Pick a chapter for each card that did not move by itself. Nothing about your memory changes."
      />
      {q.isPending ? (
        <div aria-busy="true" className="space-y-1">
          <span className="sr-only" role="status">
            Loading…
          </span>
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : q.isError ? (
        <LoadError what="your cards" onRetry={() => void q.refetch()} />
      ) : q.data.items.length === 0 ? (
        <EmptyState
          className="rounded-lg py-6"
          icon={<CircleCheck aria-hidden />}
          title="Every card has a chapter"
          description="Nothing is waiting for a chapter of your new syllabus."
          action={
            <ButtonLink variant="outline" size="sm" asChild>
              <Link to="/app/recall">Back to revision</Link>
            </ButtonLink>
          }
        />
      ) : (
        <>
          <p className="text-[13px] font-medium">{remapSummary(q.data.items)}</p>
          <ChapterRemapTable>
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
          </ChapterRemapTable>
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
