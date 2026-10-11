import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '~/lib/api'

import type { ImportResult } from '../lib/schemas'
import { expectNoA11yViolations, renderWithQuery } from '../test-utils'
import { NewCardContainer } from './NewCardContainer'

const h = vi.hoisted(() => ({
  online: true,
  importCards: vi.fn(),
  track: vi.fn(),
}))

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)
vi.mock('~/modules/observability', () => ({ track: h.track, useFeatureFlag: () => true }))
vi.mock('../hooks/useRecallBasics', () => ({
  useRecallEnabled: () => true,
  useOnlineStatus: () => h.online,
  useRecallUser: () => 'u1',
}))
vi.mock('../hooks/useChapterPicker', () => ({
  useCourses: () => ({ data: [], isPending: false, isError: false }),
  useLevelSubjects: () => ({ data: [], isPending: false, isError: false }),
  useSubjectChapters: () => ({ data: [], isPending: false, isError: false }),
}))
vi.mock('../hooks/useCardScreens', () => ({
  useCreateCard: () => ({ mutate: vi.fn(), isPending: false }),
  useCardQueue: () => ({ pending: 0, queue: vi.fn() }),
  useRefresh: () => vi.fn(),
}))
vi.mock('../lib/api', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  recallApi: { importCards: h.importCards },
}))

const result = (over: Partial<ImportResult> = {}): ImportResult => ({
  dry_run: true,
  total: 3,
  valid: 2,
  invalid: 1,
  created: 0,
  existing: 0,
  quota: { room: 100, needed: 2, fits: true },
  rows: [
    { line: 1, status: 'ok', kind: 'pointer', front: 'Q1', back: 'A1', issues: [], card_id: null },
    {
      line: 2,
      status: 'error',
      kind: 'pointer',
      front: 'Only a question',
      back: '',
      issues: [{ field: 'row', code: 'missing_back', message: 'This line could not be read.' }],
      card_id: null,
    },
    { line: 3, status: 'ok', kind: 'pointer', front: 'Q3', back: 'A3', issues: [], card_id: null },
  ],
  ...over,
})

const mount = () => renderWithQuery(<NewCardContainer search={{ mode: 'import' }} />)
const paste = async (user: ReturnType<typeof userEvent.setup>, text = 'Q1 :: A1\nOnly a question\nQ3 :: A3') => {
  await user.click(screen.getByLabelText('Your rows'))
  await user.paste(text)
}

beforeEach(() => {
  h.online = true
  h.importCards.mockReset()
  h.track.mockReset()
})

