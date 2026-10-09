import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'

import { apiCard } from '../lib/testing'
import { expectNoA11yViolations, renderWithQuery, setOnline } from '../test-utils'
import { CardDetailContainer } from './CardDetailContainer'
import { CardsContainer } from './CardsContainer'
import { NewCardContainer } from './NewCardContainer'

const h = vi.hoisted(() => ({
  navigate: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
  api: {
    cards: vi.fn(),
    card: vi.fn(),
    cardHistory: vi.fn(),
    createCard: vi.fn(),
    patchCard: vi.fn(),
    deleteCard: vi.fn(),
    undoDelete: vi.fn(),
    setCardState: vi.fn(),
    bulkCards: vi.fn(),
  },
}))

vi.mock('@tanstack/react-router', async () => ({
  ...(await import('~/test/router-stub')).routerStub,
  useNavigate: () => h.navigate,
}))
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
vi.mock('@artha/design-system', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  toast: Object.assign((...a: unknown[]) => h.toast.info(...a), h.toast),
}))
vi.mock('~/lib/richtext', () => ({
  RichText: ({ markdown }: { markdown: string }) => <div data-testid="rt">{markdown}</div>,
}))

const apiError = (status: number, code: string, details?: unknown) =>
  new ApiError(status, 'x', { error: { code, message: 'm', details } })

const row = (i: number, over: Record<string, unknown> = {}) => ({
  ...apiCard(i),
  fields: { prompt_md: `Question ${i}?`, answer_md: `Answer ${i}` },
  tags: [],
  deck_ids: [],
  status: 'active',
  state_name: 'new',
  ...over,
})
const detail = (over: Record<string, unknown> = {}) => ({
  ...row(1),
  id: 'c1',
  rev: 3,
  kind: 'pointer',
  front_md: 'Question 1?',
  importance: 'bullet',
  memory: {
    stability: 12.4,
    difficulty: 5.2,
    due_scheduled_at: null,
    postponed_until: null,
    due_at: '2026-10-20T04:00:00Z',
    last_review_at: '2026-10-09T04:00:00Z',
    reps: 4,
    lapses: 1,
    step: null,
  },
  ...over,
})

beforeEach(() => {
  vi.clearAllMocks()
  window.localStorage.clear()
  setOnline(true)
  h.api.cards.mockResolvedValue({ items: [], next_cursor: null, server_time: '2026-10-09T05:00:00Z' })
  h.api.cardHistory.mockResolvedValue({ items: [] })
})

