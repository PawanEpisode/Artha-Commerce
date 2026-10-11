import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'

import type { CardChanges, RecallCardDetail, UpdateHistoryRow } from '../lib/schemas'
import { expectNoA11yViolations, renderWithQuery } from '../test-utils'
import { AttestationSection } from './AttestationSection'
import { CardChangesSection } from './CardChangesSection'
import { QuestionCardButton } from './QuestionCardButton'
import { UpdateHistorySection } from './UpdateHistorySection'

const h = vi.hoisted(() => ({
  online: true,
  enabled: true,
  track: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  api: {
    attest: vi.fn(),
    cardChanges: vi.fn(),
    updateHistory: vi.fn(),
    cardFromQuestion: vi.fn(),
  },
}))

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)
vi.mock('~/modules/observability', () => ({ track: h.track, useFeatureFlag: () => true }))
vi.mock('@artha/design-system', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  toast: h.toast,
}))
vi.mock('../hooks/useRecallBasics', () => ({
  useRecallEnabled: () => h.enabled,
  useOnlineStatus: () => h.online,
  useRecallUser: () => 'u1',
}))
vi.mock('../hooks/useCardScreens', () => ({ useRefresh: () => vi.fn() }))
vi.mock('../lib/api', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  recallApi: h.api,
}))

const card = (att: Partial<RecallCardDetail['attestation']> = {}): RecallCardDetail =>
  ({
    id: 'c1',
    attestation: { required: true, attested: false, attested_at: null, ...att },
  }) as unknown as RecallCardDetail

beforeEach(() => {
  vi.clearAllMocks()
  h.online = true
  h.enabled = true
})

