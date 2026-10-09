import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'

import type { ApiDeck, ApiDeckItem } from '../lib/schemas'
import { expectNoA11yViolations, renderWithQuery } from '../test-utils'
import { DataControlsContainer } from './DataControlsContainer'
import { DeckDetailContainer } from './DeckDetailContainer'
import { DecksContainer } from './DecksContainer'
import { SettingsContainer } from './SettingsContainer'

const sub = (over = {}) => ({
  id: 'sub1',
  status: 'active' as const,
  version_no: 1,
  newer_versions: 0,
  subscribed_at: '2026-10-01T00:00:00Z',
  min_importance: 'bullet',
  ...over,
})

const deck = (over: Partial<ApiDeck> = {}): ApiDeck => ({
  id: 'd1',
  slug: 'gst',
  title: 'GST: input tax credit',
  description: 'The pointers you must know.',
  course_id: null,
  level_id: null,
  subject_key: 'taxation',
  subject_name: 'Taxation',
  chapter_id: null,
  chapter_name: 'GST ITC',
  version_no: 1,
  item_count: 2,
  card_count: 3,
  tiers: { mandatory: 1, important: 1, bullet: 0 },
  published_at: null,
  changelog_md: '',
  subscription: null,
  ...over,
})

const item = (i: number, over: Partial<ApiDeckItem> = {}): ApiDeckItem => ({
  item_id: `i${i}`,
  kind: 'pointer',
  importance: 'mandatory',
  position: i,
  preview: `When is ITC blocked ${i}?`,
  chapter_name: null,
  ...over,
})

type Mut = {
  mutate: ReturnType<typeof vi.fn>
  isPending: boolean
  isError: boolean
  error: unknown
  reset: () => void
  variables?: unknown
}
const mut = (over: Partial<Mut> = {}): Mut => ({
  mutate: vi.fn(),
  isPending: false,
  isError: false,
  error: null,
  reset: vi.fn(),
  ...over,
})

const h = vi.hoisted(() => ({
  enabled: true,
  library: null as unknown,
  mine: null as unknown,
  detail: null as unknown,
  subscribe: null as unknown,
  unsubscribe: null as unknown,
  resubscribe: null as unknown,
  report: null as unknown,
  exportJson: null as unknown,
  exportCsv: null as unknown,
  erase: null as unknown,
  eraseDone: undefined as undefined | (() => void),
  settings: null as unknown,
}))

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)
vi.mock('../hooks/useRecallBasics', () => ({
  useRecallEnabled: () => h.enabled,
  useOnlineStatus: () => true,
  useRecallUser: () => 'u1',
}))
vi.mock('../hooks/useDecks', () => ({
  useDeckLibrary: () => h.library,
  useMyDecks: () => h.mine,
  useDeck: () => h.detail,
  useSubscribe: () => h.subscribe,
  useUnsubscribe: () => h.unsubscribe,
  useResubscribe: () => h.resubscribe,
  useReportItem: () => h.report,
}))
vi.mock('../hooks/useDataControls', () => ({
  useExportJson: () => h.exportJson,
  useExportCsv: () => h.exportCsv,
  useEraseAll: (done: () => void) => {
    h.eraseDone = done
    return h.erase
  },
}))
vi.mock('../hooks/useSettings', () => ({
  useSettings: () => h.settings,
  useSaveSettings: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
  useSetVacation: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}))

const lib = (decks: ApiDeck[], over = {}) => ({
  isPending: false,
  isError: false,
  refetch: vi.fn(),
  hasNextPage: false,
  isFetchingNextPage: false,
  fetchNextPage: vi.fn(),
  data: { pages: [{ items: decks, next_cursor: null }] },
  ...over,
})
const query = (data: unknown, over = {}) => ({
  isPending: false,
  isError: false,
  refetch: vi.fn(),
  data,
  error: null,
  ...over,
})

/** jsdom has no layout, so the 320 px promise is checked on the classes: nothing fixed wide, long text wraps. */
function expectFits320(container: HTMLElement) {
  for (const el of container.querySelectorAll('[class]')) {
    const cls = el.getAttribute('class') ?? ''
    for (const m of cls.matchAll(/(?:^|\s)(?:min-w|w)-\[(\d+)px\]/g)) expect(Number(m[1])).toBeLessThanOrEqual(320)
  }
}

beforeEach(() => {
  h.enabled = true
  h.library = lib([deck()])
  h.mine = query([])
  h.detail = query({ deck: deck(), items: [item(1), item(2, { importance: 'important' })] })
  h.subscribe = mut()
  h.unsubscribe = mut()
  h.resubscribe = mut()
  h.report = mut()
  h.exportJson = mut()
  h.exportCsv = mut()
  h.erase = mut()
  h.settings = query(undefined, { isPending: true })
})

