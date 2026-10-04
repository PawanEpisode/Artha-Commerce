import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '~/components/ui/accordion'
import { Container } from '~/design-system'
import { faqItems } from '../data/faq'

export function Faq() {
  return (
    <section className="py-20 sm:py-28" aria-labelledby="faq-title">
      <Container className="max-w-3xl">
        <h2 id="faq-title" className="mb-10 text-center text-3xl font-bold sm:text-4xl">
          Questions, answered
        </h2>
        <Accordion type="single" collapsible>
          {faqItems.map((item, i) => (
            <AccordionItem key={item.q} value={`item-${i}`}>
              <AccordionTrigger>{item.q}</AccordionTrigger>
              <AccordionContent>{item.a}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </Container>
    </section>
  )
}
