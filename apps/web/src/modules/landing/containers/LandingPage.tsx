import { Container, Section, Skeleton } from '@artha/design-system'
import { useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'

import { useAuth } from '~/modules/auth'
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
        <Skeleton className="mt-8 h-40 w-full rounded-lg" />
      </Container>
    </div>
  )
}

/**
 * Guests get the marketing page. A signed-in student has one home, the workspace: `/app?from=landing` also restores
 * the page they were last on.
 */
export function LandingPage() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const signedIn = !loading && Boolean(user)
  useEffect(() => {
    if (signedIn) void navigate({ to: '/app', search: { from: 'landing' }, replace: true })
  }, [signedIn, navigate])
  if (signedIn) return <StudyPending />
  return (
    <>
      <style>{SIGNED_IN_MARK_CSS}</style>
      <MarketingHome />
      <StudyPending />
    </>
  )
}
