import { Badge, Card, Container } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { FeatureIcon } from '~/components/feature-icon'

import type { FeatureOffer } from '../lib/offers'
import { BrowseButton, OfferButton, type OpenDestination } from './OfferLink'

interface Props {
  ready: FeatureOffer[]
  soon: FeatureOffer[]
  onOpen: (slug: string, destination: OpenDestination) => void
}

function Actions({ offer, onOpen, large }: { offer: FeatureOffer; onOpen: Props['onOpen']; large?: boolean }) {
  return (
    <>
      <OfferButton offer={offer} size={large ? 'lg' : 'default'} className="w-full sm:w-auto" onOpen={onOpen} />
      <BrowseButton offer={offer} className="w-full sm:w-auto" onOpen={onOpen} />
    </>
  )
}

function Hero({ offer, onOpen }: { offer: FeatureOffer; onOpen: Props['onOpen'] }) {
  const { feature } = offer
  return (
    <Card className="flex flex-col gap-6 border-primary p-6 sm:flex-row sm:items-center sm:p-8">
      <span className="grid size-14 shrink-0 place-items-center rounded-2xl bg-secondary text-primary">
        <FeatureIcon name={feature.icon} className="size-7" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-primary">Start here</p>
        <h2 className="mt-1 text-2xl font-bold">{feature.title}</h2>
        <p className="mt-2 text-muted-foreground">{feature.tagline}</p>
        <p className="mt-3">
          <Link
            to="/features/$slug"
            params={{ slug: feature.slug }}
            className="inline-flex min-h-11 items-center text-sm font-semibold text-primary underline-offset-4 hover:underline"
          >
            How it works
          </Link>
        </p>
      </div>
      <div className="flex w-full flex-col gap-2 sm:w-auto">
        <Actions offer={offer} onOpen={onOpen} large />
      </div>
    </Card>
  )
}

function ReadyCard({ offer, onOpen }: { offer: FeatureOffer; onOpen: Props['onOpen'] }) {
  const { feature } = offer
  return (
    <Card className="flex h-full flex-col p-6">
      <span className="grid size-12 place-items-center rounded-xl bg-secondary text-primary">
        <FeatureIcon name={feature.icon} className="size-6" />
      </span>
      <h3 className="mt-4 text-lg font-semibold">{feature.title}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{feature.tagline}</p>
      <div className="mt-5 flex flex-1 flex-col justify-end gap-2">
        <Actions offer={offer} onOpen={onOpen} />
        <Link
          to="/features/$slug"
          params={{ slug: feature.slug }}
          className="inline-flex min-h-11 items-center text-sm font-semibold text-primary underline-offset-4 hover:underline"
        >
          How it works
        </Link>
      </div>
    </Card>
  )
}

export function FeaturesIndex({ ready, soon, onOpen }: Props) {
  const [hero, ...rest] = ready
  return (
    <Container className="py-12 sm:py-20">
      <header className="max-w-2xl">
        <p className="mb-3 text-sm font-semibold tracking-widest text-primary uppercase">Features</p>
        <h1 className="text-3xl font-bold sm:text-4xl">What you can use today</h1>
        <p className="mt-4 text-lg text-muted-foreground">
          Syllabus coverage, a focus timer and a time tracker are ready. Everything else is coming soon.
        </p>
      </header>

      {hero ? (
        <div className="mt-10">
          <Hero offer={hero} onOpen={onOpen} />
        </div>
      ) : (
        <p className="mt-10 text-muted-foreground">
          Nothing is open for your account yet. The tools below are on the way.
        </p>
      )}

      {rest.length > 0 ? (
        <ul className="mt-5 grid list-none gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {rest.map((offer) => (
            <li key={offer.feature.slug}>
              <ReadyCard offer={offer} onOpen={onOpen} />
            </li>
          ))}
        </ul>
      ) : null}

      {soon.length > 0 ? (
        <section className="mt-14" aria-labelledby="coming-soon-heading">
          <h2 id="coming-soon-heading" className="text-2xl font-bold">
            Coming soon
          </h2>
          <p className="mt-2 max-w-2xl text-muted-foreground">These are not in the workspace yet.</p>
          <ul className="mt-6 grid list-none gap-5 sm:grid-cols-2">
            {soon.map(({ feature }) => (
              <li key={feature.slug}>
                <Link to="/features/$slug" params={{ slug: feature.slug }} className="group block h-full">
                  <Card className="flex h-full flex-col p-6 transition-all group-hover:-translate-y-1 group-hover:shadow-lift">
                    <div className="flex items-start justify-between gap-3">
                      <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-secondary text-primary">
                        <FeatureIcon name={feature.icon} className="size-6" />
                      </span>
                      <Badge variant="outline">Coming soon</Badge>
                    </div>
                    <h3 className="mt-4 text-lg font-semibold">{feature.title}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{feature.tagline}</p>
                  </Card>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </Container>
  )
}
