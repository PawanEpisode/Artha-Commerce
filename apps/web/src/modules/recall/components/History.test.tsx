import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { CardChanges, UpdateHistoryRow } from '../lib/schemas'
import { expectNoA11yViolations } from '../test-utils'
import { AttestationPanel } from './AttestationPanel'
import { CardChangesList } from './CardChangesList'
import { UpdateHistoryList } from './UpdateHistoryList'

const row = (over: Partial<UpdateHistoryRow> = {}): UpdateHistoryRow => ({
  id: 'u1',
  from_version_no: 1,
  to_version_no: 3,
  versions_skipped: 1,
  trigger: 'manual',
  applied_at: '2026-10-11T08:00:00Z',
  counts: { rechecked: 2, cards_created: 1 },
  changelog_md: 'Section 17 reworded.',
  ...over,
})

const changes = (over: Partial<CardChanges> = {}): CardChanges => ({
  card_id: 'c1',
  item_id: 'i1',
  platform: true,
  waiting: 1,
  versions: [
    {
      version_no: 3,
      change_kind: 'substantive',
      change_note: 'Time limit corrected',
      at: '2026-10-10T08:00:00Z',
      text: 'What is the ITC time limit?',
      received: false,
      current: false,
    },
    { version_no: 2, change_kind: 'typo', change_note: '', at: null, text: '', received: true, current: true },
  ],
  resets: [{ at: '2026-10-09T08:00:00Z', reason: 'amendment' }],
  ...over,
})

describe('the attestation panel', () => {
  const props = { attested: false, pending: false, offline: false, error: null, onChange: vi.fn() }

  it('asks the question, and saying yes passes true', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const { container } = render(<AttestationPanel {...props} onChange={onChange} />)
    expect(screen.getByRole('heading', { name: 'Are these your own words?' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Yes, these are my own words' }))
    expect(onChange).toHaveBeenCalledWith(true)
    await expectNoA11yViolations(container)
  })

  it('once said, offers to take it back (false)', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const { container } = render(<AttestationPanel {...props} attested onChange={onChange} />)
    expect(screen.getByRole('heading', { name: 'You said these are your own words' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Take that back' }))
    expect(onChange).toHaveBeenCalledWith(false)
    await expectNoA11yViolations(container)
  })

  it('is disabled offline with a reason, and shows a failure', () => {
    render(<AttestationPanel {...props} offline error="We could not save that." />)
    expect(screen.getByRole('button', { name: 'Yes, these are my own words' })).toBeDisabled()
    expect(screen.getByText('This needs the internet.')).toBeInTheDocument()
    expect(screen.getByText('We could not save that.')).toBeInTheDocument()
  })
})

describe('the update history list', () => {
  const props = { rows: [row()], loading: false, failed: false, onRetry: vi.fn() }

  it('lists each update with who applied it, the versions and what it did', async () => {
    const { container } = render(<UpdateHistoryList {...props} />)
    expect(screen.getByRole('list', { name: 'Past updates' })).toBeInTheDocument()
    expect(screen.getByText('You applied it')).toBeInTheDocument()
    expect(screen.getByText('Version 1 to version 3 (1 version in between)')).toBeInTheDocument()
    expect(screen.getByText('Section 17 reworded.')).toBeInTheDocument()
    expect(screen.getByText('1 new card, 2 cards to re-check.')).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })

  it('says so when there is nothing yet', () => {
    render(<UpdateHistoryList {...props} rows={[]} />)
    expect(screen.getByText(/No updates yet/)).toBeInTheDocument()
  })

  it('has a loading state and an error with a retry', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    const { rerender } = render(<UpdateHistoryList {...props} rows={undefined} loading />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading your past updates')
    rerender(<UpdateHistoryList {...props} rows={undefined} failed onRetry={onRetry} />)
    await user.click(screen.getByRole('button', { name: /try again/i }))
    expect(onRetry).toHaveBeenCalled()
  })
})

describe('the card changes list', () => {
  const props = { changes: changes(), loading: false, failed: false, onRetry: vi.fn() }

  it('marks the version she is on, the one waiting, and the re-checks', async () => {
    const { container } = render(<CardChangesList {...props} />)
    expect(screen.getByText(/1 newer version of this card is waiting/)).toBeInTheDocument()
    expect(screen.getByText('Not applied yet')).toBeInTheDocument()
    expect(screen.getByText('Your card shows this version')).toBeInTheDocument()
    expect(screen.getByText('Time limit corrected')).toBeInTheDocument()
    expect(screen.getByText('What is the ITC time limit?')).toBeInTheDocument()
    expect(screen.getByText(/A law this card relies on was amended/)).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })

  it('shows no notice when nothing is waiting and no re-check section without resets', () => {
    render(<CardChangesList {...props} changes={changes({ waiting: 0, resets: [] })} />)
    expect(screen.queryByText(/is waiting/)).not.toBeInTheDocument()
    expect(screen.queryByText(/came back for a re-check/)).not.toBeInTheDocument()
  })

  it('loads and fails kindly', () => {
    const { rerender } = render(<CardChangesList {...props} changes={undefined} loading />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading what changed')
    rerender(<CardChangesList {...props} changes={undefined} failed />)
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })

  it('offers the changed words between two versions with text and marks them for everyone', async () => {
    const user = userEvent.setup()
    const two = changes({
      versions: [
        {
          version_no: 3,
          change_kind: 'substantive',
          change_note: '',
          at: null,
          text: 'ITC limit is 60 days',
          received: true,
          current: true,
        },
        {
          version_no: 2,
          change_kind: 'create',
          change_note: '',
          at: null,
          text: 'ITC limit is 30 days',
          received: true,
          current: false,
        },
      ],
    })
    const { container } = render(<CardChangesList {...props} changes={two} />)
    const toggle = screen.getByRole('button', { name: 'Show what changed since version 2' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(toggle)
    const diff = screen.getByLabelText('Words changed since version 2')
    expect(diff.querySelector('del')).toHaveTextContent('removed: 30')
    expect(diff.querySelector('ins')).toHaveTextContent('added: 60')
    expect(screen.getByRole('button', { name: 'Hide the changed words' })).toHaveAttribute('aria-expanded', 'true')
    await expectNoA11yViolations(container)
    await user.click(screen.getByRole('button', { name: 'Hide the changed words' }))
    expect(screen.queryByLabelText('Words changed since version 2')).not.toBeInTheDocument()
  })

  it('offers no comparison when a version has no earlier text or the words are the same', () => {
    render(<CardChangesList {...props} />)
    expect(screen.queryByRole('button', { name: /Show what changed/ })).not.toBeInTheDocument()
  })
})
