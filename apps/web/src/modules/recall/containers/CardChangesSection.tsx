import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@artha/design-system'
import { useState } from 'react'

import { CardChangesList } from '../components/CardChangesList'
import { useCardChanges } from '../hooks/useHistory'

/** "What changed" on the card page. Closed by default; the read happens when she opens it. */
export function CardChangesSection({ cardId }: { cardId: string }) {
  const [open, setOpen] = useState('')
  const q = useCardChanges(cardId, open === 'changes')
  return (
    <section aria-labelledby="changes-heading" className="space-y-2">
      <h2 id="changes-heading" className="font-display text-xl font-bold">
        What changed
      </h2>
      <Accordion type="single" collapsible value={open} onValueChange={setOpen}>
        <AccordionItem value="changes">
          <AccordionTrigger>Versions of this card</AccordionTrigger>
          <AccordionContent>
            <CardChangesList
              changes={q.data}
              loading={q.isPending && open === 'changes'}
              failed={q.isError}
              onRetry={() => void q.refetch()}
            />
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </section>
  )
}
