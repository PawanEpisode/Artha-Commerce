import { ArrowLeft, Badge, Button, Check, Container } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { FeatureIcon } from '~/components/feature-icon'
import type { Feature } from '~/modules/catalog'

import type { FeatureOffer } from '../lib/offers'
import { BrowseButton, OfferButton, type OpenDestination } from './OfferLink'

interface Props {
  feature: Feature
  offer: FeatureOffer
  /** Shipped tools to offer when this one is not open yet. */
  alternatives: FeatureOffer[]
  onOpen: (slug: string, destination: OpenDestination) => void
}

export function FeatureDetail({ feature, offer, alternatives, onOpen }: Props) {
  const comingSoon = offer.destination === 'soon'
  return (
    <Container className="max-w-3xl py-12 sm:py-20">
      <Button variant="link" className="mb-8 px-0" asChild>
        <Link to="/features">
          <ArrowLeft /> All features
        </Link>
      </Button>
      <span className="grid size-14 place-items-center rounded-2xl bg-secondary text-primary">
        <FeatureIcon name={feature.icon} className="size-7" />
      </span>
      <h1 className="mt-6 text-4xl font-extrabold sm:text-5xl">{feature.title}</h1>
      <p className="mt-3 text-xl text-muted-foreground">{feature.tagline}</p>
      {comingSoon ? (
        <Badge variant="outline" className="mt-4">
          Coming soon
        </Badge>
      ) : null}
      <p className="mt-8 text-lg leading-relaxed">{feature.description}</p>
      <ul className="mt-8 space-y-3">
        {feature.highlights.map((h) => (
          <li key={h} className="flex items-start gap-3">
            {comingSoon ? (
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-muted-foreground" aria-hidden />
            ) : (
              <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-accent/20 text-accent-foreground dark:text-accent">
                <Check className="size-4" aria-hidden />
              </span>
            )}
            {h}
          </li>
        ))}
      </ul>

      {comingSoon ? (
        <p className="mt-8 rounded-xl border border-dashed p-4 text-muted-foreground">
          This is not in the workspace yet.
        </p>
      ) : (
        <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
          <OfferButton offer={offer} size="lg" className="w-full sm:w-auto" onOpen={onOpen} />
          <BrowseButton offer={offer} className="w-full sm:w-auto" onOpen={onOpen} />
        </div>
      )}

      {comingSoon && alternatives.length > 0 ? (
        <section className="mt-12" aria-labelledby="available-now-heading">
          <h2 id="available-now-heading" className="text-xl font-bold">
            Available now
          </h2>
          <p className="mt-2 text-muted-foreground">Open a tool that already works.</p>
          <ul className="mt-4 flex list-none flex-col gap-3 sm:flex-row sm:flex-wrap">
            {alternatives.map((alt) => (
              <li key={alt.feature.slug}>
                <OfferButton offer={alt} className="w-full sm:w-auto" onOpen={onOpen} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </Container>
  )
}
