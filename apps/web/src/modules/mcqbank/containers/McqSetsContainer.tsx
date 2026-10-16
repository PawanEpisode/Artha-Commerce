import { EmptyState, Page, PageHeader, Skeleton, toast } from '@artha/design-system'
import { Link, useNavigate } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { ExternalLogDialog } from '../components/ExternalLogDialog'
import { SetsTable } from '../components/SetsTable'
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
      <Page>
        <div role="status" aria-busy="true" aria-label="Loading MCQ sets" className="space-y-3">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-48 w-full" />
        </div>
      </Page>
    )
  }

  return (
    <Page>
      <PageHeader
        eyebrow={
          <Link to="/app/mcq" className="hover:underline">
            MCQ Bank
          </Link>
        }
        title={title}
        description={subtitle}
      />

      {sets.length > 0 ? (
        <SetsTable
          sets={sets}
          onStartPractice={handleStartSet}
          onOpenExternalLog={(item) => setLogDialogSet(item)}
          isStarting={isStarting}
        />
      ) : (
        <EmptyState title="No MCQ practice sets found matching criteria." />
      )}

      <ExternalLogDialog
        open={!!logDialogSet}
        onOpenChange={(open) => !open && setLogDialogSet(null)}
        set={logDialogSet}
      />
    </Page>
  )
}
