import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'

import type { AiConsent, AiOverview, Suggestion, SuggestionBatch } from '../lib/schemas'
import { expectNoA11yViolations, renderWithQuery } from '../test-utils'
import { SuggestionsContainer } from './SuggestionsContainer'

const h = vi.hoisted(() => ({
  flag: true,
  online: true,
  track: vi.fn(),
  api: {
    aiOverview: vi.fn(),
    aiConsent: vi.fn(),
    grantAiConsent: vi.fn(),
    withdrawAiConsent: vi.fn(),
    requestSuggestions: vi.fn(),
    suggestionBatch: vi.fn(),
    acceptSuggestion: vi.fn(),
    rejectSuggestion: vi.fn(),
  },
}))

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)
vi.mock('~/modules/observability', () => ({ track: h.track, useFeatureFlag: () => h.flag }))
vi.mock('../hooks/useRecallBasics', () => ({
  useRecallEnabled: () => true,
  useOnlineStatus: () => h.online,
  useRecallUser: () => 'u1',
}))
vi.mock('../hooks/useChapterPicker', () => ({
  useCourses: () => ({ data: [], isPending: false, isError: false }),
  useLevelSubjects: () => ({ data: [], isPending: false, isError: false }),
  useSubjectChapters: () => ({ data: [], isPending: false, isError: false }),
  useStudentPapers: () => null,
}))
vi.mock('../hooks/useCardScreens', () => ({ useRefresh: () => vi.fn() }))
vi.mock('../lib/api', async (original) => ({ ...(await original<Record<string, unknown>>()), recallApi: h.api }))

const overview = (over: Partial<AiOverview> = {}): AiOverview => ({
  available: true,
  consent: { version: 'v1', given: true, given_at: '2026-10-12T00:00:00Z' },
  quota: { batches_used: 0, batches_limit: 3, suggestions_used: 0, suggestions_limit: 30, resets_on: '2026-10-13' },
  sources: ['notes', 'pasted'],
  limits: { min_count: 1, max_count: 10, default_count: 5, max_pasted_chars: 12000, min_source_chars: 80 },
  waiting_drafts: 0,
  ...over,
})

const consent: AiConsent = {
  version: 'v1',
  title: 'Before the AI reads your material',
  points: [{ heading: 'What is sent', text: 'Only the text you choose.' }],
  consented: false,
  consented_at: null,
  available: true,
}

const draft = (over: Partial<Suggestion> = {}): Suggestion => ({
  id: 's1',
  position: 0,
  kind: 'pointer',
  fields: { prompt_md: 'What is ITC?', answer_md: 'Input tax credit' },
  front_md: 'What is ITC?',
  back_md: 'Input tax credit',
  evidence_quote: 'ITC means input tax credit.',
  evidence_label: 'your notes',
  status: 'draft',
  item_id: null,
  decided_at: null,
  ...over,
})

const batch = (over: Partial<SuggestionBatch> = {}): SuggestionBatch => ({
  id: 'b1',
  status: 'ready',
  chapter_id: 'c1',
  sources: ['notes'],
  kinds: [],
  requested_count: 5,
  produced: 1,
  dropped: 0,
  error_code: null,
  created_at: '2026-10-12T00:00:00Z',
  finished_at: null,
  expires_at: null,
  suggestions: [draft()],
  ...over,
})

const mount = (search = {}) => renderWithQuery(<SuggestionsContainer search={search} />)

beforeEach(() => {
  h.flag = true
  h.online = true
  h.track.mockReset()
  for (const f of Object.values(h.api)) f.mockReset()
  h.api.aiOverview.mockResolvedValue(overview())
})

