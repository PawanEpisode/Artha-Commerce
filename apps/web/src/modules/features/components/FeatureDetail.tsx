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
    <Container className="max-w-3xl py-6 sm:py-8">
      <Button variant="outline" size="sm" className="mb-5" asChild>
        <Link to="/features">
          <ArrowLeft /> All features
        </Link>
      </Button>
      <span className="grid size-9 place-items-center rounded-md bg-secondary text-primary">
        <FeatureIcon name={feature.icon} className="size-5" />
      </span>
      <h1 className="mt-4 text-2xl font-semibold tracking-tight">{feature.title}</h1>
      <p className="mt-1 text-base text-muted-foreground">{feature.tagline}</p>
      {comingSoon ? (
        <Badge variant="outline" className="mt-4">
          Coming soon
        </Badge>
      ) : null}
      <p className="mt-4 text-[15px] leading-relaxed">{feature.description}</p>
      <ul className="mt-5 space-y-2 text-[15px]">
        {feature.highlights.map((h) => (
          <li key={h} className="flex items-start gap-2.5">
            {comingSoon ? (
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-muted-foreground" aria-hidden />
            ) : (
              <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-accent/20 text-accent-foreground dark:text-accent">
                <Check className="size-3.5" aria-hidden />
              </span>
            )}
            {h}
          </li>
        ))}
      </ul>

      {comingSoon ? (
        <p className="mt-6 rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
          This is not in the workspace yet.
        </p>
      ) : (
        <div className="mt-6 flex flex-wrap gap-2">
          <OfferButton offer={offer} variant="default" onOpen={onOpen} />
          <BrowseButton offer={offer} onOpen={onOpen} />
        </div>
      )}

      {comingSoon && alternatives.length > 0 ? (
        <section className="mt-10" aria-labelledby="available-now-heading">
          <h2 id="available-now-heading" className="text-base font-semibold">
            Available now
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">Open a tool that already works.</p>
          <ul className="mt-3 flex list-none flex-wrap gap-2">
            {alternatives.map((alt) => (
              <li key={alt.feature.slug}>
                <OfferButton offer={alt} variant="default" onOpen={onOpen} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </Container>
  )
}
