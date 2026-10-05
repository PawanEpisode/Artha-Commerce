import { siteUrl } from '~/lib/env'

/**
 * What an Open Graph preview card says. Pure text decisions (wording, truncation, font size) live here so they are
 * tested; drawing happens in `og-render.server.ts`.
 */

export interface OgCard {
  /** Small line above the title: "CA · Intermediate". */
  eyebrow: string
  title: string
  /** One line under the title. */
  subtitle: string
  /** Pills along the bottom. */
  facts: string[]
}

const MAX_TITLE = 92
const MAX_SUBTITLE = 120

/**
 * The bundled font covers Latin text. Anything else would draw as an empty box, so map the characters that occur in
 * syllabus names to plain equivalents and drop the rest.
 */
export function safeText(text: string): string {
  return text
    .replace(/\u20B9/g, 'Rs ')
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/[\u2013\u2014]/g, '-')
    .replace(/\u00A0/g, ' ')
    .replace(/[^\u0020-\u007E\u00A1-\u024F\u2022\u00B7]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

export function clamp(text: string, max: number): string {
  const clean = safeText(text)
  if (clean.length <= max) return clean
  return `${clean.slice(0, max - 1).trimEnd()}…`
}

/** Longer titles get smaller type so they stay inside three lines. */
export function titleSize(title: string): number {
  if (title.length <= 28) return 84
  if (title.length <= 52) return 68
  return 54
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

export function courseCard(input: {
  name: string
  fullName: string
  body: string
  levels: string[]
  description: string
}): OgCard {
  return {
    eyebrow: clamp(`${input.name} · ${input.body}`, 60),
    title: clamp(input.fullName, MAX_TITLE),
    subtitle: clamp(input.description, MAX_SUBTITLE),
    facts: input.levels.slice(0, 4).map((l) => clamp(l, 24)),
  }
}

export function chapterCard(input: {
  courseName: string
  levelName: string
  subjectName: string
  chapterName: string
  topicCount: number
  marks: string | null
}): OgCard {
  const facts = [plural(input.topicCount, 'topic')]
  if (input.marks) facts.push(`${input.marks} marks`)
  facts.push('Track your coverage')
  return {
    eyebrow: clamp(`${input.courseName} · ${input.levelName}`, 60),
    title: clamp(input.chapterName, MAX_TITLE),
    subtitle: clamp(input.subjectName, MAX_SUBTITLE),
    facts: facts.map((f) => clamp(f, 24)),
  }
}

/** "5 to 8" when the chapter has a marks range, "6" when it is a single figure, null when unknown. */
export function marksLabel(min: string | null, max: string | null): string | null {
  const a = min?.trim()
  const b = max?.trim()
  if (a && b && Number(a) !== Number(b)) return `${Number(a)} to ${Number(b)}`
  const only = a || b
  return only && Number.isFinite(Number(only)) ? String(Number(only)) : null
}

/** Where the generated preview image of a page lives. Pass the result as `image` to `buildHead`. */
export const courseOgPath = (course: string) => `/og/courses/${course}`
export const chapterOgPath = (course: string, level: string, subject: string, chapter: string) =>
  `/og/courses/${course}/${level}/${subject}/${chapter}`

const CACHE = 'public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800'

/** Responses of the image routes. A failure never returns an error page to a link unfurler: it sends the site image. */
export const ogResponse = {
  png: (bytes: Uint8Array) =>
    new Response(bytes as BodyInit, { headers: { 'Content-Type': 'image/png', 'Cache-Control': CACHE } }),
  notFound: () => new Response('Not found', { status: 404, headers: { 'Cache-Control': 'public, max-age=300' } }),
  /**
   * Serves the static site image with a 200 (unfurlers such as WhatsApp handle a direct image more reliably than a
   * redirect). Falls back to a redirect only if the static file cannot be fetched.
   */
  fallback: async (path: string): Promise<Response> => {
    try {
      const res = await fetch(`${siteUrl}${path}`)
      if (res.ok) {
        return new Response(res.body, {
          headers: { 'Content-Type': 'image/png', 'Cache-Control': 'public, max-age=300' },
        })
      }
    } catch {
      // fall through to the redirect
    }
    return new Response(null, { status: 302, headers: { Location: path, 'Cache-Control': 'no-store' } })
  },
}
