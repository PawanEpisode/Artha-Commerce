import {
  Badge,
  Button,
  ButtonLink,
  EmptyState,
  Page,
  PageHeader,
  Play,
  Skeleton,
  StatTile,
  toastApiError,
} from '@artha/design-system'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { ExternalLogDialog, getMcqSet, type McqSetDetail, startSetPractice } from '~/modules/mcqbank'
import { buildHead } from '~/modules/seo'

export const Route = createFileRoute('/app/mcq/sets/$slug')({
  head: ({ params }) =>
    buildHead({
      title: `MCQ Set: ${params.slug}`,
      description: 'MCQ practice set details and timed/untimed practice.',
      path: `/app/mcq/sets/${params.slug}`,
      noindex: true,
    }),
  component: function McqSetDetailRoute() {
    const { slug } = Route.useParams()
    const navigate = useNavigate()
    const [set, setSet] = useState<McqSetDetail | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [isStarting, setIsStarting] = useState(false)
    const [showLogDialog, setShowLogDialog] = useState(false)

    useEffect(() => {
      async function load() {
        try {
          const detail = await getMcqSet(slug)
          setSet(detail)
        } catch (err: unknown) {
          toastApiError(err, 'Failed to load practice set')
        } finally {
          setIsLoading(false)
        }
      }
      load()
    }, [slug])

    async function handleStartPractice(mode: 'untimed' | 'timed' = 'untimed') {
      try {
        setIsStarting(true)
        const res = await startSetPractice(slug, mode)
        navigate({
          to: '/app/practice/session/$id',
          params: { id: res.session_id },
        })
      } catch (err: unknown) {
        toastApiError(err, 'Could not start practice session')
        setIsStarting(false)
      }
    }

    if (isLoading) {
      return (
        <Page>
          <div role="status" aria-busy="true" aria-label="Loading set" className="space-y-3">
            <Skeleton className="h-8 w-96 max-w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        </Page>
      )
    }

    if (!set) {
      return (
        <Page>
          <EmptyState title="Practice set not found." />
        </Page>
      )
    }

    const isHosted = set.delivery === 'hosted'

    return (
      <Page>
        <PageHeader
          eyebrow={
            <Link to="/app/mcq/sets" className="hover:underline">
              MCQ sets
            </Link>
          }
          title={
            <span className="inline-flex items-center gap-2">
              {set.title}
              <Badge variant="outline" className="uppercase">
                {set.set_kind.replace(/_/g, ' ')}
              </Badge>
            </span>
          }
          description={set.description || undefined}
          actions={
            isHosted ? (
              <>
                <Button variant="outline" disabled={isStarting} onClick={() => handleStartPractice('timed')}>
                  Timed Mode
                </Button>
                <Button disabled={isStarting} onClick={() => handleStartPractice('untimed')}>
                  <Play aria-hidden className="size-3.5 fill-current" />
                  Practice Untimed
                </Button>
              </>
            ) : undefined
          }
        />

        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatTile label="Questions" value={`${set.question_count} MCQs`} />
          <StatTile label="Estimated Time" value={`${set.est_minutes} min`} />
          <StatTile
            label="Delivery Mode"
            value={<span className="capitalize">{set.delivery.replace(/_/g, ' ')}</span>}
          />
          <StatTile label="Source" value={set.source_name || 'ArthaCommerce'} />
        </div>

        {!isHosted && set.source_url && (
          <div className="flex flex-wrap gap-2">
            <ButtonLink variant="outline" size="sm" href={set.source_url} target="_blank" rel="noreferrer">
              Open Official ICMAI PDF
            </ButtonLink>
            <Button size="sm" onClick={() => setShowLogDialog(true)}>
              Log Physical Score
            </Button>
          </div>
        )}

        <ExternalLogDialog open={showLogDialog} onOpenChange={setShowLogDialog} set={set} />
      </Page>
    )
  },
})