describe('the cards browser', () => {
  it('sends the URL’s filters to the API and shows them as removable chips', async () => {
    const user = userEvent.setup()
    h.api.cards.mockResolvedValue({ items: [row(1), row(2)], next_cursor: null, server_time: '2026-10-09T05:00:00Z' })
    const { container } = renderWithQuery(<CardsContainer search={{ kind: 'cloze', tier: 'mandatory', q: 'gst' }} />)
    expect(within(await screen.findByRole('list', { name: 'Cards' })).getAllByRole('listitem')).toHaveLength(2)
    expect(h.api.cards).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'cloze', tier: 'mandatory', q: 'gst', limit: 50 }),
    )
    await user.click(screen.getByRole('button', { name: 'Remove filter: Fill in the blank' }))
    expect(h.navigate).toHaveBeenCalledWith(
      expect.objectContaining({
        to: '/app/recall/cards',
        search: expect.objectContaining({ kind: undefined, tier: 'mandatory' }),
      }),
    )
    await expectNoA11yViolations(container)
  })

  it('says what to do when there are no cards, and when a filter hides them all', async () => {
    const { unmount } = renderWithQuery(<CardsContainer search={{}} />)
    expect(await screen.findByText('You have no cards yet')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Make your first card' })).toHaveAttribute('href', '/app/recall/cards/new')
    unmount()
    renderWithQuery(<CardsContainer search={{ kind: 'formula' }} />)
    expect(await screen.findByText('No cards match')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Clear filters' })).toBeInTheDocument()
  })

  it('loads the next page with the cursor', async () => {
    const user = userEvent.setup()
    h.api.cards
      .mockResolvedValueOnce({ items: [row(1)], next_cursor: 'cur1', server_time: '2026-10-09T05:00:00Z' })
      .mockResolvedValueOnce({ items: [row(2)], next_cursor: null, server_time: '2026-10-09T05:00:00Z' })
    renderWithQuery(<CardsContainer search={{}} />)
    await user.click(await screen.findByRole('button', { name: 'Show more cards' }))
    expect(within(await screen.findByRole('list', { name: 'Cards' })).getAllByRole('listitem')).toHaveLength(2)
    expect(h.api.cards).toHaveBeenLastCalledWith(expect.objectContaining({ cursor: 'cur1' }))
  })

  it('selects cards, and deletes them only after a confirmation', async () => {
    const user = userEvent.setup()
    h.api.cards.mockResolvedValue({
      items: [row(1), row(2), row(3)],
      next_cursor: null,
      server_time: '2026-10-09T05:00:00Z',
    })
    h.api.bulkCards.mockResolvedValue({ count: 2 })
    renderWithQuery(<CardsContainer search={{}} />)
    const boxes = await screen.findAllByRole('checkbox')
    await user.click(boxes[0]!)
    await user.click(boxes[2]!)
    expect(screen.getByRole('status', { name: '' })).toHaveTextContent('2 selected')
    await user.click(screen.getByRole('button', { name: 'Delete' }))
    expect(h.api.bulkCards).not.toHaveBeenCalled()
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Delete 2 cards?')).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Delete' }))
    await waitFor(() =>
      expect(h.api.bulkCards).toHaveBeenCalledWith([expect.any(String), expect.any(String)], 'delete', undefined),
    )
    expect(h.toast.success).toHaveBeenCalledWith('Deleted 2 cards')
  })

  it('offers a retry when the list cannot load', async () => {
    h.api.cards.mockRejectedValue(apiError(500, 'server'))
    renderWithQuery(<CardsContainer search={{}} />)
    expect(await screen.findByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})

describe('making a card', () => {
  it('names each missing field before sending anything, and keeps the form accessible', async () => {
    const user = userEvent.setup()
    const { container } = renderWithQuery(<NewCardContainer search={{}} />)
    await user.click(screen.getByRole('button', { name: 'Save card' }))
    expect(await screen.findByText('Question is needed.')).toBeInTheDocument()
    expect(screen.getByText('Answer is needed.')).toBeInTheDocument()
    expect(h.api.createCard).not.toHaveBeenCalled()
    expect(screen.getByLabelText(/Question/)).toHaveAttribute('aria-invalid', 'true')
    await expectNoA11yViolations(container)
  })

  it('shows a counter and a live preview as the student types', async () => {
    const user = userEvent.setup()
    renderWithQuery(<NewCardContainer search={{}} />)
    await user.type(screen.getByLabelText(/Question/), 'What is GST?')
    expect(screen.getAllByText('12 of 4000 characters').length).toBeGreaterThan(0)
    expect(screen.getAllByTestId('rt').some((n) => n.textContent === 'What is GST?')).toBe(true)
  })

  it('sends a valid card once with its own id, then offers to make another', async () => {
    const user = userEvent.setup()
    h.api.createCard.mockResolvedValue({ item_id: 'i1', kind: 'pointer', existing: false, cards: [detail()] })
    renderWithQuery(<NewCardContainer search={{ chapter: '11111111-1111-4111-8111-111111111111' }} />)
    await user.type(screen.getByLabelText(/Question/), 'What is GST?')
    await user.type(screen.getByLabelText(/Answer/), 'A tax on supply.')
    await user.click(screen.getByRole('button', { name: 'Save card' }))
    expect(await screen.findByRole('heading', { name: 'Card made' })).toBeInTheDocument()
    expect(h.api.createCard).toHaveBeenCalledTimes(1)
    expect(h.api.createCard.mock.calls[0]![0]).toMatchObject({
      kind: 'pointer',
      fields: { prompt_md: 'What is GST?', answer_md: 'A tax on supply.' },
      chapter_id: '11111111-1111-4111-8111-111111111111',
      force: false,
      client_id: expect.stringMatching(/^[0-9a-f-]{36}$/),
    })
    expect(screen.getByRole('link', { name: 'Open the card' })).toHaveAttribute('href', '/app/recall/cards/c1')
  })

  it('warns about a duplicate and keeps both only when asked', async () => {
    const user = userEvent.setup()
    h.api.createCard
      .mockRejectedValueOnce(apiError(409, 'duplicate_card', { card_id: 'old', item_id: 'i' }))
      .mockResolvedValueOnce({ item_id: 'i2', kind: 'pointer', existing: false, cards: [detail({ id: 'c2' })] })
    renderWithQuery(<NewCardContainer search={{}} />)
    await user.type(screen.getByLabelText(/Question/), 'Q')
    await user.type(screen.getByLabelText(/Answer/), 'A')
    await user.click(screen.getByRole('button', { name: 'Save card' }))
    expect(await screen.findByText('You already have a card with this text.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open it' })).toHaveAttribute('href', '/app/recall/cards/old')
    await user.click(screen.getByRole('button', { name: 'Keep both' }))
    expect(await screen.findByRole('heading', { name: 'Card made' })).toBeInTheDocument()
    expect(h.api.createCard.mock.calls[1]![0]).toMatchObject({
      force: true,
      client_id: h.api.createCard.mock.calls[0]![0].client_id,
    })
  })

  it('shows the server’s own field problems', async () => {
    const user = userEvent.setup()
    h.api.createCard.mockRejectedValue(
      apiError(422, 'invalid_fields', {
        errors: [{ field: 'prompt_md', code: 'math', message: 'The formula in Question is not valid.' }],
      }),
    )
    renderWithQuery(<NewCardContainer search={{}} />)
    await user.type(screen.getByLabelText(/Question/), 'Q')
    await user.type(screen.getByLabelText(/Answer/), 'A')
    await user.click(screen.getByRole('button', { name: 'Save card' }))
    expect(await screen.findByText('The formula in Question is not valid.')).toBeInTheDocument()
  })

  it('tells the student when the plan limit is reached', async () => {
    const user = userEvent.setup()
    h.api.createCard.mockRejectedValue(apiError(429, 'quota_exceeded'))
    renderWithQuery(<NewCardContainer search={{}} />)
    await user.type(screen.getByLabelText(/Question/), 'Q')
    await user.type(screen.getByLabelText(/Answer/), 'A')
    await user.click(screen.getByRole('button', { name: 'Save card' }))
    expect(await screen.findByText('m')).toBeInTheDocument()
  })

  it('keeps the card on the device when offline and sends it, once, when back online', async () => {
    const user = userEvent.setup()
    setOnline(false)
    renderWithQuery(<NewCardContainer search={{}} />)
    expect(screen.getByText(/You are offline/)).toBeInTheDocument()
    await user.type(screen.getByLabelText(/Question/), 'Q')
    await user.type(screen.getByLabelText(/Answer/), 'A')
    await user.click(screen.getByRole('button', { name: 'Save card' }))
    expect(await screen.findByRole('heading', { name: 'Saved on this device' })).toBeInTheDocument()
    expect(h.api.createCard).not.toHaveBeenCalled()
    h.api.createCard.mockResolvedValue({ item_id: 'i1', kind: 'pointer', existing: false, cards: [detail()] })
    setOnline(true)
    await waitFor(() => expect(h.api.createCard).toHaveBeenCalledTimes(1))
    expect(h.api.createCard.mock.calls[0]![0]).toMatchObject({ fields: { prompt_md: 'Q', answer_md: 'A' } })
    await waitFor(() =>
      expect(JSON.parse(window.localStorage.getItem('artha.recall.cardQueue.v1.u1') ?? '[]')).toEqual([]),
    )
  })

  it('falls back to the device queue when the network drops mid save', async () => {
    const user = userEvent.setup()
    h.api.createCard.mockRejectedValue(new TypeError('Failed to fetch'))
    renderWithQuery(<NewCardContainer search={{}} />)
    await user.type(screen.getByLabelText(/Question/), 'Q')
    await user.type(screen.getByLabelText(/Answer/), 'A')
    await user.click(screen.getByRole('button', { name: 'Save card' }))
    expect(await screen.findByRole('heading', { name: 'Saved on this device' })).toBeInTheDocument()
  })

  it('prefills from a selection and suggests the kind', async () => {
    renderWithQuery(
      <NewCardContainer search={{ from: 'selection', draft: 'Section 80C allows a deduction of Rs 1.5 lakh.' }} />,
    )
    expect(screen.getByText(/Made from the text you selected/)).toBeInTheDocument()
    expect(screen.getByLabelText(/In short/)).toHaveValue('Section 80C allows a deduction of Rs 1.5 lakh.')
  })

  it('checks fill in the blank text', async () => {
    const user = userEvent.setup()
    renderWithQuery(<NewCardContainer search={{ kind: 'cloze' }} />)
    await user.type(screen.getByLabelText(/Text/), 'No blanks here')
    await user.click(screen.getByRole('button', { name: 'Save card' }))
    expect(await screen.findByText('Add at least one {{c1::...}} deletion.')).toBeInTheDocument()
  })
})

