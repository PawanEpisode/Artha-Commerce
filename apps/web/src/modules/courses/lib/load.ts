import { type Course, courses as staticCourses, type Level } from '~/modules/catalog'
import { type CourseSummary, fetchCourses, fetchLevel } from '~/modules/syllabus'

/**
 * A course as the public pages show it. Same shape as the static catalog entry, but the slug is any course code the
 * API knows, not only ca, cs and cma.
 */
export type PublicCourse = Omit<Course, 'slug'> & { slug: string }

const byOrder = (a: { sort_order: number }, b: { sort_order: number }) => a.sort_order - b.sort_order

/**
 * Merges what the API knows about a course over its static catalog entry. The API is the truth for the course
 * description and the list of levels; the catalog fills in what the API does not carry (tagline, full body name) and
 * keeps any level that is not in the database yet.
 */
export function mergeCourse(api: CourseSummary | undefined, fallback: Course | undefined): PublicCourse | null {
  if (!api && !fallback) return null
  const slug = (api?.code ?? fallback?.slug ?? '').toLowerCase()
  const staticLevels = new Map((fallback?.levels ?? []).map((l) => [l.slug, l]))
  const apiLevels: Level[] = [...(api?.levels ?? [])].sort(byOrder).map((l) => ({
    slug: l.code.toLowerCase(),
    name: l.name,
    subjects: staticLevels.get(l.code.toLowerCase())?.subjects ?? [],
  }))
  const seen = new Set(apiLevels.map((l) => l.slug))
  const levels = [...apiLevels, ...(fallback?.levels ?? []).filter((l) => !seen.has(l.slug))]
  return {
    slug,
    name: fallback?.name ?? api?.code.toUpperCase() ?? slug.toUpperCase(),
    fullName: fallback?.fullName ?? api?.name ?? slug.toUpperCase(),
    body: fallback?.body ?? api?.institute_name ?? '',
    bodyFullName: fallback?.bodyFullName ?? api?.institute_name ?? '',
    tagline: fallback?.tagline ?? '',
    description: api?.description || fallback?.description || '',
    levels,
  }
}

async function apiCourses(): Promise<CourseSummary[]> {
  try {
    return await fetchCourses()
  } catch {
    return []
  }
}

/** Every course for /courses: the API's, with static-only courses kept so a half-seeded database never hides one. */
export async function loadCourses(): Promise<PublicCourse[]> {
  const fromApi = await apiCourses()
  const out: PublicCourse[] = []
  const used = new Set<string>()
  for (const base of staticCourses) {
    const merged = mergeCourse(
      fromApi.find((c) => c.code.toLowerCase() === base.slug),
      base,
    )
    if (merged) out.push(merged)
    used.add(base.slug)
  }
  for (const api of fromApi) {
    if (used.has(api.code.toLowerCase())) continue
    const merged = mergeCourse(api, undefined)
    if (merged) out.push(merged)
  }
  return out
}

/**
 * One course by slug. With `papers`, each level's paper names come from the curated syllabus when there is one
 * (the course page lists a few of them); the static list is the fallback per level.
 */
export async function loadCourse(slug: string, options: { papers?: boolean } = {}): Promise<PublicCourse | null> {
  const course = (await loadCourses()).find((c) => c.slug === slug.toLowerCase())
  if (!course || !options.papers) return course ?? null
  const levels = await Promise.all(
    course.levels.map(async (l) => {
      const syllabus = await fetchLevel(course.slug, l.slug)
      return syllabus && syllabus.subjects.length ? { ...l, subjects: syllabus.subjects.map((s) => s.name) } : l
    }),
  )
  return { ...course, levels }
}

export const findLevel = (course: PublicCourse, slug: string): Level | undefined =>
  course.levels.find((l) => l.slug === slug.toLowerCase())