describe('the own-words statement on the card page', () => {
  it('shows nothing for a card it does not apply to', () => {
    const { container } = renderWithQuery(<AttestationSection card={card({ required: false })} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('saves the statement, says so, and sends only a flag to analytics', async () => {
    h.api.attest.mockResolvedValue({
      card_id: 'c1',
      changed: true,
      required: true,
      attested: true,
      attested_at: '2026-10-11T08:00:00Z',
      shareable: true,
    })
    const user = userEvent.setup()
    const { container } = renderWithQuery(<AttestationSection card={card()} />)
    await user.click(screen.getByRole('button', { name: 'Yes, these are my own words' }))
    await waitFor(() => expect(h.api.attest).toHaveBeenCalledWith('c1', true))
    await waitFor(() => expect(h.toast.success).toHaveBeenCalledWith('Saved. This card can be shared.'))
    expect(h.track).toHaveBeenCalledWith('recall_own_words_set', { attested: true })
    await expectNoA11yViolations(container)
  })

  it('takes it back from the attested state', async () => {
    h.api.attest.mockResolvedValue({
      card_id: 'c1',
      changed: true,
      required: true,
      attested: false,
      attested_at: null,
      shareable: false,
    })
    const user = userEvent.setup()
    renderWithQuery(<AttestationSection card={card({ attested: true })} />)
    await user.click(screen.getByRole('button', { name: 'Take that back' }))
    await waitFor(() => expect(h.api.attest).toHaveBeenCalledWith('c1', false))
    await waitFor(() => expect(h.toast.success).toHaveBeenCalledWith('Taken back. This card is private.'))
  })

  it('shows a failure in words and keeps the button usable', async () => {
    h.api.attest.mockRejectedValue(new ApiError(500, 'server_error', 'x'))
    const user = userEvent.setup()
    renderWithQuery(<AttestationSection card={card()} />)
    await user.click(screen.getByRole('button', { name: 'Yes, these are my own words' }))
    expect(await screen.findByText(/could not save that|something went wrong/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Yes, these are my own words' })).toBeEnabled()
  })

  it('cannot be changed offline', () => {
    h.online = false
    renderWithQuery(<AttestationSection card={card()} />)
    expect(screen.getByRole('button', { name: 'Yes, these are my own words' })).toBeDisabled()
  })
})

describe('what changed in a card', () => {
  const changes: CardChanges = {
    card_id: 'c1',
    item_id: 'i1',
    platform: true,
    waiting: 0,
    versions: [
      {
        version_no: 2,
        change_kind: 'typo',
        change_note: '',
        at: null,
        text: 'Text two',
        received: true,
        current: true,
      },
    ],
    resets: [],
  }

  it('reads nothing until she opens it, then shows the versions', async () => {
    h.api.cardChanges.mockResolvedValue(changes)
    const user = userEvent.setup()
    const { container } = renderWithQuery(<CardChangesSection cardId="c1" />)
    expect(h.api.cardChanges).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Versions of this card' }))
    expect(await screen.findByText('Text two')).toBeInTheDocument()
    expect(h.api.cardChanges).toHaveBeenCalledWith('c1')
    expect(h.track).toHaveBeenCalledWith('recall_card_changes_viewed', { versions: 1, waiting: 0 })
    await expectNoA11yViolations(container)
  })

  it('offers a retry when the read fails', async () => {
    h.api.cardChanges.mockRejectedValueOnce(new ApiError(500, 'server_error', 'x')).mockResolvedValue(changes)
    const user = userEvent.setup()
    renderWithQuery(<CardChangesSection cardId="c1" />)
    await user.click(screen.getByRole('button', { name: 'Versions of this card' }))
    await user.click(await screen.findByRole('button', { name: /try again/i }))
    expect(await screen.findByText('Text two')).toBeInTheDocument()
  })
})

describe('past updates of a deck', () => {
  const rows: UpdateHistoryRow[] = [
    {
      id: 'u1',
      from_version_no: 1,
      to_version_no: 2,
      versions_skipped: 0,
      trigger: 'auto',
      applied_at: '2026-10-11T08:00:00Z',
      counts: { rechecked: 1 },
      changelog_md: '',
    },
  ]

  it('reads only when opened and lists the updates', async () => {
    h.api.updateHistory.mockResolvedValue(rows)
    const user = userEvent.setup()
    const { container } = renderWithQuery(<UpdateHistorySection subscriptionId="s1" />)
    expect(h.api.updateHistory).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Show what past updates did' }))
    expect(await screen.findByText('Applied for you')).toBeInTheDocument()
    expect(h.api.updateHistory).toHaveBeenCalledWith('s1')
    expect(h.track).toHaveBeenCalledWith('recall_update_history_viewed', { updates: 1 })
    await expectNoA11yViolations(container)
  })

  it('says so when there are no updates yet', async () => {
    h.api.updateHistory.mockResolvedValue([])
    const user = userEvent.setup()
    renderWithQuery(<UpdateHistorySection subscriptionId="s1" />)
    await user.click(screen.getByRole('button', { name: 'Show what past updates did' }))
    expect(await screen.findByText(/No updates yet/)).toBeInTheDocument()
  })
})

describe('the make-a-card-from-a-question button', () => {
  const made = (existing: boolean) => ({
    item_id: 'i',
    kind: 'pointer',
    existing,
    cards: [],
    card_id: 'c9',
    undo_token: existing ? null : 't',
    undo_seconds: 10,
  })

  it('is hidden while recall is off', () => {
    h.enabled = false
    const { container } = renderWithQuery(<QuestionCardButton questionId="q" versionId="v" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('makes the card with one client id and links to it', async () => {
    h.api.cardFromQuestion.mockResolvedValue(made(false))
    const onMade = vi.fn()
    const user = userEvent.setup()
    const { container } = renderWithQuery(<QuestionCardButton questionId="q1" versionId="v1" onMade={onMade} />)
    await user.click(screen.getByRole('button', { name: 'Make a card from this' }))
    expect(await screen.findByText('Card made.')).toBeInTheDocument()
    const body = h.api.cardFromQuestion.mock.calls[0]?.[0] as {
      question_id: string
      version_id: string
      client_id: string
    }
    expect(body.question_id).toBe('q1')
    expect(body.version_id).toBe('v1')
    expect(body.client_id).toMatch(/^[0-9a-f-]{36}$/)
    expect(onMade).toHaveBeenCalledWith('c9', false)
    expect(h.track).toHaveBeenCalledWith('recall_question_card_made', { existing: false })
    await expectNoA11yViolations(container)
  })

  it('says when the card was already there', async () => {
    h.api.cardFromQuestion.mockResolvedValue(made(true))
    const user = userEvent.setup()
    renderWithQuery(<QuestionCardButton questionId="q1" versionId="v1" />)
    await user.click(screen.getByRole('button', { name: 'Make a card from this' }))
    expect(await screen.findByText('You already have a card for this question.')).toBeInTheDocument()
  })

  it('tells her kindly when it fails, and she can try again', async () => {
    h.api.cardFromQuestion.mockRejectedValue(new ApiError(503, 'question_source_unavailable', 'x'))
    const user = userEvent.setup()
    renderWithQuery(<QuestionCardButton questionId="q1" versionId="v1" />)
    await user.click(screen.getByRole('button', { name: 'Make a card from this' }))
    await waitFor(() => expect(h.toast.error).toHaveBeenCalled())
    expect(screen.getByRole('button', { name: 'Make a card from this' })).toBeEnabled()
  })

  it('needs the internet', () => {
    h.online = false
    renderWithQuery(<QuestionCardButton questionId="q1" versionId="v1" />)
    expect(screen.getByRole('button', { name: 'Make a card from this' })).toBeDisabled()
    expect(screen.getByText('This needs the internet.')).toBeInTheDocument()
  })
})