describe('decks library', () => {
  it('lists decks with links to their pages and passes axe', async () => {
    const { container } = renderWithQuery(<DecksContainer />)
    expect(screen.getByRole('heading', { name: 'Decks', level: 1 })).toBeInTheDocument()
    const list = screen.getByRole('list', { name: 'Deck library' })
    expect(within(list).getByRole('link', { name: 'GST: input tax credit' })).toHaveAttribute(
      'href',
      '/app/recall/decks/d1',
    )
    expect(within(list).getByText('3 cards')).toBeInTheDocument()
    expect(within(list).getByText(/1 must know, 1 important/)).toBeInTheDocument()
    await expectNoA11yViolations(container)
    expectFits320(container)
  })

  it('shows her subscribed decks first, and a newer version as a count', async () => {
    h.library = lib([deck({ subscription: sub({ newer_versions: 2 }) })])
    h.mine = query([deck({ subscription: sub({ newer_versions: 2 }) })])
    const { container } = renderWithQuery(<DecksContainer />)
    const mine = screen.getByRole('list', { name: 'Your decks' })
    expect(within(mine).getByText('Subscribed')).toBeInTheDocument()
    expect(within(mine).getByText('2 newer versions exist')).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })

  it('does not list an unsubscribed deck under "Your decks"', () => {
    h.mine = query([deck({ subscription: sub({ status: 'archived' }) })])
    renderWithQuery(<DecksContainer />)
    expect(screen.queryByRole('list', { name: 'Your decks' })).toBeNull()
  })

  it('has loading, empty, error and "show more" states', async () => {
    const user = userEvent.setup()
    h.library = lib([], { isPending: true, data: undefined })
    const { rerender } = renderWithQuery(<DecksContainer />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading decks')
    h.library = lib([])
    rerender(<DecksContainer />)
    expect(screen.getByText('No decks yet')).toBeInTheDocument()
    const retry = vi.fn()
    h.library = lib([], { isError: true, refetch: retry, data: undefined })
    rerender(<DecksContainer />)
    await user.click(screen.getByRole('button', { name: /try again/i }))
    expect(retry).toHaveBeenCalled()
    const more = vi.fn()
    h.library = lib([deck()], { hasNextPage: true, fetchNextPage: more })
    rerender(<DecksContainer />)
    await user.click(screen.getByRole('button', { name: 'Show more decks' }))
    expect(more).toHaveBeenCalled()
  })

  it('shows the unavailable page with the flag off', () => {
    h.enabled = false
    renderWithQuery(<DecksContainer />)
    expect(screen.queryByRole('heading', { name: 'Decks' })).toBeNull()
    expect(screen.getByText('Revision cards are not available yet')).toBeInTheDocument()
  })
})

describe('deck page', () => {
  it('shows the cards inside and lets her add the deck, choosing what to add', async () => {
    const user = userEvent.setup()
    const { container } = renderWithQuery(<DeckDetailContainer deckId="d1" />)
    expect(screen.getByRole('heading', { name: 'GST: input tax credit', level: 1 })).toBeInTheDocument()
    const items = screen.getByRole('list', { name: 'Cards in this deck' })
    expect(within(items).getAllByRole('listitem')).toHaveLength(2)
    await expectNoA11yViolations(container)
    expectFits320(container)
    await user.click(screen.getByRole('button', { name: 'Must know only' }))
    expect(screen.getByRole('button', { name: 'Must know only' })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: 'Add this deck to my revision' }))
    expect((h.subscribe as Mut).mutate).toHaveBeenCalledWith('mandatory', expect.any(Object))
  })

  it('lets her remove a subscribed deck and says the progress is kept', async () => {
    const user = userEvent.setup()
    h.detail = query({ deck: deck({ subscription: sub({ newer_versions: 1 }) }), items: [item(1)] })
    const { container } = renderWithQuery(<DeckDetailContainer deckId="d1" />)
    expect(screen.getByText('A newer version exists. Your cards stay as they are for now.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Remove from my revision' }))
    expect((h.unsubscribe as Mut).mutate).toHaveBeenCalledWith('sub1', expect.any(Object))
    await expectNoA11yViolations(container)
  })

  it('brings an unsubscribed deck back', async () => {
    const user = userEvent.setup()
    h.detail = query({ deck: deck({ subscription: sub({ status: 'archived' }) }), items: [item(1)] })
    renderWithQuery(<DeckDetailContainer deckId="d1" />)
    expect(screen.getByText(/cards return with the progress you had/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Bring it back' }))
    expect((h.resubscribe as Mut).mutate).toHaveBeenCalledWith('sub1', expect.any(Object))
  })

  it('explains a deck that is too large to add', () => {
    h.subscribe = mut({
      isError: true,
      error: new ApiError(422, 'x', { error: { code: 'deck_too_large', extra: { cards: 501, limit: 500 } } }),
    })
    renderWithQuery(<DeckDetailContainer deckId="d1" />)
    expect(screen.getByRole('alert')).toHaveTextContent(/501 cards and a deck can add up to 500/)
  })

  it('reports a card from a dialog', async () => {
    const user = userEvent.setup()
    const { baseElement } = renderWithQuery(<DeckDetailContainer deckId="d1" />)
    await user.click(screen.getByRole('button', { name: /Report this card: When is ITC blocked 1\?/ }))
    const dialog = await screen.findByRole('dialog', { name: 'Report this card' })
    await user.type(within(dialog).getByLabelText(/Anything else/), 'Section number is wrong')
    expect(within(dialog).getByText('23 of 500 characters')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Send report' }))
    expect((h.report as Mut).mutate).toHaveBeenCalledWith(
      { itemId: 'i1', reason: 'wrong', note: 'Section number is wrong' },
      expect.any(Object),
    )
    await expectNoA11yViolations(baseElement)
  })

  it('says so when the deck is gone, and retries other failures', async () => {
    const user = userEvent.setup()
    h.detail = query(undefined, { isError: true, error: new ApiError(404, 'x') })
    const { rerender } = renderWithQuery(<DeckDetailContainer deckId="d1" />)
    expect(screen.getByText('This deck is not available.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to decks' })).toHaveAttribute('href', '/app/recall/decks')
    const retry = vi.fn()
    h.detail = query(undefined, { isError: true, error: new ApiError(500, 'x'), refetch: retry })
    rerender(<DeckDetailContainer deckId="d1" />)
    await user.click(screen.getByRole('button', { name: /try again/i }))
    expect(retry).toHaveBeenCalled()
  })
})

