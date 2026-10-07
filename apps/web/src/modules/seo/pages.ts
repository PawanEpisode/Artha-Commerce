import type { Course, Feature, Level } from '~/modules/catalog'

import { buildHead, DEFAULT_OG_IMAGE } from './head'
import { breadcrumbJsonLd, faqJsonLd, organizationJsonLd, websiteJsonLd } from './jsonld'
import { chapterOgPath, courseOgPath } from './og-card'

/**
 * All page copy for link previews and search results, in one typed place.
 * Static pages are declared once in STATIC_PAGES; pages built from data have a function below.
 * Routes only call these (`head: () => pageHead('/features')`), so no meta string is written twice.
 *
 * Rules: title <= 60 chars including the " | ArthaCommerce" suffix (added by buildHead), description 120-155 chars,
 * written for CA / CS / CMA students in India.
 */

export interface StaticPage {
  title: string
  description: string
  /** Generic image of the section (all are 1200x630 PNGs under 300 KB in public/og). */
  image?: string
  imageAlt?: string
  /** Pages that must not be indexed (sign-in, token links, internal style guide). Their preview still renders. */
  noindex?: boolean
}

export const STATIC_PAGES = {
  '/': {
    title: 'ArthaCommerce: Exam Prep Workspace for CA, CS, CMA',
    description:
      'Plan your study, track every chapter, practise mock tests and revise smarter. The exam preparation workspace for CA, CS and CMA students in India.',
    imageAlt: 'ArthaCommerce: your entire exam prep in one calm workspace for CA, CS and CMA students',
  },
  '/features': {
    title: 'Features for CA, CS and CMA Students',
    description:
      'Syllabus tracking, a Pomodoro focus timer and a study time tracker are ready for CA, CS and CMA students. Mock tests, notes and more are coming soon.',
    image: '/og/features.png',
    imageAlt: 'ArthaCommerce features: syllabus tracker, focus timer and study hours',
  },
  '/courses': {
    title: 'CA, CS and CMA Courses and Syllabus',
    description:
      'Explore Foundation, Intermediate or Executive and Final or Professional levels of CA, CS and CMA, paper by paper, with chapters and marks weightage.',
    image: '/og/courses.png',
    imageAlt: 'CA, CS and CMA courses, paper by paper',
  },
  '/login': {
    title: 'Sign in',
    description:
      'Sign in to your ArthaCommerce workspace to pick up your CA, CS or CMA syllabus coverage, focus rounds and study hours where you left off.',
    noindex: true,
  },
  '/signup': {
    title: 'Create your free account',
    description:
      'Create a free ArthaCommerce account to track your CA, CS or CMA syllabus, run focus rounds and see your study hours and streaks in one calm place.',
    noindex: true,
  },
  '/auth/callback': {
    title: 'Signing you in',
    description:
      'Finishing your ArthaCommerce sign-in. You will be taken to your workspace in a moment, so please keep this page open until then.',
    noindex: true,
  },
  '/auth/confirm': {
    title: 'Confirming your email link',
    description:
      'Confirming your ArthaCommerce email link. If this page does not move on, request a new sign-in or reset link and try again.',
    noindex: true,
  },
  '/unsubscribe': {
    title: 'Unsubscribe',
    description:
      'Stop receiving the ArthaCommerce weekly summary email. This page opens from the signed link in the email and needs no sign-in.',
    noindex: true,
  },
  '/auth/forgot-password': {
    title: 'Reset your password',
    description:
      'Forgot your ArthaCommerce password? Enter your email and we will send you a secure link to choose a new one, free of charge.',
    noindex: true,
  },
  '/auth/reset-password': {
    title: 'Choose a new password',
    description:
      'Choose a new password for your ArthaCommerce account. Use at least eight characters, then sign in to continue your preparation.',
    noindex: true,
  },
  '/design-system': {
    title: 'Design system',
    description:
      'Internal style guide of ArthaCommerce: colours, themes, type, components and motion used across the product. Not public.',
    noindex: true,
  },
} as const satisfies Record<string, StaticPage>

export type StaticPath = keyof typeof STATIC_PAGES

/**
 * The head of a page whose copy is fixed. The home page also emits Organization and WebSite data; pass the FAQ that
 * the page renders as `faq` and it is emitted as FAQPage (only ever pass what is visible on the page).
 * WebSite has no SearchAction on purpose: the site has no public search endpoint to point at.
 */
export function pageHead(path: StaticPath, extra: { faq?: Array<{ q: string; a: string }> } = {}) {
  const page: StaticPage = STATIC_PAGES[path]
  const jsonLd =
    path === '/' ? [organizationJsonLd(), websiteJsonLd(), ...(extra.faq ? [faqJsonLd(extra.faq)] : [])] : undefined
  return buildHead({
    title: page.title,
    description: page.description,
    path,
    image: page.image ?? DEFAULT_OG_IMAGE,
    imageAlt: page.imageAlt,
    noindex: page.noindex,
    jsonLd,
  })
}

