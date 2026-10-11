import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ matches: [] as Array<{ staticData: { chrome?: 'bare'; footer?: boolean } }> }))
vi.mock('@tanstack/react-router', () => ({
  useMatches: ({ select }: { select: (m: typeof state.matches) => unknown }) => select(state.matches),
}))
vi.mock('./SiteHeader', () => ({ SiteHeader: () => <header>site header</header> }))
vi.mock('./SiteFooter', () => ({ SiteFooter: () => <footer>site footer</footer> }))

import { SiteShell } from './SiteShell'

describe('SiteShell', () => {
  it('draws the header and skip link, but no footer, around an ordinary page', () => {
    state.matches = [{ staticData: {} }]
    render(<SiteShell>page</SiteShell>)
    expect(screen.getByText('site header')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Skip to content' })).toBeInTheDocument()
    expect(screen.queryByText('site footer')).toBeNull()
  })

  it('draws the footer on a static public page', () => {
    state.matches = [{ staticData: {} }, { staticData: { footer: true } }]
    render(<SiteShell>landing</SiteShell>)
    expect(screen.getByText('site footer')).toBeInTheDocument()
  })

  it('draws only the page for a bare route (the fallback timer window)', () => {
    state.matches = [{ staticData: {} }, { staticData: { chrome: 'bare' } }]
    render(<SiteShell>the timer</SiteShell>)
    expect(screen.getByRole('main')).toHaveTextContent('the timer')
    expect(screen.queryByText('site header')).toBeNull()
    expect(screen.queryByText('site footer')).toBeNull()
    expect(screen.queryByRole('link', { name: 'Skip to content' })).toBeNull()
  })
})