describe('a card’s page', () => {
  it('shows memory and history, and saves an edit against the revision she started from', async () => {
    const user = userEvent.setup()
    h.api.card.mockResolvedValue(detail())
    h.api.cardHistory.mockResolvedValue({
      items: [
        {
          id: 'r1',
          rating: 3,
          reviewed_at: '2026-10-09T04:00:00Z',
          mode: 'normal',
          duration_ms: 3000,
          scheduled_days: 12,
          retrievability_before: 0.9,
        },
      ],
    })
    h.api.patchCard.mockResolvedValue(detail({ rev: 4, fields: { prompt_md: 'New question?', answer_md: 'Answer 1' } }))
    const { container } = renderWithQuery(<CardDetailContainer cardId="c1" />)
    expect(await screen.findByText('Likely to recall now')).toBeInTheDocument()
    expect(await screen.findByText('Good')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled()
    await user.clear(screen.getByLabelText(/Question/))
    await user.type(screen.getByLabelText(/Question/), 'New question?')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(h.api.patchCard).toHaveBeenCalledTimes(1))
    expect(h.api.patchCard).toHaveBeenCalledWith(
      'c1',
      expect.objectContaining({ base_rev: 3, fields: expect.objectContaining({ prompt_md: 'New question?' }) }),
    )
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled())
    await expectNoA11yViolations(container)
  })

  it('merges quietly when the other device changed a different part', async () => {
    const user = userEvent.setup()
    h.api.card.mockResolvedValue(detail())
    h.api.patchCard
      .mockRejectedValueOnce(
        apiError(409, 'edit_conflict', {
          server_fields: { prompt_md: 'Question 1?', answer_md: 'Their answer' },
          rev: 5,
        }),
      )
      .mockResolvedValueOnce(detail({ rev: 6 }))
    renderWithQuery(<CardDetailContainer cardId="c1" />)
    await user.clear(await screen.findByLabelText(/Question/))
    await user.type(screen.getByLabelText(/Question/), 'My question?')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(h.api.patchCard).toHaveBeenCalledTimes(2))
    expect(h.api.patchCard.mock.calls[1]![1]).toMatchObject({
      base_rev: 5,
      fields: { prompt_md: 'My question?', answer_md: 'Their answer' },
    })
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('asks which version to keep when both changed the same part, and sends the choice on the new revision', async () => {
    const user = userEvent.setup()
    h.api.card.mockResolvedValue(detail())
    h.api.patchCard
      .mockRejectedValueOnce(
        apiError(409, 'edit_conflict', {
          server_fields: { prompt_md: 'Their question?', answer_md: 'Answer 1' },
          rev: 5,
        }),
      )
      .mockResolvedValueOnce(detail({ rev: 6 }))
    renderWithQuery(<CardDetailContainer cardId="c1" />)
    await user.clear(await screen.findByLabelText(/Question/))
    await user.type(screen.getByLabelText(/Question/), 'My question?')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('This card was changed somewhere else')).toBeInTheDocument()
    const save = within(dialog).getByRole('button', { name: 'Save this version' })
    expect(save).toBeDisabled()
    await user.click(within(dialog).getByRole('radio', { name: /The other version/ }))
    await user.click(save)
    await waitFor(() => expect(h.api.patchCard).toHaveBeenCalledTimes(2))
    expect(h.api.patchCard.mock.calls[1]![1]).toMatchObject({ base_rev: 5, fields: { prompt_md: 'Their question?' } })
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('deletes with an undo that brings the card back', async () => {
    const user = userEvent.setup()
    h.api.card.mockResolvedValue(detail())
    h.api.deleteCard.mockResolvedValue({ deleted: true, card_id: 'c1', undo_token: 'tok', undo_seconds: 10 })
    h.api.undoDelete.mockResolvedValue(detail())
    renderWithQuery(<CardDetailContainer cardId="c1" />)
    await user.click(await screen.findByRole('button', { name: 'Delete' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(h.api.deleteCard).toHaveBeenCalledWith('c1'))
    const [, options] = h.toast.success.mock.calls.find((c) => c[0] === 'Card deleted')!
    expect(options.action.label).toBe('Undo')
    options.action.onClick()
    await waitFor(() => expect(h.api.undoDelete).toHaveBeenCalledWith('tok'))
    expect(h.navigate).toHaveBeenCalledWith(expect.objectContaining({ to: '/app/recall/cards' }))
  })

  it('pauses, brings back and resets memory only after confirming the reset', async () => {
    const user = userEvent.setup()
    h.api.card.mockResolvedValue(detail())
    h.api.setCardState.mockResolvedValue(detail())
    renderWithQuery(<CardDetailContainer cardId="c1" />)
    await user.click(await screen.findByRole('button', { name: 'Pause' }))
    await waitFor(() => expect(h.api.setCardState).toHaveBeenCalledWith('c1', 'suspend'))
    await user.click(screen.getByRole('button', { name: 'Reset memory' }))
    expect(h.api.setCardState).toHaveBeenCalledTimes(1)
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Reset' }))
    await waitFor(() => expect(h.api.setCardState).toHaveBeenLastCalledWith('c1', 'reset'))
  })

  it('says so for a card that is gone', async () => {
    h.api.card.mockRejectedValue(apiError(410, 'card_deleted'))
    renderWithQuery(<CardDetailContainer cardId="c1" />)
    expect(await screen.findByText('This card was deleted.')).toBeInTheDocument()
  })

  it('keeps what she typed and says so when she is offline', async () => {
    const user = userEvent.setup()
    h.api.card.mockResolvedValue(detail())
    renderWithQuery(<CardDetailContainer cardId="c1" />)
    await user.type(await screen.findByLabelText(/Question/), ' more')
    setOnline(false)
    expect(await screen.findByText(/You are offline. Connect to save/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled()
    expect(screen.getByLabelText(/Question/)).toHaveValue('Question 1? more')
  })
})
