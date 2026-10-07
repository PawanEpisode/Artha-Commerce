import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  flag: true,
  track: vi.fn(),
  api: { getDigest: vi.fn(), postDigestAnswer: vi.fn() },
}))

vi.mock('~/modules/observability', () => ({ track: state.track, useFeatureFlag: () => state.flag }))
vi.mock('../lib/api', async (original) => ({ ...(await original<Record<string, unknown>>()), ...state.api }))

import { ApiError } from '~/lib/api'

import type { DigestState } from '../lib/schemas'
import { DigestContainer } from './DigestContainer'

const digest = (over: Partial<DigestState> = {}): DigestState => ({
  offer: true,
  enabled: false,
  time: '10:00',
  ...over,
})

function setup(place: 'settings' | 'inbox' = 'inbox') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <DigestContainer place={place} />
    </QueryClientProvider>,
  )
}

const answers = () => state.api.postDigestAnswer.mock.calls.map(([a]) => a as string)

beforeEach(() => {
  vi.clearAllMocks()
  state.flag = true
  state.api.getDigest.mockResolvedValue(digest())
  state.api.postDigestAnswer.mockImplementation(async (answer: string) =>
    digest({ offer: false, enabled: answer === 'accept' }),
  )
})

describe('DigestContainer (W3.7)', () => {
  it('shows the offer once, records it as seen, and keeps it on screen until answered', async () => {
    setup()
    expect(await screen.findByRole('heading', { name: 'Fewer alerts, one daily digest?' })).toBeInTheDocument()
    await waitFor(() => expect(answers()).toEqual(['seen']))
    expect(screen.getByText('10:00')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Switch to a daily digest' })).toBeEnabled()
    expect(state.track).toHaveBeenCalledWith('digest_offer_shown', { place: 'inbox' })
  })

  it('accepting in the inbox says what changed, takes focus, and closes', async () => {
    setup('inbox')
    await userEvent.click(await screen.findByRole('button', { name: 'Switch to a daily digest' }))
    await waitFor(() => expect(answers()).toEqual(['seen', 'accept']))
    const heading = await screen.findByRole('heading', { name: 'Daily digest' })
    await waitFor(() => expect(heading).toHaveFocus())
    expect(screen.getAllByText(/One digest a day at 10:00 from now on/).length).toBeGreaterThan(0)
    expect(state.track).toHaveBeenCalledWith('digest_answered', { answer: 'accept', place: 'inbox' })
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
  })

  it('accepting in settings turns the card into the switch back, and switching back says so', async () => {
    setup('settings')
    await userEvent.click(await screen.findByRole('button', { name: 'Switch to a daily digest' }))
    const status = await screen.findByRole('heading', { name: 'Daily digest is on' })
    await waitFor(() => expect(status).toHaveFocus())
    await userEvent.click(screen.getByRole('button', { name: 'Switch back to separate alerts' }))
    await waitFor(() => expect(answers()).toEqual(['seen', 'accept', 'stop']))
    expect((await screen.findAllByText(/Separate alerts are back on/)).length).toBeGreaterThan(0)
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
  })

  it('declining says nothing changed and does not offer again after closing', async () => {
    setup()
    await userEvent.click(await screen.findByRole('button', { name: 'Keep separate alerts' }))
    await waitFor(() => expect(answers()).toEqual(['seen', 'decline']))
    expect((await screen.findAllByText(/No change/)).length).toBeGreaterThan(0)
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
  })

  it('shows nothing when no offer is due, when the flag is off, or when notifications are off', async () => {
    state.api.getDigest.mockResolvedValue(digest({ offer: false }))
    setup()
    await waitFor(() => expect(state.api.getDigest).toHaveBeenCalled())
    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
    expect(answers()).toEqual([])
  })

  it('never asks the API while the flag is off', () => {
    state.flag = false
    setup()
    expect(state.api.getDigest).not.toHaveBeenCalled()
  })

  it('stays quiet when the server says notifications are off', async () => {
    state.api.getDigest.mockRejectedValue(new ApiError(403, 'off', { error: { code: 'notifications_disabled' } }))
    setup()
    await waitFor(() => expect(state.api.getDigest).toHaveBeenCalled())
    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
  })

  it('shows the switch back in settings when the digest is already on', async () => {
    state.api.getDigest.mockResolvedValue(digest({ offer: false, enabled: true, time: '08:15' }))
    setup('settings')
    expect(await screen.findByRole('heading', { name: 'Daily digest is on' })).toBeInTheDocument()
    expect(screen.getByText('08:15')).toBeInTheDocument()
    expect(answers()).toEqual([])
  })
})
