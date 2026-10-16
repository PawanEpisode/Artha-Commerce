import {
  Badge,
  Button,
  Container,
  DataTable,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { FeatureIcon } from '~/components/feature-icon'

import type { FeatureOffer } from '../lib/offers'
import { BrowseButton, OfferButton, type OpenDestination } from './OfferLink'

interface Props {
  ready: FeatureOffer[]
  soon: FeatureOffer[]
  onOpen: (slug: string, destination: OpenDestination) => void
}

function FeatureCell({ offer, first }: { offer: FeatureOffer; first?: boolean }) {
  const { feature } = offer
  return (
    <div className="flex min-w-0 items-center gap-3">
      <span className="grid size-8 shrink-0 place-items-center rounded-md bg-secondary text-primary">
        <FeatureIcon name={feature.icon} className="size-4" />
      </span>
      <div className="min-w-0">
        <p className="flex flex-wrap items-center gap-1.5 text-sm font-medium">
          <Link
            to="/features/$slug"
            params={{ slug: feature.slug }}
            className="rounded outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            {feature.title}
          </Link>
          {first ? <Badge variant="accent">Start here</Badge> : null}
        </p>
        <p className="text-[13px] text-muted-foreground">{feature.tagline}</p>
      </div>
    </div>
  )
}

function ReadyActions({ offer, onOpen }: { offer: FeatureOffer; onOpen: Props['onOpen'] }) {
  const { feature } = offer
  return (
    <div className="flex flex-wrap items-center justify-end gap-1.5">
      <OfferButton offer={offer} size="sm" variant="default" arrow={false} onOpen={onOpen} />
      <BrowseButton offer={offer} size="sm" arrow={false} onOpen={onOpen} />
      <Button variant="ghost" size="sm" className="text-primary" asChild>
        <Link to="/features/$slug" params={{ slug: feature.slug }}>
          How it works<span className="sr-only"> for {feature.title}</span>
        </Link>
      </Button>
    </div>
  )
}

export function FeaturesIndex({ ready, soon, onOpen }: Props) {
  return (
    <Container className="py-6 sm:py-8">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Features</h1>
        <p className="mt-1 text-sm text-muted-foreground">What you can use today. Everything else is coming soon.</p>
      </header>

      <section className="mt-6" aria-labelledby="available-heading">
        <h2 id="available-heading" className="mb-2 text-sm font-semibold">
          Available now
        </h2>
        {ready.length > 0 ? (
          <DataTable>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Feature</TableHead>
                <TableHead className="text-right">Open</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {ready.map((offer, i) => (
                <TableRow key={offer.feature.slug}>
                  <TableCell className="h-14 py-2">
                    <FeatureCell offer={offer} first={i === 0} />
                  </TableCell>
                  <TableCell className="py-2">
                    <ReadyActions offer={offer} onOpen={onOpen} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </DataTable>
        ) : (
          <p className="text-sm text-muted-foreground">
            Nothing is open for your account yet. The tools below are on the way.
          </p>
        )}
      </section>

      {soon.length > 0 ? (
        <section className="mt-8" aria-labelledby="coming-soon-heading">
          <h2 id="coming-soon-heading" className="mb-2 text-sm font-semibold">
            Coming soon
          </h2>
          <DataTable>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Feature</TableHead>
                <TableHead className="w-28 text-right">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {soon.map((offer) => (
                <TableRow key={offer.feature.slug}>
                  <TableCell className="h-14 py-2">
                    <FeatureCell offer={offer} />
                  </TableCell>
                  <TableCell className="py-2 text-right">
                    <Badge variant="outline">Coming soon</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </DataTable>
        </section>
      ) : null}
    </Container>
  )
}
