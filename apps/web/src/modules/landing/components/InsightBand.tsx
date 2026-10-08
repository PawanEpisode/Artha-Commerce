import { Container, Reveal } from '@artha/design-system'

import { insightBand } from '../data/story'

export function InsightBand() {
  return (
    <section className="py-16 sm:py-24" aria-labelledby="insight-title">
      <Container className="max-w-4xl text-center">
        <Reveal>
          <p className="text-sm font-semibold tracking-widest text-primary uppercase">{insightBand.eyebrow}</p>
          <h2 id="insight-title" className="mt-4 font-display text-3xl font-extrabold sm:text-5xl sm:leading-[1.1]">
            {insightBand.title}
          </h2>
          <p className="prose-reading mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">{insightBand.body}</p>
        </Reveal>
      </Container>
    </section>
  )
}
