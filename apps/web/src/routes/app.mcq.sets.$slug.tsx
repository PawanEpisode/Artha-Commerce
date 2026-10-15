import {
  ArrowLeft,
  Badge,
  Button,
  ButtonLink,
  Card,
  Clock,
  Container,
  Play,
  Skeleton,
  toast,
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
          const msg = err instanceof Error ? err.message : 'Failed to load practice set'
          toast.error(msg)
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
        const msg = err instanceof Error ? err.message : 'Could not start practice session'
        toast.error(msg)
        setIsStarting(false)
      }
    }

    if (isLoading) {
      return (
        <Container className="space-y-6 py-8">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-10 w-96" />
          <Skeleton className="h-44 w-full" />
        </Container>
      )
    }

    if (!set) {
      return (
        <Container className="py-8">
          <div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">
            Practice set not found.
          </div>
        </Container>
      )
    }

    const isHosted = set.delivery === 'hosted'

    return (
      <Container className="space-y-8 py-8">
        <div className="space-y-4">
          <ButtonLink
            asChild
            variant="ghost"
            size="sm"
            className="-ml-2 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <Link to="/app/mcq/sets">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Sets
            </Link>
          </ButtonLink>

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">{set.title}</h1>
                <Badge variant="outline" className="text-xs uppercase">
                  {set.set_kind.replace('_', ' ')}
                </Badge>
              </div>
              {set.description && <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{set.description}</p>}
            </div>

            {isHosted && (
              <div className="flex items-center gap-2">
                <Button
                  size="default"
                  variant="outline"
                  disabled={isStarting}
                  onClick={() => handleStartPractice('timed')}
                  className="font-semibold"
                >
                  Timed Mode
                </Button>
                <Button
                  size="default"
                  disabled={isStarting}
                  onClick={() => handleStartPractice('untimed')}
                  className="gap-2 font-semibold shadow"
                >
                  <Play className="h-4 w-4 fill-current" />
                  Practice Untimed
                </Button>
              </div>
            )}
          </div>
        </div>

        <Card className="space-y-4 p-6">
          <h2 className="text-sm font-semibold tracking-wider text-muted-foreground uppercase">Set Information</h2>
          <div className="grid grid-cols-2 gap-4 text-xs sm:grid-cols-4">
            <div>
              <span className="block text-muted-foreground">Questions</span>
              <span className="text-base font-semibold text-foreground">{set.question_count} MCQs</span>
            </div>
            <div>
              <span className="block text-muted-foreground">Estimated Time</span>
              <span className="flex items-center gap-1 text-base font-semibold text-foreground">
                <Clock className="h-3.5 w-3.5" />
                {set.est_minutes} min
              </span>
            </div>
            <div>
              <span className="block text-muted-foreground">Delivery Mode</span>
              <span className="text-base font-semibold text-foreground capitalize">{set.delivery}</span>
            </div>
            <div>
              <span className="block text-muted-foreground">Source</span>
              <span className="text-base font-semibold text-foreground">{set.source_name || 'ArthaCommerce'}</span>
            </div>
          </div>

          {!isHosted && set.source_url && (
            <div className="flex flex-wrap gap-3 border-t pt-4">
              <ButtonLink variant="outline" size="sm" href={set.source_url} target="_blank" rel="noreferrer">
                Open Official ICMAI PDF
              </ButtonLink>
              <Button variant="default" size="sm" onClick={() => setShowLogDialog(true)}>
                Log Physical Score
              </Button>
            </div>
          )}
        </Card>

        {/* External Score Dialog */}
        <ExternalLogDialog open={showLogDialog} onOpenChange={setShowLogDialog} set={set} />
      </Container>
    )
  },
})
