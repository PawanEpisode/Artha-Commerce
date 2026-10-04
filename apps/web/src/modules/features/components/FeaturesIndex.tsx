import { Badge, Card, Section } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { FeatureIcon } from '~/components/feature-icon'
import { features } from '~/modules/catalog'

export function FeaturesIndex() {
  return (
    <Section
      eyebrow="Features"
      title="Built for how commerce students study"
      description="Explore every tool in the workspace."
    >
      <div className="grid gap-5 sm:grid-cols-2">
        {features.map((f) => (
          <Link key={f.slug} to="/features/$slug" params={{ slug: f.slug }} className="group block">
            <Card className="flex h-full gap-5 p-6 transition-all group-hover:-translate-y-1 group-hover:shadow-lift">
              <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-secondary text-primary">
                <FeatureIcon name={f.icon} className="size-6" />
              </span>
              <div>
                <h2 className="text-lg font-semibold">
                  {f.title}{' '}
                  {f.status === 'soon' && (
                    <Badge variant="highlight" className="ml-1 align-middle">
                      Early access
                    </Badge>
                  )}
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">{f.tagline}</p>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </Section>
  )
}