describe('AI suggestions screen', () => {
  it('says so plainly when the flag is off, and calls nothing', async () => {
    h.flag = false
    mount()
    expect(await screen.findByText('AI suggestions are not available')).toBeInTheDocument()
    expect(h.api.aiOverview).not.toHaveBeenCalled()
  })

  it('shows the notice first and records the version she agreed to', async () => {
    const user = userEvent.setup()
    h.api.aiOverview.mockResolvedValue(overview({ consent: { version: 'v1', given: false, given_at: null } }))
    h.api.aiConsent.mockResolvedValue(consent)
    h.api.grantAiConsent.mockResolvedValue({ ...consent, consented: true })
    const { container } = mount()
    expect(await screen.findByText('Only the text you choose.')).toBeInTheDocument()
    await expectNoA11yViolations(container)
    h.api.aiOverview.mockResolvedValue(overview())
    await user.click(screen.getByRole('button', { name: 'I agree' }))
    await waitFor(() => expect(h.api.grantAiConsent).toHaveBeenCalledWith('v1'))
    expect(await screen.findByRole('button', { name: /Suggest cards/ })).toBeInTheDocument()
  })

  it('explains why the button is off until a chapter is chosen', async () => {
    const { container } = mount()
    expect(await screen.findByRole('button', { name: /Suggest cards/ })).toBeDisabled()
    expect(screen.getByText('Choose a chapter first.')).toBeInTheDocument()
    expect(screen.getByText('Today you can ask 3 more times for up to 30 suggestions.')).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })

  it('shows a batch from the link, with the quote, and adds one card on accept', async () => {
    const user = userEvent.setup()
    h.api.suggestionBatch.mockResolvedValue(batch())
    h.api.acceptSuggestion.mockResolvedValue({
      created: 1,
      card_id: 'card1',
      suggestion: draft({ status: 'accepted', item_id: 'card1' }),
    })
    const { container } = mount({ batch: 'b1' })
    expect(await screen.findByText('ITC means input tax credit.')).toBeInTheDocument()
    expect(screen.getByText(/From your notes/)).toBeInTheDocument()
    expect(screen.getByText('1 suggestion ready.')).toBeInTheDocument()
    await expectNoA11yViolations(container)

    await user.click(screen.getByRole('button', { name: 'Add as a card' }))
    await waitFor(() =>
      expect(h.api.acceptSuggestion).toHaveBeenCalledWith('s1', { fields: undefined, force: undefined }),
    )
    expect(await screen.findByText('Added to your cards')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add as a card' })).not.toBeInTheDocument()
    expect(h.track).toHaveBeenCalledWith('recall_suggestion_decided', { decision: 'accepted', edited: 0 })
  })

  it('sends her own words when she edits first', async () => {
    const user = userEvent.setup()
    h.api.suggestionBatch.mockResolvedValue(batch())
    h.api.acceptSuggestion.mockResolvedValue({
      created: 1,
      card_id: 'c',
      suggestion: draft({ status: 'edited_accepted', item_id: 'c' }),
    })
    mount({ batch: 'b1' })
    await user.click(await screen.findByRole('button', { name: 'Edit first' }))
    const answer = screen.getByLabelText('Answer')
    await user.clear(answer)
    await user.type(answer, 'Credit for tax paid on inputs')
    await user.click(screen.getByRole('button', { name: 'Save my version as a card' }))
    await waitFor(() => expect(h.api.acceptSuggestion).toHaveBeenCalled())
    expect(h.api.acceptSuggestion.mock.calls[0][1].fields).toEqual({
      prompt_md: 'What is ITC?',
      answer_md: 'Credit for tax paid on inputs',
    })
    expect(h.track).toHaveBeenCalledWith('recall_suggestion_decided', { decision: 'accepted', edited: 1 })
  })

  it('rejects a draft and keeps a failed accept on screen with a sentence', async () => {
    const user = userEvent.setup()
    h.api.suggestionBatch.mockResolvedValue(batch())
    h.api.rejectSuggestion.mockResolvedValue({ suggestion: draft({ status: 'rejected' }) })
    mount({ batch: 'b1' })
    await user.click(await screen.findByRole('button', { name: 'Not useful' }))
    expect(await screen.findByText('Not suggested again')).toBeInTheDocument()
  })

  it('shows the server problem next to the card it is about', async () => {
    const user = userEvent.setup()
    h.api.suggestionBatch.mockResolvedValue(batch())
    h.api.acceptSuggestion.mockRejectedValue(new ApiError(409, 'dup', { error: { code: 'duplicate_card' } }))
    mount({ batch: 'b1' })
    await user.click(await screen.findByRole('button', { name: 'Add as a card' }))
    expect(await screen.findByText(/already have a card with this text/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add as a card' })).toBeEnabled()
  })

  it('tells her a failed batch cost nothing', async () => {
    h.api.suggestionBatch.mockResolvedValue(
      batch({ status: 'failed', error_code: 'nothing_usable', suggestions: [], produced: 0 }),
    )
    mount({ batch: 'b1' })
    expect(await screen.findByText(/You were not charged/)).toBeInTheDocument()
  })

  it('withdraws the agreement', async () => {
    const user = userEvent.setup()
    h.api.withdrawAiConsent.mockResolvedValue({ withdrawn: true, cancelled: 0, drafts_deleted: 2 })
    mount()
    await user.click(await screen.findByRole('button', { name: 'Withdraw my agreement' }))
    await waitFor(() => expect(h.api.withdrawAiConsent).toHaveBeenCalled())
    expect(h.track).toHaveBeenCalledWith('recall_ai_consent_withdrawn', { drafts_deleted: 2 })
  })

  it('offers a way to retry when the page cannot load', async () => {
    h.api.aiOverview.mockRejectedValue(new ApiError(500, 'boom'))
    mount()
    expect(await screen.findByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
