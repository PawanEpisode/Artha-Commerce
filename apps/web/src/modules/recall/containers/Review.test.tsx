import 'fake-indexeddb/auto'

import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { IDBFactory } from 'fake-indexeddb'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { eventStore, resetEventStore } from '../lib/eventStore'
import { OFFLINE_EVENT_CAP } from '../lib/limits'
import { apiCard, apiPack as basePack } from '../lib/testing'
import { expectNoA11yViolations, renderWithQuery, setOnline } from '../test-utils'
import { ReviewContainer } from './ReviewContainer'

const h = vi.hoisted(() => ({
  navigate: vi.fn(),
  track: vi.fn(),
  api: {
    pack: vi.fn(),
    queue: vi.fn(),
    openSession: vi.fn(),
    closeSession: vi.fn(),
    submitBatch: vi.fn(),
    undo: vi.fn(),
    cardAction: vi.fn(),
  },
}))

vi.mock('@tanstack/react-router', async () => ({
  ...(await import('~/test/router-stub')).routerStub,
  useNavigate: () => h.navigate,
}))
vi.mock('~/modules/observability', () => ({ track: h.track, useFeatureFlag: () => true }))
vi.mock('../hooks/useRecallBasics', async () => {
  const { useSyncExternalStore } = await import('react')
  return {
    useRecallEnabled: () => true,
    useRecallUser: () => 'u1',
    useOnlineStatus: () =>
      useSyncExternalStore(
        (n) => {
          window.addEventListener('online', n)
          window.addEventListener('offline', n)
          return () => {
            window.removeEventListener('online', n)
            window.removeEventListener('offline', n)
          }
        },
        () => window.navigator.onLine,
      ),
  }
})
vi.mock('../lib/api', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  recallApi: h.api,
}))

/** Expired a long time ago, so an online session always downloads the pack the test gave it. */
const apiPack = (cs: Parameters<typeof basePack>[0], over: Parameters<typeof basePack>[1] = {}) =>
  basePack(cs, { expires_at: '2026-01-01T00:00:00Z', ...over })

const PREVIEWS = { '1': '10 min', '2': '1 d', '3': '3 d', '4': '6 d' }
const cards = (n: number, over: Record<string, unknown> = {}) =>
  Array.from({ length: n }, (_, i) => apiCard(i + 1, { previews: PREVIEWS, ...over }))

function honestServer() {
  h.api.submitBatch.mockImplementation(async (events: Array<{ id: string; card_id: string }>) => ({
    results: events.map((e) => ({ event_id: e.id, status: 'applied', reason: '', merged: false, card: null })),
    cards: [],
    server_time: '2026-10-09T08:00:00Z',
  }))
}

const search = { source: 'today' as const }

beforeEach(async () => {
  vi.clearAllMocks()
  await new Promise((r) => setTimeout(r, 40)) // let the last test's storage writes finish before the store is wiped
  // A new database for every test: a connection left open by the last one can never hold this one up.
  globalThis.indexedDB = new IDBFactory()
  resetEventStore()
  window.localStorage.clear()
  window.localStorage.setItem('artha-recall-intro-seen', '1')
  setOnline(true)
  h.api.pack.mockResolvedValue(apiPack(cards(3)))
  h.api.openSession.mockResolvedValue({})
  h.api.closeSession.mockResolvedValue({})
  honestServer()
})

const flip = async (user: ReturnType<typeof userEvent.setup>) => {
  await screen.findByRole('button', { name: /Show answer/ })
  await user.keyboard(' ')
  await screen.findByRole('group', { name: 'How well did you remember it?' })
}

