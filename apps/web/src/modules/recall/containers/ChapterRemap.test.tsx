import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { expectNoA11yViolations, renderWithQuery } from '../test-utils'
import { ChapterRemapContainer } from './ChapterRemapContainer'

const h = vi.hoisted(() => ({
  enabled: true,
  list: null as unknown,
  choose: null as unknown,
}))

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)
vi.mock('../hooks/useRecallBasics', () => ({
  useRecallEnabled: () => h.enabled,
  useOnlineStatus: () => true,
  useRecallUser: () => 'u1',
}))
vi.mock('../hooks/useUpdates', () => ({
  useChapterRemaps: () => h.list,
  useChooseChapter: () => h.choose,
}))

const q = (data: unknown, over = {}) => ({ isPending: false, isError: false, refetch: vi.fn(), data, ...over })
const choose = (over = {}) => ({
  mutate: vi.fn(),
  isPending: false,
  isError: false,
  error: null,
  variables: undefined,
  ...over,
})

const body = {
  count: 1,
  chapters: [{ id: 'x', key: 'x', name: 'Any chapter' }],
  items: [
    {
      id: 'r1',
      relation: 'split',
      label: 'What is the place of supply?',
      card_count: 1,
      from_chapter: { id: 'o', key: 'o', name: 'Old chapter' },
      candidates: [{ id: 'n1', key: 'n1', name: 'New chapter' }],
    },
  ],
}

beforeEach(() => {
  h.enabled = true
  h.list = q(body)
  h.choose = choose()
})

describe('needs a new chapter', () => {
  it('lists the cards waiting and moves one to the chosen chapter', async () => {
    const user = userEvent.setup()
    const { container } = renderWithQuery(<ChapterRemapContainer />)
    expect(screen.getByRole('heading', { name: 'Needs a new chapter', level: 1 })).toBeInTheDocument()
    expect(screen.getByText('1 topic needs a chapter of your new syllabus')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Move card' }))
    expect((h.choose as { mutate: ReturnType<typeof vi.fn> }).mutate).toHaveBeenCalledWith({
      remapId: 'r1',
      chapterId: 'n1',
      relation: 'split',
    })
    await expectNoA11yViolations(container)
  })

  it('has loading, error and empty states', async () => {
    const user = userEvent.setup()
    h.list = q(undefined, { isPending: true })
    const first = renderWithQuery(<ChapterRemapContainer />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading…')
    first.unmount()
    const refetch = vi.fn()
    h.list = q(undefined, { isError: true, refetch })
    const second = renderWithQuery(<ChapterRemapContainer />)
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(refetch).toHaveBeenCalled()
    second.unmount()
    h.list = q({ count: 0, chapters: [], items: [] })
    const { container } = renderWithQuery(<ChapterRemapContainer />)
    expect(screen.getByText('Every card has a chapter')).toBeInTheDocument()
    await expectNoA11yViolations(container)
  })

  it('shows a failed move on the card it belongs to', () => {
    h.choose = choose({
      isError: true,
      error: new Error('x'),
      variables: { remapId: 'r1', chapterId: 'n1', relation: 'split' },
    })
    renderWithQuery(<ChapterRemapContainer />)
    expect(screen.getByRole('alert')).toHaveTextContent('Could not move this card')
  })

  it('shows nothing with the flag off', () => {
    h.enabled = false
    renderWithQuery(<ChapterRemapContainer />)
    expect(screen.getByRole('heading', { name: 'Revision cards are not available yet' })).toBeInTheDocument()
  })
})
