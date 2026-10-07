import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import { courses, features } from '~/modules/catalog'

import { DESCRIPTION_MAX, TITLE_MAX } from './head'
import { chapterHead, courseHead, featureHead, levelHead, pageHead, STATIC_PAGES, subjectHead } from './pages'
import { buildRobotsTxt } from './robots'
import { buildSitemapXml, publicPaths } from './sitemap'

type Tag = Record<string, string | undefined>
type Head = ReturnType<typeof pageHead>
const title = (h: Head) => (h.meta as Tag[])[0]!.title!
const meta = (h: Head, key: 'name' | 'property', value: string) =>
  (h.meta as Tag[]).find((m) => m[key] === value)?.content

function expectCompleteHead(h: Head) {
  expect(title(h).length).toBeLessThanOrEqual(TITLE_MAX)
  const description = meta(h, 'name', 'description')!
  expect(description.length).toBeGreaterThanOrEqual(60)
  expect(description.length).toBeLessThanOrEqual(DESCRIPTION_MAX)
  expect(h.links[0]).toMatchObject({ rel: 'canonical' })
  expect(meta(h, 'property', 'og:url')).toBe((h.links[0] as { href: string }).href)
  expect(meta(h, 'property', 'og:image')).toMatch(/^https?:\/\//)
  expect(meta(h, 'name', 'twitter:card')).toBe('summary_large_image')
}

/** Every head the site can produce from static copy and from the catalog. */
function allHeads(): Array<{ id: string; head: Head }> {
  const out: Array<{ id: string; head: Head }> = (Object.keys(STATIC_PAGES) as Array<keyof typeof STATIC_PAGES>).map(
    (p) => ({ id: p, head: pageHead(p) }),
  )
  for (const f of features) out.push({ id: `/features/${f.slug}`, head: featureHead(f) })
  for (const c of courses) {
    out.push({ id: `/courses/${c.slug}`, head: courseHead(c) })
    for (const l of c.levels) {
      out.push({ id: `/courses/${c.slug}/${l.slug}`, head: levelHead(c, l, l.subjects.length, false) })
    }
  }
  return out
}

describe('page copy', () => {
  it('every static page, feature, course and level has a complete head', () => {
    for (const { head } of allHeads()) expectCompleteHead(head)
  })

  it('titles, descriptions and canonicals are unique across all pages', () => {
    const heads = allHeads()
    for (const pick of [
      (h: Head) => title(h),
      (h: Head) => meta(h, 'name', 'description'),
      (h: Head) => (h.links[0] as { href: string }).href,
    ]) {
      const values = heads.map(({ head }) => pick(head))
      expect(new Set(values).size).toBe(values.length)
    }
  })

  it('static page descriptions are 120-155 characters', () => {
    for (const [path, page] of Object.entries(STATIC_PAGES)) {
      expect(page.description.length, path).toBeGreaterThanOrEqual(120)
      expect(page.description.length, path).toBeLessThanOrEqual(DESCRIPTION_MAX)
    }
  })

  it('private pages are noindex and public pages are not', () => {
    for (const [path, page] of Object.entries(STATIC_PAGES)) {
      const noindex = meta(pageHead(path as keyof typeof STATIC_PAGES), 'name', 'robots') === 'noindex, nofollow'
      const isPrivate =
        path === '/design-system' ||
        path.startsWith('/auth/') ||
        path === '/login' ||
        path === '/signup' ||
        path === '/unsubscribe'
      expect(noindex, path).toBe(isPrivate)
      expect('noindex' in page && page.noindex === true, path).toBe(isPrivate)
    }
  })

  it('home carries Organization, WebSite (no fake SearchAction) and only the FAQ it is given', () => {
    const home = pageHead('/', { faq: [{ q: 'Q?', a: 'A.' }] })
    const types = home.scripts.map((s) => JSON.parse(s.children)['@type'])
    expect(types).toEqual(['Organization', 'WebSite', 'FAQPage'])
    expect(home.scripts.some((s) => s.children.includes('SearchAction'))).toBe(false)
    expect(pageHead('/').scripts).toHaveLength(2)
    expect(pageHead('/features').scripts).toHaveLength(0)
  })

  it('syllabus pages use their own images, breadcrumbs and article type', () => {
    const c = courses[0]!
    const l = c.levels[0]!
    const subject = { key: 'taxation', name: 'Taxation', total_marks: '100', chapters: [{ name: 'Income' }] }
    const sh = subjectHead(c, l, subject)
    expectCompleteHead(sh)
    expect(sh.scripts.map((s) => JSON.parse(s.children)['@type'])).toEqual(['BreadcrumbList', 'Course'])
    const ch = chapterHead(c, l, {
      key: 'income',
      name: 'Income',
      subject: { key: 'taxation', name: 'Taxation' },
      topics: [1, 2],
    })
    expectCompleteHead(ch)
    expect(meta(ch, 'property', 'og:type')).toBe('article')
    expect(meta(ch, 'property', 'og:image')).toContain(`/og/courses/${c.slug}/${l.slug}/taxation/income`)
  })
})

describe('sitemap and robots', () => {
  it('lists only public paths, no private ones, each once', () => {
    const xml = buildSitemapXml(['/courses/ca/foundation/x'], '2026-10-06')
    const locs = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]!)
    expect(new Set(locs).size).toBe(locs.length)
    expect(locs.every((u) => /^https?:\/\/[^/]+\//.test(u))).toBe(true)
    expect(locs.some((u) => /\/(app|auth|login|signup|design-system)(\/|$)/.test(u))).toBe(false)
    expect(xml).toContain('<lastmod>2026-10-06</lastmod>')
    for (const p of publicPaths()) expect(locs.some((u) => u.endsWith(p === '/' ? '/' : p))).toBe(true)
  })

  it('robots.txt blocks private paths, never blocks link unfurlers or /og, and names the sitemap', () => {
    const txt = buildRobotsTxt()
    expect(txt).toContain('Disallow: /app')
    expect(txt).toContain('Disallow: /auth/')
    expect(txt).toContain('Disallow: /unsubscribe')
    expect(txt).not.toMatch(/Disallow:\s*\/\s*$/m)
    expect(txt).not.toContain('Disallow: /og')
    for (const bot of ['WhatsApp', 'facebookexternalhit', 'Twitterbot']) expect(txt).toContain(`User-agent: ${bot}`)
    expect(txt).toMatch(/Sitemap: https?:\/\/[^/]+\/sitemap\.xml/)
  })
})

describe('route coverage: a new route cannot forget its head', () => {
  const routesDir = join(__dirname, '..', '..', 'routes')
  const SERVER_ONLY = /^(__root|og\.|robots|sitemap)/
  const files = readdirSync(routesDir).filter((f) => f.endsWith('.tsx') && !SERVER_ONLY.test(f))
  const read = (f: string) => readFileSync(join(routesDir, f), 'utf8')

  it('finds the route files', () => {
    expect(files.length).toBeGreaterThan(20)
  })

  it('every route declares head with buildHead or a page/section head helper', () => {
    for (const f of files) {
      const src = read(f)
      if (!/\bcreateFileRoute\(/.test(src)) continue // layout wrappers without a path
      if (/^app\.tsx$/.test(f)) continue // pathless-style layout: its children declare their heads
      expect(src, `${f} has no head`).toMatch(/\bhead:/)
      expect(src, `${f} head does not use the seo module`).toMatch(
        /\b(buildHead|pageHead|featureHead|courseHead|levelHead|subjectHead|chapterHead)\(/,
      )
    }
  })

  it('every private route under /app is noindex', () => {
    for (const f of files.filter((n) => n.startsWith('app.') && n !== 'app.tsx')) {
      expect(read(f), `${f} must be noindex`).toMatch(/noindex: true/)
    }
  })

  it('every static (parameter-free) route outside /app has its copy in STATIC_PAGES', () => {
    for (const f of files) {
      const path = read(f).match(/createFileRoute\('([^']+)'\)/)?.[1]
      if (!path || path.includes('$') || path.startsWith('/app')) continue
      const key = path.length > 1 ? path.replace(/\/$/, '') : path
      expect(Object.keys(STATIC_PAGES), `${f} (${key}) is missing from STATIC_PAGES`).toContain(key)
    }
  })

  it('every STATIC_PAGES entry has a route', () => {
    const declared = files.map((f) =>
      read(f)
        .match(/createFileRoute\('([^']+)'\)/)?.[1]
        ?.replace(/(.)\/$/, '$1'),
    )
    for (const key of Object.keys(STATIC_PAGES)) expect(declared, key).toContain(key)
  })
})