describe('export and erase', () => {
  it('offers the three downloads and disables them while one runs', async () => {
    const user = userEvent.setup()
    const { container, rerender } = renderWithQuery(<DataControlsContainer />)
    expect(screen.getByRole('heading', { name: 'Your revision data' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Download everything (JSON)' }))
    expect((h.exportJson as Mut).mutate).toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Reviews (CSV)' }))
    expect((h.exportCsv as Mut).mutate).toHaveBeenCalledWith('reviews', expect.any(Object))
    await expectNoA11yViolations(container)
    expectFits320(container)
    h.exportCsv = mut({ isPending: true, variables: 'cards' })
    rerender(<DataControlsContainer />)
    expect(screen.getByRole('button', { name: 'Cards (CSV)' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Download everything (JSON)' })).toBeDisabled()
  })

  it('shows a failed download as a sentence', () => {
    h.exportCsv = mut({ isError: true, error: new ApiError(0, 'x') })
    renderWithQuery(<DataControlsContainer />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('erases only after the word is typed exactly', async () => {
    const user = userEvent.setup()
    const { baseElement } = renderWithQuery(<DataControlsContainer />)
    await user.click(screen.getByRole('button', { name: 'Erase everything' }))
    const dialog = await screen.findByRole('dialog', { name: 'Erase all your revision data?' })
    const go = within(dialog).getByRole('button', { name: 'Erase everything' })
    expect(go).toBeDisabled()
    await user.type(within(dialog).getByLabelText('Type ERASE to confirm'), 'erase')
    expect(go).toBeDisabled()
    await user.clear(within(dialog).getByLabelText('Type ERASE to confirm'))
    await user.type(within(dialog).getByLabelText('Type ERASE to confirm'), 'ERASE')
    expect(go).toBeEnabled()
    await expectNoA11yViolations(baseElement)
    await user.click(go)
    expect((h.erase as Mut).mutate).toHaveBeenCalledWith('ERASE')
    h.eraseDone?.()
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('stays reachable with the feature switched off, under the unavailable message', () => {
    h.enabled = false
    renderWithQuery(<SettingsContainer />)
    expect(screen.getByText('Revision cards are not available yet')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Your revision data' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Revision settings' })).toBeNull()
  })

  it('sits below the settings form when the feature is on', () => {
    h.settings = query(undefined, { isPending: true })
    renderWithQuery(<SettingsContainer />)
    expect(screen.getByRole('heading', { name: 'Revision settings' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Your revision data' })).toBeInTheDocument()
  })
})