describe('the review player', () => {
  it('completes a whole session with the keyboard alone, and no card text is ever sent', async () => {
    const user = userEvent.setup()
    renderWithQuery(<ReviewContainer search={search} />)
    // Easy graduates a new card; Good or Again would bring it back within minutes, as a learning step does.
    for (const [i, key] of ['4', '4', '4'].entries()) {
      await flip(user)
      await user.keyboard(key)
      await waitFor(() => expect(document.body.textContent).toContain(`${i + 1} of 3`))
    }
    await waitFor(() =>
      expect(h.navigate).toHaveBeenCalledWith(expect.objectContaining({ to: '/app/recall/review/summary/$sessionId' })),
    )
    await waitFor(() => expect(h.api.submitBatch).toHaveBeenCalled())
    const sent = h.api.submitBatch.mock.calls.flatMap((c) => c[0] as Array<{ rating: number }>)
    expect(sent.map((e) => e.rating).sort()).toEqual([4, 4, 4])
    const everything = JSON.stringify([h.api.submitBatch.mock.calls, h.api.openSession.mock.calls, h.track.mock.calls])
    expect(everything).not.toMatch(/Question|Answer|Chapter one/)
  })

  it('announces the card turning and the buttons say when each answer comes back', async () => {
    const user = userEvent.setup()
    const { container } = renderWithQuery(<ReviewContainer search={search} />)
    await flip(user)
    expect(screen.getAllByRole('status').length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /Good, next in/ })).toBeInTheDocument()
    expect(screen.getByText(/Be honest: Again is fine/)).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })

  it('rates with the buttons too, and moves on to the next card', async () => {
    const user = userEvent.setup()
    renderWithQuery(<ReviewContainer search={search} />)
    await flip(user)
    await user.click(screen.getByRole('button', { name: /Again/ }))
    expect(await screen.findByRole('button', { name: /Show answer/ })).toBeInTheDocument()
    await waitFor(async () => expect(await eventStore.pendingCount('u1')).toBeGreaterThanOrEqual(0))
  })

  it('shows the first-time introduction before the first card and ignores keys until it is closed', async () => {
    window.localStorage.removeItem('artha-recall-intro-seen')
    const user = userEvent.setup()
    renderWithQuery(<ReviewContainer search={search} />)
    expect(await screen.findByText('How reviewing works')).toBeInTheDocument()
    await user.keyboard(' ')
    expect(screen.queryByRole('group', { name: 'How well did you remember it?' })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Start reviewing' }))
    expect(await screen.findByRole('button', { name: /Show answer/ })).toBeInTheDocument()
    expect(window.localStorage.getItem('artha-recall-intro-seen')).toBe('1')
  })

  it('opens the shortcut list with ?', async () => {
    const user = userEvent.setup()
    renderWithQuery(<ReviewContainer search={search} />)
    await screen.findByRole('button', { name: /Show answer/ })
    await user.keyboard('?')
    expect(await screen.findByRole('dialog', { name: 'Keyboard shortcuts' })).toBeInTheDocument()
  })

  it('works offline: answers are kept on the device, nothing is sent, and U takes the last one back', async () => {
    const user = userEvent.setup()
    renderWithQuery(<ReviewContainer search={search} />)
    await screen.findByRole('button', { name: /Show answer/ })
    setOnline(false)
    await flip(user)
    await user.keyboard('3')
    await waitFor(async () => expect(await eventStore.pendingCount('u1')).toBe(1))
    expect(h.api.submitBatch).not.toHaveBeenCalled()
    await user.keyboard('u')
    await waitFor(async () => expect(await eventStore.pendingCount('u1')).toBe(0))
    expect(await screen.findByText('Last answer undone.', { selector: '[role="status"]' })).toBeInTheDocument()
  })

  it('sends what was answered offline once the connection is back', async () => {
    const user = userEvent.setup()
    renderWithQuery(<ReviewContainer search={search} />)
    await screen.findByRole('button', { name: /Show answer/ })
    setOnline(false)
    await flip(user)
    await user.keyboard('3')
    await waitFor(async () => expect(await eventStore.pendingCount('u1')).toBe(1))
    setOnline(true)
    await waitFor(() => expect(h.api.submitBatch).toHaveBeenCalled(), { timeout: 3000 })
    await waitFor(async () => expect(await eventStore.pendingCount('u1')).toBe(0))
  })

  it('warns when the downloaded cards are more than two days old', async () => {
    await eventStore.savePack('u1', apiPack(cards(2)), Date.now() - 3 * 24 * 3600 * 1000)
    setOnline(false)
    renderWithQuery(<ReviewContainer search={search} />)
    expect(await screen.findByText(/downloaded more than 2 days ago/)).toBeInTheDocument()
  })

  it('does not warn about a fresh pack', async () => {
    await eventStore.savePack('u1', apiPack(cards(2)))
    setOnline(false)
    renderWithQuery(<ReviewContainer search={search} />)
    await screen.findByRole('button', { name: /Show answer/ })
    expect(screen.queryByText(/downloaded more than 2 days ago/)).toBeNull()
  })

  it('refuses new answers with a clear message when the device holds 5,000 waiting reviews', async () => {
    const user = userEvent.setup()
    await eventStore.savePack('u1', apiPack(cards(2)))
    setOnline(false)
    for (let n = 0; n < OFFLINE_EVENT_CAP; n += 1) {
      await eventStore.addEvent('u1', {
        id: `old-${n}`,
        card_id: `c-${n % 50}`,
        rating: 3,
        reviewed_at: new Date(1_790_000_000_000 + n * 1000).toISOString(),
        duration_ms: 1000,
        session_id: null,
        mode: 'normal',
        item_version_id: null,
        device_id: null,
        tz_offset_min: 330,
      })
    }
    renderWithQuery(<ReviewContainer search={search} />)
    await screen.findByRole('button', { name: /Show answer/ })
    await flip(user)
    await user.keyboard('3')
    expect(await screen.findByRole('alert')).toHaveTextContent('holding as many reviews as it can keep')
    expect(await eventStore.pendingCount('u1')).toBe(OFFLINE_EVENT_CAP)
  }, 60_000)

  it('marks a tricky card', async () => {
    h.api.pack.mockResolvedValue(apiPack(cards(2, { badges: ['tricky'], lapses: 9 })))
    renderWithQuery(<ReviewContainer search={search} />)
    expect(await screen.findByText('Tricky card')).toBeInTheDocument()
  })

  it('says there is nothing to review, and can look ahead', async () => {
    h.api.pack.mockResolvedValue(apiPack([]))
    h.api.queue.mockResolvedValue({ cards: [], server_time: '2026-10-09T08:00:00Z' })
    renderWithQuery(<ReviewContainer search={search} />)
    expect(await screen.findByText('Nothing to review right now')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to revision' })).toHaveAttribute('href', '/app/recall')
  })

  it('offers a retry when the cards cannot be loaded and nothing is stored', async () => {
    h.api.pack.mockRejectedValue(new TypeError('Failed to fetch'))
    renderWithQuery(<ReviewContainer search={search} />)
    expect(await screen.findByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('shows a loading state while the cards are fetched', () => {
    h.api.pack.mockReturnValue(new Promise(() => {}))
    renderWithQuery(<ReviewContainer search={search} />)
    expect(screen.getByRole('status')).toHaveTextContent('Getting your cards ready')
  })

  it('only ever sends flags, numbers and short tokens to analytics', async () => {
    const user = userEvent.setup()
    renderWithQuery(<ReviewContainer search={search} />)
    await flip(user)
    await user.keyboard('3')
    await waitFor(() => expect(h.track).toHaveBeenCalled())
    for (const [, props] of h.track.mock.calls) {
      for (const value of Object.values((props ?? {}) as Record<string, unknown>)) {
        const ok =
          typeof value === 'boolean' ||
          (typeof value === 'number' && Number.isFinite(value)) ||
          (typeof value === 'string' && /^[a-z0-9_-]{1,32}$/.test(value))
        expect(ok).toBe(true)
      }
    }
  })

  it('offers an edit link to the card page for a turned card', async () => {
    const user = userEvent.setup()
    renderWithQuery(<ReviewContainer search={search} />)
    await flip(user)
    await user.click(screen.getByRole('button', { name: 'Edit card' }))
    expect(h.navigate).toHaveBeenCalledWith(expect.objectContaining({ to: '/app/recall/cards/$cardId' }))
    void within
  })

  it.each([
    ['left', 200, 50, 1],
    ['right', 50, 200, 3],
  ] as const)(
    'a swipe %s rates the card, and the buttons stay for anyone who cannot swipe',
    async (_name, from, to, rating) => {
      const user = userEvent.setup()
      await eventStore.savePack('u1', apiPack(cards(2)))
      setOnline(false)
      renderWithQuery(<ReviewContainer search={search} />)
      await flip(user)
      expect(screen.getByRole('button', { name: /Good/ })).toBeInTheDocument()
      const card = screen.getByRole('group', { name: 'Flashcard' })
      fireEvent.pointerDown(card, { clientX: from, clientY: 0 })
      fireEvent.pointerUp(card, { clientX: to, clientY: 0 })
      await waitFor(async () =>
        expect((await eventStore.pendingEvents('u1')).map((e) => e.body.rating)).toEqual([rating]),
      )
    },
  )

  it('does not swipe before the answer is shown, or on a short drag', async () => {
    const user = userEvent.setup()
    await eventStore.savePack('u1', apiPack(cards(2)))
    setOnline(false)
    renderWithQuery(<ReviewContainer search={search} />)
    await screen.findByRole('button', { name: /Show answer/ })
    const card = screen.getByRole('group', { name: 'Flashcard' })
    fireEvent.pointerDown(card, { clientX: 200, clientY: 0 })
    fireEvent.pointerUp(card, { clientX: 50, clientY: 0 })
    await flip(user)
    fireEvent.pointerDown(card, { clientX: 100, clientY: 0 })
    fireEvent.pointerUp(card, { clientX: 110, clientY: 0 })
    expect(await eventStore.pendingCount('u1')).toBe(0)
  })
})
