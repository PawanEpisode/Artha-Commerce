import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { AiPageDialog } from '../components/ai/AiPageDialog'
import { PageReadNotice } from '../components/ai/PageReadNotice'
import { useAiAvailable, useAiConsent, useAiOcrJob, useGrantConsent, useRequestAiOcr } from '../hooks/useAi'
import { usePageText } from '../hooks/useDocuments'
import { useUsage } from '../hooks/useNotesQueries'
import {
  aiPagesAllowance,
  aiPagesText,
  canImprove,
  pageQuality,
  pageReadFailureText,
  startFailureText,
} from '../lib/ai-copy'
import { isSummaryActive } from '../lib/ai-types'
import { notesKeys } from '../lib/keys'
import { notify } from '../lib/notify'

/**
 * The quality line and "Improve this page" of the reader. Hidden unless AI is on for this student. One job at a time per
 * page; when it ends the page text and the search are read again, so the better text shows at once.
 */
export function AiPageReadContainer({ docId, page }: { docId: string; page: number }) {
  const ai = useAiAvailable()
  return ai.available ? <PageRead docId={docId} page={page} /> : null
}

function PageRead({ docId, page }: { docId: string; page: number }) {
  const qc = useQueryClient()
  const text = usePageText(docId, page)
  const consent = useAiConsent()
  const usage = useUsage()
  const grant = useGrantConsent()
  const request = useRequestAiOcr()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string>()
  const [tracked, setTracked] = useState<{ id: string; page: number } | null>(null)
  const job = useAiOcrJob(tracked?.id)
  const announced = useRef<string>('')

  const status = job.data?.status
  useEffect(() => {
    if (!tracked || !job.data || isSummaryActive(job.data.status) || announced.current === tracked.id) return
    announced.current = tracked.id
    void qc.invalidateQueries({ queryKey: ['notes', 'document', docId, 'text'] })
    void qc.invalidateQueries({ queryKey: notesKeys.usage })
    if (job.data.status === 'accepted') notify.aiPageRead(tracked.page)
  }, [tracked, job.data, qc, docId])

  const here = tracked && tracked.page === page ? tracked : null
  const working = !!here && (status === undefined || isSummaryActive(status))
  const failed = here && job.data && job.data.status !== 'accepted' && !isSummaryActive(job.data.status)
  const allowance = aiPagesAllowance(usage.data)
  const quality = pageQuality(text.page?.source, text.page?.conf)

  const start = async () => {
    setError(undefined)
    const result = await request.mutateAsync({ docId, page })
    if (!result.ok) {
      if (result.failure.reason === 'not_consented') void consent.refetch()
      else setError(startFailureText(result.failure))
      return
    }
    if (result.started.job) setTracked({ id: result.started.job.id, page })
    setOpen(false)
  }

  return (
    <>
      <PageReadNotice
        page={page}
        quality={quality}
        canImprove={canImprove(text.page?.source, text.page?.conf)}
        working={working}
        message={
          failed ? pageReadFailureText(job.data?.error_code ?? Object.values(job.data?.failed ?? {})[0]) : undefined
        }
        onImprove={() => setOpen(true)}
      />
      <AiPageDialog
        open={open}
        onOpenChange={setOpen}
        page={page}
        consentText={consent.data && !consent.data.consented ? consent.data.text : undefined}
        consentPending={grant.isPending}
        consentFailed={grant.isError}
        onAgree={() => consent.data && grant.mutate(consent.data.text.version)}
        allowance={aiPagesText(allowance)}
        canStart={(allowance?.left ?? 0) > 0}
        busy={request.isPending}
        error={error}
        onStart={() => void start()}
      />
    </>
  )
}
