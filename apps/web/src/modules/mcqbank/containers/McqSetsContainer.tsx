import { ArrowLeft, ButtonLink, Container, Skeleton, toast } from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { ExternalLogDialog } from '../components/ExternalLogDialog'
import { SetCard } from '../components/SetCard'
import { listMcqSets, startSetPractice } from '../lib/api'
import type { McqFilter, McqSetCard } from '../lib/types'

interface McqSetsContainerProps {
  initialFilter?: McqFilter
  title?: string
  subtitle?: string
}

export function McqSetsContainer({
  initialFilter = {},
  title = 'MCQ Practice Sets',
  subtitle = 'Platform-hosted high-yield sprints and official ICMAI question banks.',
}: McqSetsContainerProps) {
  const navigate = useNavigate()
  const [sets, setSets] = useState<McqSetCard[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isStarting, setIsStarting] = useState(false)
  const [logDialogSet, setLogDialogSet] = useState<McqSetCard | null>(null)

  const filterKey = JSON.stringify(initialFilter)

  useEffect(() => {
    async function load() {
      try {
        const items = await listMcqSets(initialFilter)
        setSets(items)
      } catch (err: unknown) {
        toast.error(err instanceof Error ? err.message : 'Failed to load MCQ sets')
      } finally {
        setIsLoading(false)
      }
    }
    load()
  }, [filterKey, initialFilter])

  async function handleStartSet(slug: string) {
    try {
      setIsStarting(true)
      const res = await startSetPractice(slug, 'untimed')
      navigate({
        to: '/app/practice/session/$id',
        params: { id: res.session_id },
      })
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Could not start set')
      setIsStarting(false)
    }
  }

  if (isLoading) {
    return (
      <Container className="space-y-6 py-8">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-44 w-full" />
          <Skeleton className="h-44 w-full" />
          <Skeleton className="h-44 w-full" />
        </div>
      </Container>
    )
  }

  return (
    <Container className="space-y-8 py-8">
      <div className="space-y-4">
        <ButtonLink
          asChild
          variant="ghost"
          size="sm"
          className="-ml-2 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <Link to="/app/mcq">
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to MCQ Bank
          </Link>
        </ButtonLink>

        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
        </div>
      </div>

      {sets.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sets.map((s) => (
            <SetCard
              key={s.id}
              set={s}
              onStartPractice={handleStartSet}
              onOpenExternalLog={(item) => setLogDialogSet(item)}
              isStarting={isStarting}
            />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">
          No MCQ practice sets found matching criteria.
        </div>
      )}

      {/* External Score Dialog */}
      <ExternalLogDialog
        open={!!logDialogSet}
        onOpenChange={(open) => !open && setLogDialogSet(null)}
        set={logDialogSet}
      />
    </Container>
  )
}
