import { Container, Section, Skeleton } from '@artha/design-system'

import { useAuth } from '~/modules/auth'
import { type PublicCourse, StudyHomeContainer } from '~/modules/courses'
import { PlannerPreview } from '~/modules/planner-preview'

import { CourseCards } from '../components/CourseCards'
import { Faq } from '../components/Faq'
import { FeatureWalkthrough } from '../components/FeatureWalkthrough'
import { FinalCta } from '../components/FinalCta'
import { Hero } from '../components/Hero'
import { HowItWorks } from '../components/HowItWorks'
import { InsightBand } from '../components/InsightBand'
import { SIGNED_IN_MARK_CSS } from '../lib/sessionMark'

function MarketingHome() {
  return (
    <div data-marketing-home>
      <Hero />
      <InsightBand />
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
      <FeatureWalkthrough />
      <HowItWorks />
      <Faq />
      <FinalCta />
    </div>
  )
}

function StudyPending() {
  return (
    <div data-study-pending>
      <Container className="py-16" aria-busy="true">
        <p className="sr-only">Loading your course</p>
        <Skeleton className="h-10 w-2/3 max-w-md" />
        <Skeleton className="mt-8 h-40 w-full rounded-xl" />
      </Container>
    </div>
  )
}

/** Guests get the marketing page. A signed-in student gets their course, on this same URL. */
export function LandingPage({ courses }: { courses: PublicCourse[] }) {
  const { user, loading } = useAuth()
  const signedIn = !loading && Boolean(user)
  if (signedIn) return <StudyHomeContainer courses={courses} />
  return (
    <>
      <style>{SIGNED_IN_MARK_CSS}</style>
      <MarketingHome />
      <StudyPending />
    </>
  )
}
