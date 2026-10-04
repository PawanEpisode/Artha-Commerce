import { Section } from '@artha/design-system'

import { PlannerPreview } from '~/modules/planner-preview'

import { CourseCards } from '../components/CourseCards'
import { Faq } from '../components/Faq'
import { FeatureGrid } from '../components/FeatureGrid'
import { FinalCta } from '../components/FinalCta'
import { Hero } from '../components/Hero'
import { HowItWorks } from '../components/HowItWorks'

/** Composes landing sections. Contains no markup of its own, only order. */
export function LandingPage() {
  return (
    <>
      <Hero />
      <CourseCards />
      <Section
        id="planner"
        eyebrow="Try it now"
        title="See your plan in 10 seconds"
        description="Move the sliders and watch your study hours take shape. No sign-up needed."
        className="bg-muted/40"
      >
        <PlannerPreview />
      </Section>
      <FeatureGrid />
      <HowItWorks />
      <Faq />
      <FinalCta />
    </>
  )
}
