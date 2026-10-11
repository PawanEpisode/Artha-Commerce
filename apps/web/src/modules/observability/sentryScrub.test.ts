import type { Breadcrumb, Event } from '@sentry/react'
import { describe, expect, it } from 'vitest'

import { maskUrl, scrubBreadcrumb, scrubEvent } from './sentryScrub'

const CARD = '6f1c2a9e-3b4d-4c5e-8f60-7a8b9c0d1e2f'
const TEXT = 'my private note about section 17(5)'

describe('Sentry scrubbing for recall', () => {
  it('removes the query and the ids from a recall URL and leaves others alone', () => {
    expect(maskUrl(`/api/v1/recall/cards/${CARD}/?q=${TEXT}#x`)).toBe('/api/v1/recall/cards/{id}/')
    expect(maskUrl(`/api/v1/recall/subscriptions/${CARD}/apply-update/`)).toBe(
      '/api/v1/recall/subscriptions/{id}/apply-update/',
    )
    expect(maskUrl(`/api/v1/recall/chapter-remaps/${CARD}/choose/`)).toBe('/api/v1/recall/chapter-remaps/{id}/choose/')
    const crumb: Breadcrumb = {
      category: 'fetch',
      data: { url: `https://api.example.com/api/v1/recall/cards/${CARD}/?q=a`, status_code: 200 },
    }
    expect(scrubBreadcrumb(crumb, false)?.data?.url).toBe('https://api.example.com/api/v1/recall/cards/{id}/')
    const other: Breadcrumb = { category: 'fetch', data: { url: `https://api.example.com/api/v1/notes/${CARD}/?q=a` } }
    expect(scrubBreadcrumb(other, false)?.data?.url).toBe(`https://api.example.com/api/v1/notes/${CARD}/?q=a`)
  })

  it('masks page navigation inside the recall screens', () => {
    const crumb: Breadcrumb = {
      category: 'navigation',
      data: { from: '/app/recall', to: `/app/recall/cards/${CARD}?draft=${TEXT}` },
    }
    expect(scrubBreadcrumb(crumb, false)?.data).toEqual({ from: '/app/recall', to: '/app/recall/cards/{id}' })
  })

  it('drops console and typing breadcrumbs while a recall screen is open, keeps them elsewhere', () => {
    expect(scrubBreadcrumb({ category: 'console', message: TEXT }, true)).toBeNull()
    expect(scrubBreadcrumb({ category: 'ui.input', message: TEXT }, true)).toBeNull()
    expect(scrubBreadcrumb({ category: 'console', message: 'hi' }, false)).not.toBeNull()
    expect(scrubBreadcrumb({ category: 'ui.click', message: 'button.rate-good' }, true)).not.toBeNull()
  })

  it('sends no body, query, card id or typing from a recall event', () => {
    const event: Event = {
      transaction: `/app/recall/cards/${CARD}`,
      request: {
        url: `https://app.example.com/app/recall/cards/${CARD}?q=${TEXT}`,
        query_string: `q=${TEXT}`,
        data: { fields: TEXT },
        cookies: { a: 'b' },
        headers: { 'User-Agent': 'ua' },
      },
      breadcrumbs: [
        { category: 'console', message: TEXT },
        { category: 'fetch', data: { url: `/api/v1/recall/cards/${CARD}/` } },
      ],
    }
    const out = JSON.stringify(scrubEvent(event))
    expect(out).not.toContain(TEXT)
    expect(out).not.toContain(CARD)
    expect(out).toContain('{id}')
    expect(out).toContain('User-Agent')
  })

  it('leaves events from other screens as they are', () => {
    const event: Event = {
      request: { url: 'https://app.example.com/app/notes?x=1', data: { a: 1 } },
      breadcrumbs: [{ category: 'console', message: 'hi' }],
    }
    expect(scrubEvent(event)).toEqual({
      request: { url: 'https://app.example.com/app/notes?x=1', data: { a: 1 } },
      breadcrumbs: [{ category: 'console', message: 'hi' }],
    })
  })
})
