import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { FILED_LINK, UNFILED_LINK } from '../../lib/testing'
import { makeDocument } from '../../lib/testing-documents'
import { DocumentCard } from './DocumentCard'

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)

const longName = 'An extraordinarily long chapter or subject name that would never fit on a narrow phone screen'

describe('DocumentCard filing chips', () => {
  it('shows a Subject chip and a Chapter chip with the full path as tooltip', () => {
    render(<DocumentCard doc={makeDocument({ link: FILED_LINK })} />)
    const subject = screen.getByText('Taxation').closest('[data-slot="entity-badge"]')
    const chapter = screen.getByText('GST: Input tax credit').closest('[data-slot="entity-badge"]')
    expect(subject).toHaveAttribute('data-kind', 'paper')
    expect(chapter).toHaveAttribute('data-kind', 'chapter')
    expect(subject).toHaveAttribute('title', 'Taxation › GST: Input tax credit')
    expect(chapter).toHaveAttribute('title', 'Taxation › GST: Input tax credit')
  })

  it('shows "All chapters" when the PDF is filed under the whole subject', () => {
    const link = { ...FILED_LINK, chapter_id: null, chapter_key: null, chapter_name: null }
    render(<DocumentCard doc={makeDocument({ link })} />)
    expect(screen.getByText('Taxation')).toBeInTheDocument()
    expect(screen.getByText('All chapters')).toBeInTheDocument()
  })

  it('shows a muted Unfiled chip, and nothing when the page already says where it is filed', () => {
    const { rerender } = render(<DocumentCard doc={makeDocument({ link: UNFILED_LINK })} />)
    expect(screen.getByText('Unfiled')).toBeInTheDocument()
    rerender(<DocumentCard doc={makeDocument({ link: UNFILED_LINK })} showLocation={false} />)
    expect(screen.queryByText('Unfiled')).not.toBeInTheDocument()
    rerender(<DocumentCard doc={makeDocument({ link: FILED_LINK })} showLocation={false} />)
    expect(screen.queryByText('Taxation')).not.toBeInTheDocument()
  })

  it('keeps the moved-or-removed badge and the tags', () => {
    const doc = makeDocument({
      link: { ...FILED_LINK, moved_or_removed: true },
      tags: [{ id: 't1', name: 'Revise twice', color_key: null }],
    })
    render(<DocumentCard doc={doc} />)
    expect(screen.getByText('Chapter moved or removed')).toBeInTheDocument()
    expect(screen.getByText('Revise twice')).toBeInTheDocument()
  })
})

describe('DocumentCard truncation', () => {
  it('keeps the title on one line with the full text in the title attribute', () => {
    render(<DocumentCard doc={makeDocument({ title: longName })} />)
    const link = screen.getByRole('link', { name: longName })
    expect(link).toHaveAttribute('title', longName)
    expect(link.parentElement).toHaveClass('truncate', 'min-w-0')
  })

  it('truncates subject, chapter and tag chips inside the row', () => {
    const doc = makeDocument({
      link: { ...FILED_LINK, subject_name: longName, chapter_name: longName },
      tags: [{ id: 't1', name: longName, color_key: null }],
    })
    render(<DocumentCard doc={doc} />)
    for (const text of screen.getAllByText(longName)) {
      expect(text).toHaveClass('truncate')
      expect(text.parentElement).toHaveClass('max-w-full')
      expect(text.parentElement).toHaveClass('min-w-0')
    }
    expect(screen.getAllByText(longName)).toHaveLength(3)
  })

  it('truncates the private badge and the status badge', () => {
    render(<DocumentCard doc={makeDocument({ source_kind: 'coaching' })} />)
    expect(screen.getByText('Private to you')).toHaveClass('truncate')
    expect(screen.getByText('Ready')).toHaveClass('truncate')
  })
})
