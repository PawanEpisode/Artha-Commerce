import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { FILED_LINK, makeNote } from '../lib/testing'
import { NoteCard } from './NoteCard'

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)

describe('NoteCard', () => {
  it('links the title to the note and shows the snippet and where it is filed', () => {
    render(<NoteCard note={makeNote({ link: FILED_LINK, title: 'Blocked credits' })} />)
    expect(screen.getByRole('link', { name: 'Blocked credits' })).toHaveAttribute(
      'href',
      '/app/notes/n/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    )
    expect(screen.getByText('ITC is blocked for motor vehicles.')).toBeInTheDocument()
    expect(screen.getByText('Taxation › GST: Input tax credit')).toBeInTheDocument()
  })

  it('says Unfiled for a note with no chapter, and Untitled for an empty title', () => {
    render(<NoteCard note={makeNote({ title: '  ' })} />)
    expect(screen.getByText('Unfiled')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Untitled note' })).toBeInTheDocument()
  })

  it('names the offline copy and the tags in words', () => {
    render(<NoteCard note={makeNote({ offline_copy: true, tags: [{ id: 't1', name: 'doubt', color_key: null }] })} />)
    expect(screen.getByText('Offline copy')).toBeInTheDocument()
    expect(screen.getByText('doubt')).toBeInTheDocument()
  })

  it('pins and trashes through buttons with 44px targets and clear names', async () => {
    const onPin = vi.fn()
    const onTrash = vi.fn()
    render(<NoteCard note={makeNote({ title: 'Cash flow' })} onPin={onPin} onTrash={onTrash} />)
    const pin = screen.getByRole('button', { name: 'Pin Cash flow' })
    expect(pin).toHaveClass('size-11')
    await userEvent.click(pin)
    expect(onPin).toHaveBeenCalledWith(true)
    await userEvent.click(screen.getByRole('button', { name: 'Move Cash flow to Trash' }))
    expect(onTrash).toHaveBeenCalled()
  })

  it('offers Unpin on a pinned note and can hide the location line', () => {
    render(
      <NoteCard
        note={makeNote({ pinned: true, title: 'Pinned one', link: FILED_LINK })}
        onPin={vi.fn()}
        showLocation={false}
      />,
    )
    expect(screen.getByRole('button', { name: 'Unpin Pinned one' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByText('Taxation › GST: Input tax credit')).toBeNull()
  })
})
