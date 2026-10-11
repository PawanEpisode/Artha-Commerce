import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { expectNoA11yViolations, renderWithQuery } from '../test-utils'
import { ChapterRecallSlot } from './ChapterRecallSlot'
import { ReviewCardsLink } from './ReviewCardsLink'

const CHAPTER = '3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11'
const h = vi.hoisted(() => ({
  enabled: true,
  strength: vi.fn(),
}))

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)
vi.mock('../hooks/useRecallBasics', () => ({
  useRecallEnabled: () => h.enabled,
  useOnlineStatus: () => true,
  useRecallUser: () => 'u1',
}))
vi.mock('../lib/api', async (original) => ({
  ...(await original<Record<string, unknown>>()),
  recallApi: { chapterStrength: h.strength },
}))

const row = (over: Record<string, unknown> = {}) => ({
  chapter_id: CHAPTER,
  cards: 20,
  due: 6,
  strength: 0.82,
  percent: 82,
  ...over,
})

beforeEach(() => {
  h.enabled = true
  h.strength.mockReset()
})

describe('the recall card of a chapter page', () => {
  it('shows "Recall strength 82%, 6 cards due" and links to reviewing the chapter', async () => {
    h.strength.mockResolvedValue(row())
    const { container } = renderWithQuery(<ChapterRecallSlot chapterId={CHAPTER} />)
    expect(await screen.findByText('Recall strength 82%, 6 cards due')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Review cards' })).toHaveAttribute(
      'href',
      `/app/recall/review?chapter=${CHAPTER}`,
    )
    expect(h.strength).toHaveBeenCalledWith(CHAPTER)
    await expectNoA11yViolations(container)
  })

  it('is hidden when the flag is off, and never asks the server', async () => {
    h.enabled = false
    const { container } = renderWithQuery(<ChapterRecallSlot chapterId={CHAPTER} />)
    expect(container).toBeEmptyDOMElement()
    expect(h.strength).not.toHaveBeenCalled()
  })

  it('is hidden for a chapter with no cards, and while it loads', async () => {
    h.strength.mockResolvedValue(row({ cards: 0, due: 0, strength: null, percent: null }))
    const { container } = renderWithQuery(<ChapterRecallSlot chapterId={CHAPTER} />)
    expect(container).toBeEmptyDOMElement() // loading
    await vi.waitFor(() => expect(h.strength).toHaveBeenCalled())
    await new Promise((r) => setTimeout(r, 20))
    expect(container).toBeEmptyDOMElement() // answered with no cards
  })

  it('offers a retry when the answer fails', async () => {
    h.strength.mockRejectedValueOnce(new TypeError('Failed to fetch')).mockResolvedValue(row({ due: 0 }))
    renderWithQuery(<ChapterRecallSlot chapterId={CHAPTER} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Recall strength 82%, nothing due')).toBeInTheDocument()
  })

  it('asks again when a review has synced, so the numbers follow what she just did', async () => {
    h.strength.mockResolvedValueOnce(row()).mockResolvedValue(row({ due: 2, percent: 90 }))
    const { client } = renderWithQuery(<ChapterRecallSlot chapterId={CHAPTER} />)
    await screen.findByText('Recall strength 82%, 6 cards due')
    await client.invalidateQueries({ queryKey: ['recall', 'chapter-strength'] })
    expect(await screen.findByText('Recall strength 90%, 2 cards due')).toBeInTheDocument()
  })
})

describe('"Review cards" under a revision row', () => {
  it('links to the chapter review and names the chapter for a screen reader', () => {
    renderWithQuery(<ReviewCardsLink chapterId={CHAPTER} chapterName="GST and ITC" />)
    expect(screen.getByRole('link', { name: 'Review cards of GST and ITC' })).toHaveAttribute(
      'href',
      `/app/recall/review?chapter=${CHAPTER}`,
    )
  })
  it('is not there with the flag off', () => {
    h.enabled = false
    const { container } = renderWithQuery(<ReviewCardsLink chapterId={CHAPTER} />)
    expect(container).toBeEmptyDOMElement()
  })
})
