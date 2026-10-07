import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { makeNote } from '../lib/testing'
import { NotesList } from './NotesList'

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)

const base = {
  label: 'notes',
  items: [],
  isPending: false,
  isError: false,
  onRetry: () => undefined,
  empty: <p>Nothing here</p>,
}

describe('NotesList', () => {
  it('announces loading and shows placeholders', () => {
    render(<NotesList {...base} isPending />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading notes')
  })

  it('shows an error with a retry', async () => {
    const onRetry = vi.fn()
    render(<NotesList {...base} isError onRetry={onRetry} />)
    expect(screen.getByRole('alert')).toHaveTextContent('We could not load notes')
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalled()
  })

  it('shows the empty slot when there is nothing', () => {
    render(<NotesList {...base} />)
    expect(screen.getByText('Nothing here')).toBeInTheDocument()
  })

  it('lists notes, says when they are offline copies, and loads more', async () => {
    const onLoadMore = vi.fn()
    render(
      <NotesList
        {...base}
        items={[makeNote({ id: 'a', title: 'One' }), makeNote({ id: 'b', title: 'Two' })]}
        offline
        hasMore
        onLoadMore={onLoadMore}
        renderExtra={(n) => <span>extra for {n.title}</span>}
      />,
    )
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText(/You are offline/)).toBeInTheDocument()
    expect(screen.getByText('extra for Two')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Load more' }))
    expect(onLoadMore).toHaveBeenCalled()
  })

  it('keeps showing what it has when a refresh fails', () => {
    render(<NotesList {...base} items={[makeNote({ title: 'Kept' })]} isError />)
    expect(screen.getByRole('link', { name: 'Kept' })).toBeInTheDocument()
  })
})
