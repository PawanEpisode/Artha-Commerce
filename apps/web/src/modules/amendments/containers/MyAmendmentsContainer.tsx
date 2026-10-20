import { Alert, Button, CircleCheck, EmptyState, FileText, Skeleton } from '@artha/design-system'
import { useMemo, useState } from 'react'

import { ApplicabilityFilter } from '../components/ApplicabilityFilter'
import { ChangeCard } from '../components/ChangeCard'
import { type GroupingMode, GroupingTabs } from '../components/GroupingTabs'
import { ProgressSummary } from '../components/ProgressSummary'
import { useCardActions } from '../hooks/useCardActions'
import { useMyCards } from '../hooks/useMyCards'
import { useMySummary } from '../hooks/useMySummary'
import type { CardFilter, MyCard } from '../lib/types'
import { AmendmentsShell } from './AmendmentsShell'

export function MyAmendmentsContainer() {
  const { data: summary } = useMySummary()
  const [filter, setFilter] = useState<CardFilter>({
    applies: 'mine',
    state: undefined,
    q: '',
    subject: undefined,
  })
  const [grouping, setGrouping] = useState<GroupingMode>('paper')
  const { bulkReview, isBulkReviewing } = useCardActions()

  const { data: cardsResult, isPending, isError, refetch } = useMyCards(filter)

  const cards = useMemo(() => cardsResult?.cards ?? [], [cardsResult?.cards])

  const handleFilterChange = (updated: Partial<CardFilter>) => {
    setFilter((prev) => ({ ...prev, ...updated }))
  }

  // Group cards according to selected grouping mode
  const groupedCards = useMemo(() => {
    if (grouping === 'flat') {
      return [{ key: 'all', title: 'All Amendments', cards }]
    }

    const groups = new Map<string, { key: string; title: string; cards: MyCard[] }>()

    for (const card of cards) {
      let groupKey = 'Other'
      let groupTitle = 'Other / General'

      if (grouping === 'paper') {
        const primary = card.mappings.find((m) => m.is_primary) ?? card.mappings[0]
        groupKey = primary?.subject_key ?? 'Other'
        groupTitle = primary?.subject_key ?? 'Other'
      } else if (grouping === 'chapter') {
        const primary = card.mappings.find((m) => m.is_primary) ?? card.mappings[0]
        groupKey = `${primary?.subject_key ?? 'Other'} - ${primary?.chapter_key ?? 'General'}`
        groupTitle = groupKey
      } else if (grouping === 'type') {
        groupKey = card.change_type
        groupTitle = card.change_type.toUpperCase()
      }

      let group = groups.get(groupKey)
      if (!group) {
        group = { key: groupKey, title: groupTitle, cards: [] }
        groups.set(groupKey, group)
      }
      group.cards.push(card)
    }

    return Array.from(groups.values())
  }, [cards, grouping])

  return (
    <AmendmentsShell>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">Amendments Engine</h1>
            <p className="text-sm text-muted-foreground">
              Official statutory and academic amendments curated and mapped to your syllabus chapters.
            </p>
          </div>
        </div>

        {/* Progress and Target Term Summary */}
        {summary && (
          <ProgressSummary
            summary={summary}
            activeSubject={filter.subject}
            onSelectSubject={(subjectKey) => handleFilterChange({ subject: subjectKey || undefined })}
          />
        )}

        {/* Filters and Search Bar */}
        <div className="space-y-3 rounded-lg border bg-card p-4 shadow-sm">
          <ApplicabilityFilter filter={filter} onChange={handleFilterChange} />
          <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-3">
            <GroupingTabs value={grouping} onChange={setGrouping} />
            <div className="text-xs text-muted-foreground">
              {cardsResult ? `${cardsResult.total_count} amendments matching` : 'Loading…'}
            </div>
          </div>
        </div>

        {/* Cards Content */}
        {isPending ? (
          <div aria-busy="true" className="space-y-4">
            <span className="sr-only" role="status">
              Loading amendment cards…
            </span>
            <Skeleton className="h-32 w-full rounded-lg" />
            <Skeleton className="h-32 w-full rounded-lg" />
            <Skeleton className="h-32 w-full rounded-lg" />
          </div>
        ) : isError ? (
          <Alert variant="error">
            <span className="flex flex-wrap items-center justify-between gap-3">
              <span>Could not load amendment cards.</span>
              <Button size="sm" variant="outline" onClick={() => void refetch()}>
                Try again
              </Button>
            </span>
          </Alert>
        ) : cards.length === 0 ? (
          <EmptyState
            className="rounded-lg border border-dashed py-12"
            icon={<FileText className="h-10 w-10 text-muted-foreground" aria-hidden />}
            title="No amendments match your filter"
            description="Try switching the applicability filter to 'All attempts' or clear your search term."
          >
            {(filter.q || filter.state || filter.subject || filter.applies !== 'mine') && (
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setFilter({
                    applies: 'mine',
                    state: undefined,
                    q: '',
                    subject: undefined,
                  })
                }
              >
                Reset filters
              </Button>
            )}
          </EmptyState>
        ) : (
          <div className="space-y-8">
            {groupedCards.map((group) => {
              const unreviewedCards = group.cards.filter((c) => !c.is_reviewed)
              const allReviewed = unreviewedCards.length === 0

              return (
                <section key={group.key} aria-labelledby={`group-${group.key}`} className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b pb-2">
                    <div className="flex items-center gap-2">
                      <h2 id={`group-${group.key}`} className="text-base font-semibold text-foreground">
                        {group.title}
                      </h2>
                      <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                        {group.cards.length}
                      </span>
                    </div>

                    {grouping === 'paper' && group.cards.length > 0 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={isBulkReviewing || allReviewed}
                        onClick={() =>
                          bulkReview(
                            group.cards.map((c) => c.public_id),
                            true,
                          )
                        }
                        className="text-xs text-muted-foreground hover:text-foreground"
                      >
                        <CircleCheck className="mr-1.5 h-3.5 w-3.5" />
                        {allReviewed ? 'All reviewed' : 'Mark all reviewed'}
                      </Button>
                    )}
                  </div>

                  <div className="space-y-3">
                    {group.cards.map((card) => (
                      <ChangeCard key={card.public_id} card={card} targetTerm={summary?.target_term} />
                    ))}
                  </div>
                </section>
              )
            })}
          </div>
        )}
      </div>
    </AmendmentsShell>
  )
}
