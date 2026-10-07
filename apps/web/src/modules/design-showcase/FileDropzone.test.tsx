import { FileDropzone, matchesAccept, sortFiles } from '@artha/design-system'
import { createEvent, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

const pdf = (name = 'notes.pdf', size = 1000) => {
  const file = new File(['x'], name, { type: 'application/pdf' })
  Object.defineProperty(file, 'size', { value: size })
  return file
}

describe('matchesAccept and sortFiles', () => {
  it('matches extensions, mime types and wildcards, case-insensitively', () => {
    expect(matchesAccept({ name: 'A.PDF', type: '' }, '.pdf')).toBe(true)
    expect(matchesAccept({ name: 'a', type: 'application/pdf' }, '.pdf,application/pdf')).toBe(true)
    expect(matchesAccept({ name: 'a.png', type: 'image/png' }, 'image/*')).toBe(true)
    expect(matchesAccept({ name: 'a.docx', type: 'application/x' }, '.pdf,image/*')).toBe(false)
    expect(matchesAccept({ name: 'a.docx', type: '' }, undefined)).toBe(true)
  })

  it('turns away by type, size and count', () => {
    const big = pdf('big.pdf', 500)
    const { accepted, rejected } = sortFiles(
      [pdf('notes.pdf', 50), big, new File(['x'], 'a.txt', { type: 'text/plain' }), pdf('two.pdf', 50)],
      {
        accept: '.pdf',
        maxSizeBytes: 100,
        multiple: false,
      },
    )
    expect(accepted.map((f) => f.name)).toEqual(['notes.pdf'])
    expect(rejected.map((r) => r.reason)).toEqual(['size', 'type', 'count'])
  })
})

describe('FileDropzone', () => {
  it('has a focusable file input named by its visible text and described by the hint', () => {
    render(<FileDropzone onFiles={() => undefined} accept=".pdf" hint="PDF, up to 200 MB" />)
    const input = screen.getByLabelText(/drop a file here/i)
    expect(input).toHaveAttribute('type', 'file')
    expect(input).not.toHaveAttribute('multiple')
    expect(input).toHaveAccessibleDescription('PDF, up to 200 MB')
    input.focus()
    expect(input).toHaveFocus()
  })

  it('hands accepted files to onFiles when picked', async () => {
    const onFiles = vi.fn()
    render(<FileDropzone onFiles={onFiles} accept=".pdf" />)
    await userEvent.upload(screen.getByLabelText(/drop a file here/i), pdf())
    expect(onFiles).toHaveBeenCalledOnce()
    expect(onFiles.mock.calls[0]![0]).toHaveLength(1)
  })

  it('shows an alert linked with aria-describedby for a rejected file and calls onReject', () => {
    const onFiles = vi.fn()
    const onReject = vi.fn()
    render(
      <FileDropzone
        onFiles={onFiles}
        onReject={onReject}
        accept=".pdf"
        messages={{ type: 'Only PDF files are accepted.' }}
      />,
    )
    const input = screen.getByLabelText(/drop a file here/i)
    fireEvent.change(input, { target: { files: [new File(['x'], 'a.txt', { type: 'text/plain' })] } })
    expect(onFiles).not.toHaveBeenCalled()
    expect(onReject).toHaveBeenCalledOnce()
    expect(screen.getByRole('alert')).toHaveTextContent('Only PDF files are accepted.')
    expect(input).toHaveAccessibleDescription('Only PDF files are accepted.')
    expect(input).toBeInvalid()
  })

  it('shows an error from outside', () => {
    render(<FileDropzone onFiles={() => undefined} error="Upload failed." />)
    expect(screen.getByRole('alert')).toHaveTextContent('Upload failed.')
  })

  it('takes one file unless multiple', () => {
    const onFiles = vi.fn()
    const { rerender } = render(<FileDropzone onFiles={onFiles} />)
    const input = screen.getByLabelText(/drop a file here/i)
    fireEvent.change(input, { target: { files: [pdf('a.pdf'), pdf('b.pdf')] } })
    expect(onFiles.mock.calls[0]![0]).toHaveLength(1)
    expect(screen.getByRole('alert')).toBeInTheDocument()
    rerender(<FileDropzone onFiles={onFiles} multiple />)
    fireEvent.change(screen.getByLabelText(/drop files here/i), { target: { files: [pdf('a.pdf'), pdf('b.pdf')] } })
    expect(onFiles.mock.calls[1]![0]).toHaveLength(2)
  })

  it('is disabled with its reason announced, and ignores drops', () => {
    const onFiles = vi.fn()
    const { container } = render(<FileDropzone onFiles={onFiles} disabled reason="Storage full." />)
    const input = screen.getByLabelText(/drop a file here/i)
    expect(input).toBeDisabled()
    expect(input).toHaveAccessibleDescription('Storage full.')
    fireEvent.drop(container.firstElementChild!, { dataTransfer: { files: [pdf()], types: ['Files'] } })
    expect(onFiles).not.toHaveBeenCalled()
  })

  it('changes its words and shape while a file is dragged over, and takes the drop', () => {
    const onFiles = vi.fn()
    const { container } = render(<FileDropzone onFiles={onFiles} accept=".pdf" />)
    const zone = container.firstElementChild!
    const dataTransfer = { files: [pdf()], types: ['Files'], dropEffect: 'none' }
    fireEvent.dragEnter(zone, { dataTransfer })
    expect(screen.getByText('Release to add')).toBeInTheDocument()
    expect(zone).toHaveAttribute('data-dragging')
    const over = createEvent.dragOver(zone, { dataTransfer })
    fireEvent(zone, over)
    expect(over.defaultPrevented).toBe(true)
    fireEvent.drop(zone, { dataTransfer })
    expect(screen.queryByText('Release to add')).toBeNull()
    expect(onFiles).toHaveBeenCalledOnce()
  })

  it('ignores drags that are not files', () => {
    const { container } = render(<FileDropzone onFiles={() => undefined} />)
    fireEvent.dragEnter(container.firstElementChild!, { dataTransfer: { types: ['text/plain'] } })
    expect(screen.queryByText('Release to add')).toBeNull()
  })
})
