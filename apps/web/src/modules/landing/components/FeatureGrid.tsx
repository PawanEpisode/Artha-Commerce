import { ArrowRight, Badge, buttonVariants, Card, Reveal, Section } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { FeatureIcon } from '~/components/feature-icon'
import { features } from '~/modules/catalog'

export function FeatureGrid() {
  return (
    <Section
      id="features"
      eyebrow="Features"
      title="Everything a commerce aspirant needs"
      description="Tools designed around how CA, CS and CMA students actually study."
      className="bg-muted/40"
    >
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {features.map((f, i) => (
          <Reveal key={f.slug} delay={(i % 3) * 0.08}>
            <Link
              to="/features/$slug"
              params={{ slug: f.slug }}
              className="group block h-full rounded-xl outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
            >
              <Card className="h-full p-6 transition-all group-hover:-translate-y-1 group-hover:shadow-lift">
                <div className="mb-5 flex items-center justify-between">
                  <span className="grid size-11 place-items-center rounded-xl bg-secondary text-primary">
                    <FeatureIcon name={f.icon} className="size-5" />
                  </span>
                  {f.status === 'soon' ? <Badge variant="outline">Coming soon</Badge> : null}
                </div>
                <h3 className="text-lg font-semibold">{f.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{f.tagline}</p>
                <span className="mt-4 block">
                  <span className={buttonVariants({ variant: 'outline', size: 'sm' })}>
                    {f.status === 'soon' ? 'Preview' : 'See'} {f.title}
                    <ArrowRight
                      aria-hidden
                      className="transition-transform group-hover:translate-x-1 motion-reduce:transition-none"
                    />
                  </span>
                </span>
              </Card>
            </Link>
          </Reveal>
        ))}
      </div>
    </Section>
  )
}
