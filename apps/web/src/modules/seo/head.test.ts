import { describe, expect, it } from 'vitest'

import { resolveSiteUrl } from '~/lib/site-url'

import { buildHead, canonicalPath, composeTitle, DESCRIPTION_MAX, fit, serializeJsonLd, TITLE_MAX } from './head'

type Tag = Record<string, string | undefined>
const find = (head: ReturnType<typeof buildHead>, key: 'name' | 'property', value: string) =>
  (head.meta as Tag[]).find((m) => m[key] === value)?.content

const base = { title: 'Features', description: 'A description of the page.', path: '/features' }

describe('buildHead', () => {
  it('sets title with the brand suffix, description and a canonical link', () => {
    const head = buildHead(base)
    expect((head.meta as Tag[])[0]).toEqual({ title: 'Features | ArthaCommerce' })
    expect(find(head, 'name', 'description')).toBe('A description of the page.')
    expect(head.links).toEqual([{ rel: 'canonical', href: expect.stringMatching(/^https?:\/\/[^/]+\/features$/) }])
  })

  it('does not add the brand suffix on the home page', () => {
    const head = buildHead({ ...base, title: 'ArthaCommerce: Home', path: '/' })
    expect((head.meta as Tag[])[0]).toEqual({ title: 'ArthaCommerce: Home' })
  })

  it('emits the full Open Graph set with an absolute 1200x630 image', () => {
    const head = buildHead(base)
    expect(find(head, 'property', 'og:title')).toBe('Features | ArthaCommerce')
    expect(find(head, 'property', 'og:description')).toBe(base.description)
    expect(find(head, 'property', 'og:type')).toBe('website')
    expect(find(head, 'property', 'og:site_name')).toBe('ArthaCommerce')
    expect(find(head, 'property', 'og:locale')).toBe('en_IN')
    expect(find(head, 'property', 'og:url')).toBe((head.links[0] as { href: string }).href)
    expect(find(head, 'property', 'og:image')).toMatch(/^https?:\/\/[^/]+\/og\/default\.png$/)
    expect(find(head, 'property', 'og:image:secure_url')).toBe(find(head, 'property', 'og:image'))
    expect(find(head, 'property', 'og:image:type')).toBe('image/png')
    expect(find(head, 'property', 'og:image:width')).toBe('1200')
    expect(find(head, 'property', 'og:image:height')).toBe('630')
    expect(find(head, 'property', 'og:image:alt')).toBeTruthy()
  })

  it('emits a large-image Twitter card', () => {
    const head = buildHead(base)
    expect(find(head, 'name', 'twitter:card')).toBe('summary_large_image')
    expect(find(head, 'name', 'twitter:title')).toBe('Features | ArthaCommerce')
    expect(find(head, 'name', 'twitter:image')).toBe(find(head, 'property', 'og:image'))
  })

  it('keeps an already absolute image and a generated /og route', () => {
    expect(find(buildHead({ ...base, image: 'https://cdn.example.com/a.jpg' }), 'property', 'og:image:type')).toBe(
      'image/jpeg',
    )
    expect(find(buildHead({ ...base, image: '/og/courses/ca' }), 'property', 'og:image')).toMatch(
      /^https?:\/\/[^/]+\/og\/courses\/ca$/,
    )
  })

  it('marks private pages noindex,nofollow and public pages indexable', () => {
    expect(find(buildHead({ ...base, noindex: true }), 'name', 'robots')).toBe('noindex, nofollow')
    expect(find(buildHead(base), 'name', 'robots')).toMatch(/^index, follow/)
  })

  it('uses the page type for og:type', () => {
    expect(find(buildHead({ ...base, type: 'article' }), 'property', 'og:type')).toBe('article')
  })

  it('emits one JSON-LD script per node and escapes "<"', () => {
    const none = buildHead(base)
    expect(none.scripts).toEqual([])
    const head = buildHead({ ...base, jsonLd: [{ '@type': 'A' }, { '@type': 'B', name: '</script><b>' }] })
    expect(head.scripts).toHaveLength(2)
    expect(head.scripts[1]?.type).toBe('application/ld+json')
    expect(head.scripts[1]?.children).not.toContain('</script>')
    expect(JSON.parse(head.scripts[1]!.children).name).toBe('</script><b>')
  })

  it('drops query strings and trailing slashes from the canonical and og:url', () => {
    const head = buildHead({ ...base, path: '/features/?utm=x#y' })
    expect((head.links[0] as { href: string }).href).toMatch(/\/features$/)
  })

  it('keeps title and description within search and unfurl limits', () => {
    const head = buildHead({ ...base, title: 'Long '.repeat(30), description: 'word '.repeat(80) })
    expect((head.meta as Tag[])[0]?.title?.length).toBeLessThanOrEqual(TITLE_MAX)
    expect(find(head, 'name', 'description')!.length).toBeLessThanOrEqual(DESCRIPTION_MAX)
  })
})

describe('helpers', () => {
  it('canonicalPath', () => {
    expect(canonicalPath('/')).toBe('/')
    expect(canonicalPath('')).toBe('/')
    expect(canonicalPath('/a/b/')).toBe('/a/b')
    expect(canonicalPath('/a?x=1')).toBe('/a')
  })

  it('fit cuts at a word boundary with an ellipsis', () => {
    expect(fit('short', 20)).toBe('short')
    const out = fit('alpha beta gamma delta epsilon', 18)
    expect(out.length).toBeLessThanOrEqual(18)
    expect(out.endsWith('…')).toBe(true)
  })

  it('composeTitle shortens only the page part', () => {
    const out = composeTitle('x'.repeat(100), '/a', 'Brand')
    expect(out.endsWith(' | Brand')).toBe(true)
    expect(out.length).toBeLessThanOrEqual(TITLE_MAX)
  })

  it('serializeJsonLd escapes angle brackets', () => {
    expect(serializeJsonLd({ a: '<' })).toBe('{"a":"\\u003c"}')
  })
})

describe('resolveSiteUrl (the production incident)', () => {
  it('strips a path, query and trailing slash so og:image cannot become /login/og/default.png', () => {
    expect(resolveSiteUrl('https://arthacommerce.meetpawan.com/login', true)).toBe(
      'https://arthacommerce.meetpawan.com',
    )
    expect(resolveSiteUrl('https://arthacommerce.meetpawan.com/login/', true)).toBe(
      'https://arthacommerce.meetpawan.com',
    )
    expect(resolveSiteUrl('https://x.com/?a=1#b', true)).toBe('https://x.com')
  })

  it('falls back to the production origin when unset, blank, invalid or localhost in production', () => {
    for (const bad of [undefined, '', '   ', 'http://localhost:3000', 'ftp://x.com', 'http://']) {
      expect(resolveSiteUrl(bad, true)).toBe('https://arthacommerce.meetpawan.com')
    }
  })

  it('forces https in production, accepts a bare host, and allows localhost in development', () => {
    expect(resolveSiteUrl('http://arthacommerce.meetpawan.com', true)).toBe('https://arthacommerce.meetpawan.com')
    expect(resolveSiteUrl('arthacommerce.meetpawan.com', true)).toBe('https://arthacommerce.meetpawan.com')
    expect(resolveSiteUrl(undefined, false)).toBe('http://localhost:3000')
    expect(resolveSiteUrl('http://localhost:4000/x', false)).toBe('http://localhost:4000')
  })
})
