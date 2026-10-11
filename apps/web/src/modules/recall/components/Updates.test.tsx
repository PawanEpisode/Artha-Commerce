import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { ChapterRemapItem, UpdatePreview } from '../lib/schemas'
import { expectNoA11yViolations } from '../test-utils'
import { ChapterRemapRow } from './ChapterRemapList'
import { RecheckNote } from './RecheckNote'
import { FollowToggle, OldSyllabusFlag, UpdateBanner } from './UpdateBanner'
import { UpdateSheet } from './UpdateSheet'

const preview = (over: Partial<UpdatePreview> = {}): UpdatePreview => ({
  subscription_id: 's1',
  update_available: true,
  follow_updates: true,
  from_version_no: 1,
  to_version_no: 3,
  versions_skipped: 1,
  changelog_md: 'Rewrote the ITC time limit.',
  counts: { added: 1, removed: 0, typo: 0, clarify: 0, substantive: 2, amendment: 0, total: 3, recheck: 2 },
  items: {
    substantive: [
      { item_id: 'a', label: 'When is ITC blocked?', importance: 'mandatory' },
      { item_id: 'b', label: 'Time limit for ITC', importance: 'important' },
    ],
    added: [{ item_id: 'c', label: 'New rule', importance: 'bullet' }],
  },
  more: { substantive: 4 },
  returning_today: 2,
  ...over,
})

const sheetProps = (over = {}) => ({
  open: true,
  onOpenChange: vi.fn(),
  preview: preview(),
  loading: false,
  error: null,
  applying: false,
  offline: false,
  onApply: vi.fn(),
  onRetry: vi.fn(),
  ...over,
})

describe('the update banner and the follow toggle', () => {
  it('names the number of changes and opens the sheet', async () => {
    const user = userEvent.setup()
    const onReview = vi.fn()
    const { container } = render(<UpdateBanner changes={3} follow onReview={onReview} />)
    expect(screen.getByText('Update available (3 changes)')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'See what changed' }))
    expect(onReview).toHaveBeenCalled()
    await expectNoA11yViolations(container)
  })

  it('explains pin and follow, and the switch is a labelled control that works by keyboard', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const { container, rerender } = render(<FollowToggle follow pending={false} onChange={onChange} />)
    const sw = screen.getByRole('switch', { name: 'Take updates automatically' })
    expect(sw).toBeChecked()
    sw.focus()
    await user.keyboard(' ')
    expect(onChange).toHaveBeenCalledWith(false)
    rerender(<FollowToggle follow={false} pending={false} onChange={onChange} />)
    expect(screen.getByText(/Pinned: your cards stay as they are/)).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })

  it('disables the switch while saving and offline', () => {
    render(<FollowToggle follow pending onChange={vi.fn()} />)
    expect(screen.getByRole('switch')).toBeDisabled()
  })

  it('flags a deck for the old syllabus', async () => {
    const { container } = render(<OldSyllabusFlag />)
    expect(screen.getByText(/deck is for the old syllabus/)).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })
})

describe('the update sheet', () => {
  it('shows the change note, the kinds with their cards and what returns today', async () => {
    render(<UpdateSheet {...sheetProps()} />)
    expect(screen.getByRole('dialog', { name: 'Update available (3 changes)' })).toBeInTheDocument()
    expect(screen.getByText('From version 1 to version 3.')).toBeInTheDocument()
    expect(screen.getByText('Rewrote the ITC time limit.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Meaning changed (2)' })).toBeInTheDocument()
    expect(screen.getByText('When is ITC blocked?')).toBeInTheDocument()
    expect(screen.getByText('and 4 more')).toBeInTheDocument()
    expect(screen.getByText(/2 cards come back today/)).toBeInTheDocument()
    await expectNoA11yViolations(document.body)
  })

  it('applies, and "Not now" closes without applying', async () => {
    const user = userEvent.setup()
    const props = sheetProps()
    render(<UpdateSheet {...props} />)
    await user.click(screen.getByRole('button', { name: 'Apply update' }))
    expect(props.onApply).toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Not now' }))
    expect(props.onOpenChange).toHaveBeenCalledWith(false)
  })

  it('has loading, error with retry, and offline states', async () => {
    const user = userEvent.setup()
    const { rerender } = render(<UpdateSheet {...sheetProps({ preview: undefined, loading: true })} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading the changes…')
    expect(screen.getByRole('button', { name: 'Apply update' })).toBeDisabled()
    const props = sheetProps({ preview: undefined, error: 'Could not load the changes.' })
    rerender(<UpdateSheet {...props} />)
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(props.onRetry).toHaveBeenCalled()
    rerender(<UpdateSheet {...sheetProps({ offline: true })} />)
    expect(screen.getByText(/You are offline/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Apply update' })).toBeDisabled()
  })

  it('cannot be dismissed while the update is being applied', async () => {
    const user = userEvent.setup()
    const props = sheetProps({ applying: true })
    render(<UpdateSheet {...props} />)
    await user.click(screen.getByRole('button', { name: 'Not now' }))
    expect(props.onOpenChange).not.toHaveBeenCalled()
  })
})

describe('the re-check note', () => {
  it('says why, and "Still correct" confirms', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    const { container, rerender } = render(<RecheckNote reason="content_changed" onConfirm={onConfirm} />)
    expect(screen.getByText('Updated, please re-check')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Still correct' }))
    expect(onConfirm).toHaveBeenCalled()
    rerender(<RecheckNote reason="amendment" onConfirm={onConfirm} />)
    expect(screen.getByText('Check against the amendment')).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })

  it('needs the internet to confirm', () => {
    render(<RecheckNote reason="amendment" offline onConfirm={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Still correct' })).toBeDisabled()
    expect(screen.getByText(/Connect to the internet/)).toBeInTheDocument()
  })
})

describe('a card waiting for a chapter', () => {
  const item: ChapterRemapItem = {
    id: 'r1',
    relation: 'split',
    label: 'What is the place of supply?',
    card_count: 1,
    from_chapter: { id: 'o1', key: 'old', name: 'Old chapter' },
    candidates: [
      { id: 'n1', key: 'a', name: 'New chapter A' },
      { id: 'n2', key: 'b', name: 'New chapter B' },
    ],
  }

  it('offers the map candidates and moves the card on the first one by default', async () => {
    const user = userEvent.setup()
    const onChoose = vi.fn()
    const { container } = render(
      <ul>
        <ChapterRemapRow item={item} chapters={[]} pending={false} error={null} onChoose={onChoose} />
      </ul>,
    )
    expect(screen.getByText('Was: Old chapter')).toBeInTheDocument()
    expect(screen.getByText(/split in the new syllabus/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Move card' }))
    expect(onChoose).toHaveBeenCalledWith('n1')
    await expectNoA11yViolations(container)
  })

  it('falls back to every chapter when the map has no suggestion and shows an error', () => {
    render(
      <ul>
        <ChapterRemapRow
          item={{ ...item, relation: 'none', candidates: [] }}
          chapters={[{ id: 'x', name: 'Any chapter' }]}
          pending={false}
          error="Could not move this card. Please try again."
          onChoose={vi.fn()}
        />
      </ul>,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Could not move this card')
    expect(screen.getByRole('combobox', { name: 'Move to chapter' })).toHaveTextContent('Any chapter')
  })
})
