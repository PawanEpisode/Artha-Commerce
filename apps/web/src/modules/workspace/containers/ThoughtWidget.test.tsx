import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ThoughtWidget } from './ThoughtWidget'

const s = vi.hoisted(() => ({ result: {} as Record<string, unknown> }))

vi.mock('~/modules/notifications', () => ({ useTodayThought: () => s.result }))
vi.mock('~/modules/personalization', () => ({ useOnline: () => true }))

const query = (over: Record<string, unknown> = {}) => ({
  data: undefined,
  isPending: false,
  isError: false,
  refetch: vi.fn(),
  ...over,
})
const line = { id: 'm1', body: 'One page today is better than none.', attribution: null, shown_on: '2026-10-07' }

beforeEach(() => {
  s.result = {}
})

describe('ThoughtWidget', () => {
  it('shows the line under its own heading', () => {
    s.result = { thought: line, off: false, query: query({ data: line }) }
    render(<ThoughtWidget />)
    expect(screen.getByRole('heading', { name: 'A thought for today' })).toBeInTheDocument()
    expect(screen.getByText(line.body)).toBeInTheDocument()
  })

  it('credits a line that has an attribution', () => {
    const credited = { ...line, attribution: 'Team Artha' }
    s.result = { thought: credited, off: false, query: query({ data: credited }) }
    render(<ThoughtWidget />)
    expect(screen.getByText('Team Artha')).toBeInTheDocument()
  })

  it('renders nothing when the card is off', () => {
    s.result = { thought: null, off: true, query: query({ data: null }) }
    const { container } = render(<ThoughtWidget />)
    expect(container).toBeEmptyDOMElement()
  })

  it('draws its own skeleton while loading and an error with Try again on failure', () => {
    s.result = { thought: null, off: false, query: query({ isPending: true }) }
    const { unmount } = render(<ThoughtWidget />)
    expect(screen.getByRole('status', { name: 'Loading A thought for today' })).toBeInTheDocument()
    unmount()
    s.result = { thought: null, off: false, query: query({ isError: true }) }
    render(<ThoughtWidget />)
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
