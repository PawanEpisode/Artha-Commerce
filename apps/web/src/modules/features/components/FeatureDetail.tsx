import { Badge, Button, Container } from '@artha/design-system'
import { Link } from '@tanstack/react-router'
import { ArrowLeft, Check } from 'lucide-react'

import { FeatureIcon } from '~/components/feature-icon'
import type { Feature } from '~/modules/catalog'

export function FeatureDetail({ feature }: { feature: Feature }) {
  return (
    <Container className="max-w-3xl py-16 sm:py-24">
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
      {feature.status === 'soon' && (
        <Badge variant="highlight" className="mt-4">
          Early access
        </Badge>
      )}
      <p className="mt-8 text-lg leading-relaxed">{feature.description}</p>
      <ul className="mt-8 space-y-3">
        {feature.highlights.map((h) => (
          <li key={h} className="flex items-start gap-3">
            <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-accent/20 text-accent-foreground dark:text-accent">
              <Check className="size-4" />
            </span>
            {h}
          </li>
        ))}
      </ul>
      <Button size="lg" className="mt-10" asChild>
        <Link to="/login">Get early access</Link>
      </Button>
    </Container>
  )
}
