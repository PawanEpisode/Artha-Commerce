import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({ matches: [] as Array<{ staticData: { chrome?: 'bare' } }> }))
vi.mock('@tanstack/react-router', () => ({
  useMatches: ({ select }: { select: (m: typeof state.matches) => unknown }) => select(state.matches),
}))
vi.mock('./SiteHeader', () => ({ SiteHeader: () => <header>site header</header> }))
vi.mock('./SiteFooter', () => ({ SiteFooter: () => <footer>site footer</footer> }))

import { SiteShell } from './SiteShell'

describe('SiteShell', () => {
  it('draws the header, footer and skip link around an ordinary page', () => {
    state.matches = [{ staticData: {} }]
    render(<SiteShell>page</SiteShell>)
    expect(screen.getByText('site header')).toBeInTheDocument()
    expect(screen.getByText('site footer')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Skip to content' })).toBeInTheDocument()
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
