import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  matches: [] as Array<{ staticData: { chrome?: 'bare' | 'app'; footer?: boolean } }>,
}))
vi.mock('@tanstack/react-router', () => ({
  useMatches: ({ select }: { select: (m: typeof state.matches) => unknown }) => select(state.matches),
}))
const auth = vi.hoisted(() => ({ user: null as null | { id: string }, loading: false }))
vi.mock('~/modules/auth', () => ({ useAuth: () => auth }))
vi.mock('./AppShell', () => ({
  AppShell: ({ children }: { children: unknown }) => <div>app frame {children as never}</div>,
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

  it('draws neither header nor footer inside the signed-in app frame, which brings its own', () => {
    state.matches = [{ staticData: { chrome: 'app' } }, { staticData: {} }]
    render(<SiteShell>workspace</SiteShell>)
    expect(screen.getByText('workspace')).toBeInTheDocument()
    expect(screen.queryByText('site header')).toBeNull()
    expect(screen.queryByText('site footer')).toBeNull()
    expect(screen.queryByRole('main')).toBeNull()
  })

  it('gives a signed-in student the app frame on a static public page, and a visitor the public chrome', async () => {
    state.matches = [{ staticData: { footer: true } }]
    auth.user = { id: 'u1' }
    render(<SiteShell>features</SiteShell>)
    expect(await screen.findByText(/app frame/)).toBeInTheDocument()
    expect(screen.queryByText('site header')).toBeNull()
    auth.user = null
  })

  it('keeps the public chrome for a signed-in student on a page that is not a static public page', () => {
    state.matches = [{ staticData: {} }]
    auth.user = { id: 'u1' }
    render(<SiteShell>login</SiteShell>)
    expect(screen.getByText('site header')).toBeInTheDocument()
    auth.user = null
  })
})
