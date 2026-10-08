import { Badge, Button, Check, Section, StickyStory, type StickyStoryStep } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

import { FeatureIcon } from '~/components/feature-icon'

import { featureBeats, featureForBeat } from '../data/story'
import { FeatureFrame } from './FeatureFrames'

function BeatCopy({ slug }: { slug: string }) {
  const beat = featureBeats.find((item) => item.slug === slug)
  if (!beat) return null
  const feature = featureForBeat(beat)
  const soon = feature.status === 'soon'
  return (
    <div>
      {soon ? (
        <Badge variant="outline" className="mb-4">
          Coming soon
        </Badge>
      ) : (
        <p className="mb-4 text-sm font-semibold tracking-widest text-primary uppercase">Available now</p>
      )}
      <h3 className="font-display text-2xl font-extrabold sm:text-3xl">{beat.headline}</h3>
      <p className="prose-reading mt-4 text-base leading-relaxed text-muted-foreground sm:text-lg">{beat.insight}</p>
      <ul className="mt-6 space-y-3">
        {beat.points.map((point) => (
          <li key={point} className="flex items-start gap-3 text-sm sm:text-base">
            <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-accent/20 text-accent-foreground dark:text-accent">
              <Check className="size-3.5" aria-hidden />
            </span>
            <span>{point}</span>
          </li>
        ))}
      </ul>
      <Button variant="outline" size="sm" arrow className="mt-6" asChild>
        <Link to="/features/$slug" params={{ slug: beat.slug }}>
          {beat.cta}
        </Link>
      </Button>
    </div>
  )
}

function railLabel(slug: string) {
  const beat = featureBeats.find((item) => item.slug === slug)
  if (!beat) return null
  const feature = featureForBeat(beat)
  return (
    <span className="flex min-w-0 items-center gap-2">
      <FeatureIcon name={feature.icon} className="size-4 shrink-0" />
      <span className="truncate">{beat.rail}</span>
    </span>
  )
}

export function FeatureWalkthrough() {
  const steps: StickyStoryStep[] = featureBeats.map((beat) => ({
    id: `feature-${beat.slug}`,
    rail: railLabel(beat.slug),
    content: <BeatCopy slug={beat.slug} />,
    media: <FeatureFrame slug={beat.slug} />,
  }))

  return (
    <Section
      id="features"
      align="left"
      eyebrow="The workspace"
      title="Every tool a commerce attempt actually needs"
      description="Scroll the list. Each beat is a real study problem — coverage, hours, notes, mocks — not a feature catalogue."
    >
      <StickyStory label="Workspace tools" steps={steps} />
    </Section>
  )
}