describe('the import panel of the card creator', () => {
  it('starts empty, with the format explained and nothing to press', async () => {
    const { container } = mount()
    expect(screen.getByRole('heading', { name: 'Import many cards' })).toBeInTheDocument()
    expect(screen.getByText('Nothing to check yet. Paste your rows above.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Check rows' })).toBeDisabled()
    expect(screen.getByRole('link', { name: 'Import many' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'One card' })).toHaveAttribute('href', '/app/recall/cards/new')
    await expectNoA11yViolations(container)
  })

  it('checks the rows, shows each with its error, and imports only after the check', async () => {
    const user = userEvent.setup()
    h.importCards.mockResolvedValueOnce(result()).mockResolvedValueOnce(
      result({
        dry_run: false,
        created: 2,
        valid: 2,
        rows: result().rows.map((r) => (r.status === 'ok' ? { ...r, status: 'created' as const, card_id: 'x' } : r)),
      }),
    )
    const { container } = mount()
    await paste(user)
    await user.click(screen.getByRole('button', { name: 'Check rows' }))

    const table = await screen.findByRole('table')
    expect(table).toBeInTheDocument()
    expect(screen.getAllByRole('row')).toHaveLength(4) // header + 3
    expect(screen.getByText('This line could not be read.')).toBeInTheDocument()
    expect(screen.getByText('2 rows are ready, and 1 row with a problem will be skipped.')).toBeInTheDocument()
    expect(h.importCards.mock.calls[0][0]).toMatchObject({ dry_run: true, text: 'Q1 :: A1\nOnly a question\nQ3 :: A3' })
    expect(h.importCards.mock.calls[0][0].client_id).toEqual(expect.any(String))
    await expectNoA11yViolations(container)

    await user.click(screen.getByRole('button', { name: 'Import 2 rows' }))
    expect(await screen.findByRole('heading', { name: '2 rows imported' })).toBeInTheDocument()
    expect(screen.getByText('1 row had a problem and was skipped.')).toBeInTheDocument()
    // the same batch id was used for the preview and the real call, and the real call is not a preview
    expect(h.importCards.mock.calls[1][0]).toMatchObject({ dry_run: false })
    expect(h.importCards.mock.calls[1][0].client_id).toBe(h.importCards.mock.calls[0][0].client_id)
    expect(h.track).toHaveBeenCalledWith('recall_import_done', { rows: 3, created: 2, invalid: 1 })
    expect(screen.getByRole('link', { name: 'See your cards' })).toHaveAttribute('href', '/app/recall/cards')
    await user.click(screen.getByRole('button', { name: 'Import more' }))
    expect(screen.getByLabelText('Your rows')).toHaveValue('')
  })

  it('works with the keyboard alone', async () => {
    const user = userEvent.setup()
    h.importCards.mockResolvedValue(result())
    mount()
    screen.getByLabelText('Your rows').focus()
    await user.paste('Q1 :: A1')
    await user.tab() // the file button
    await user.tab() // the check button (the chapter chooser has nothing to pick)
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Check rows' }))
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('table')).toBeInTheDocument()
  })

  it('drops the check when the text changes, so only the rows she saw can be imported', async () => {
    const user = userEvent.setup()
    h.importCards.mockResolvedValue(result())
    mount()
    await paste(user)
    await user.click(screen.getByRole('button', { name: 'Check rows' }))
    await screen.findByRole('table')
    await user.type(screen.getByLabelText('Your rows'), ' more')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Import \d/ })).not.toBeInTheDocument()
  })

  it('says when the rows do not fit the plan, and blocks the import', async () => {
    const user = userEvent.setup()
    h.importCards.mockResolvedValue(result({ quota: { room: 1, needed: 2, fits: false } }))
    mount()
    await paste(user)
    await user.click(screen.getByRole('button', { name: 'Check rows' }))
    expect(await screen.findByText(/need 2 card slots and your plan has room for 1 more/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Import 2 rows' })).toBeDisabled()
  })

  it('says nothing was added when the import fails, and keeps the rows to try again', async () => {
    const user = userEvent.setup()
    h.importCards
      .mockResolvedValueOnce(result())
      .mockRejectedValueOnce(
        new ApiError(429, 'x', { error: { code: 'quota_exceeded', message: 'Your plan is full.' } }),
      )
    mount()
    await paste(user)
    await user.click(screen.getByRole('button', { name: 'Check rows' }))
    await user.click(await screen.findByRole('button', { name: 'Import 2 rows' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Your plan is full. Nothing was added.')
    expect(screen.getByLabelText('Your rows')).toHaveValue('Q1 :: A1\nOnly a question\nQ3 :: A3')
    expect(screen.getByRole('button', { name: 'Import 2 rows' })).toBeEnabled()
  })

  it('shows the row limit message from the server', async () => {
    const user = userEvent.setup()
    h.importCards.mockRejectedValue(new ApiError(422, 'x', { error: { code: 'import_too_large', message: 'x' } }))
    mount()
    await paste(user)
    await user.click(screen.getByRole('button', { name: 'Check rows' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('at most 200 rows')
  })

  it('waits for a connection', async () => {
    h.online = false
    const user = userEvent.setup()
    mount()
    expect(screen.getByText(/You are offline/)).toBeInTheDocument()
    await paste(user)
    expect(screen.getByRole('button', { name: 'Check rows' })).toBeDisabled()
  })

  it('loads a file into the box', async () => {
    const user = userEvent.setup()
    const { container } = mount()
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(input, new File(['kind,front,back\npointer,Q,A'], 'cards.csv', { type: 'text/csv' }))
    await waitFor(() => expect(screen.getByLabelText('Your rows')).toHaveValue('kind,front,back\npointer,Q,A'))
  })

  it('refuses a file that is too big', async () => {
    const user = userEvent.setup()
    const { container } = mount()
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(input, new File(['x'.repeat(400_001)], 'big.csv', { type: 'text/csv' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('too big')
  })
})
