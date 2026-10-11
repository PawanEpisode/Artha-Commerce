import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@artha/design-system'
import { useState } from 'react'

import { UpdateHistoryList } from '../components/UpdateHistoryList'
import { useUpdateHistory } from '../hooks/useHistory'

/** "Past updates" on a deck she has. Closed by default; the read happens when she opens it. */
export function UpdateHistorySection({ subscriptionId }: { subscriptionId: string }) {
  const [open, setOpen] = useState('')
  const q = useUpdateHistory(subscriptionId, open === 'history')
  return (
    <section aria-labelledby="update-history-heading" className="space-y-1">
      <h2 id="update-history-heading" className="text-sm font-semibold">
        Past updates
      </h2>
      <Accordion type="single" collapsible value={open} onValueChange={setOpen}>
        <AccordionItem value="history">
          <AccordionTrigger>Show what past updates did</AccordionTrigger>
          <AccordionContent>
            <UpdateHistoryList
              rows={q.data}
              loading={q.isPending && open === 'history'}
              failed={q.isError}
              onRetry={() => void q.refetch()}
            />
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </section>
  )
}