const crumbs = (...trail: Array<{ name: string; path: string }>) =>
  breadcrumbJsonLd([{ name: 'Home', path: '/' }, ...trail])

export function featureHead(feature: Pick<Feature, 'slug' | 'title' | 'tagline' | 'description'>) {
  const path = `/features/${feature.slug}`
  return buildHead({
    title: feature.title,
    description: `${feature.tagline} ${feature.description}`,
    path,
    image: '/og/features.png',
    imageAlt: `${feature.title} on ArthaCommerce`,
    jsonLd: crumbs({ name: 'Features', path: '/features' }, { name: feature.title, path }),
  })
}

/** Structural inputs: the same shapes come from the static catalog and from the API, whose slugs are plain strings. */
type CourseInput = Pick<Course, 'name' | 'fullName' | 'description' | 'bodyFullName'> & { slug: string }
type LevelInput = Pick<Level, 'name'> & { slug: string }

export function courseHead(course: CourseInput) {
  const path = `/courses/${course.slug}`
  return buildHead({
    title: `${course.name} (${course.fullName}) Exam Preparation`,
    description: course.description,
    path,
    image: courseOgPath(course.slug),
    imageAlt: `${course.fullName} (${course.name}) exam preparation`,
    jsonLd: crumbs({ name: 'Courses', path: '/courses' }, { name: course.name, path }),
  })
}

export function levelHead(course: CourseInput, level: LevelInput, subjectCount: number, hasChapters: boolean) {
  const path = `/courses/${course.slug}/${level.slug}`
  return buildHead({
    title: `${course.name} ${level.name}: Papers and Preparation`,
    description: `All ${subjectCount} papers of ${course.name} ${level.name}${hasChapters ? ', with chapters and marks weightage' : ''}, plus study planning, mock tests and revision tools.`,
    path,
    image: courseOgPath(course.slug),
    imageAlt: `${course.name} ${level.name} papers and preparation`,
    jsonLd: crumbs(
      { name: 'Courses', path: '/courses' },
      { name: course.name, path: `/courses/${course.slug}` },
      { name: level.name, path },
    ),
  })
}

export interface SubjectInput {
  key: string
  name: string
  total_marks?: string | number | null
  chapters: Array<{ name: string }>
}

export function subjectHead(course: CourseInput, level: LevelInput, subject: SubjectInput) {
  const path = `/courses/${course.slug}/${level.slug}/${subject.key}`
  const marks = subject.total_marks ? `, ${subject.total_marks} marks` : ''
  return buildHead({
    title: `${subject.name}: ${course.name} ${level.name} Syllabus`,
    description: `${subject.name} for ${course.name} ${level.name}: ${subject.chapters.length} chapters${marks}, with marks weightage and topics to plan your preparation.`,
    path,
    image: courseOgPath(course.slug),
    imageAlt: `${subject.name}, ${course.name} ${level.name}`,
    jsonLd: [
      crumbs(
        { name: 'Courses', path: '/courses' },
        { name: course.name, path: `/courses/${course.slug}` },
        { name: level.name, path: `/courses/${course.slug}/${level.slug}` },
        { name: subject.name, path },
      ),
      {
        '@context': 'https://schema.org',
        '@type': 'Course',
        name: `${subject.name} (${course.name} ${level.name})`,
        description: `Syllabus of ${subject.name} for ${course.name} ${level.name}.`,
        provider: { '@type': 'Organization', name: course.bodyFullName },
        hasPart: subject.chapters.map((c) => ({ '@type': 'Course', name: c.name })),
      },
    ],
  })
}

export interface ChapterInput {
  key: string
  name: string
  subject: { key: string; name: string }
  topics: unknown[]
}

export function chapterHead(course: CourseInput, level: LevelInput, chapter: ChapterInput) {
  const subjectPath = `/courses/${course.slug}/${level.slug}/${chapter.subject.key}`
  const path = `${subjectPath}/${chapter.key}`
  return buildHead({
    title: `${chapter.name}: ${chapter.subject.name}, ${course.name} ${level.name}`,
    description: `${chapter.name} in ${chapter.subject.name} (${course.name} ${level.name}): ${chapter.topics.length} topics and marks weightage, with a way to track your progress.`,
    path,
    image: chapterOgPath(course.slug, level.slug, chapter.subject.key, chapter.key),
    imageAlt: `${chapter.name}, ${chapter.subject.name} (${course.name} ${level.name})`,
    type: 'article',
    jsonLd: [
      breadcrumbJsonLd([
        { name: 'Home', path: '/' },
        { name: 'Courses', path: '/courses' },
        { name: course.name, path: `/courses/${course.slug}` },
        { name: level.name, path: `/courses/${course.slug}/${level.slug}` },
        { name: chapter.subject.name, path: subjectPath },
        { name: chapter.name, path },
      ]),
      {
        '@context': 'https://schema.org',
        '@type': 'Article',
        headline: `${chapter.name}: ${chapter.subject.name}`,
        about: `${course.name} ${level.name} ${chapter.subject.name}`,
      },
    ],
  })
}
