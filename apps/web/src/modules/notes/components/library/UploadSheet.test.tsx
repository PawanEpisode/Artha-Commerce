import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { FALLBACK_UPLOAD_LIMITS, MIB } from '../../lib/upload-check'
import { UploadSheet, type UploadSheetState } from './UploadSheet'

const props = {
  open: true,
  onOpenChange: () => undefined,
  limits: FALLBACK_UPLOAD_LIMITS,
  online: true,
  onFiles: () => undefined,
  onUpload: () => undefined,
  onChooseAnother: () => undefined,
  onManageStorage: () => undefined,
}
const file = { name: 'taxation.pdf', type: 'application/pdf', bytes: 8 * MIB, pages: 220 }
const sheet = (state: UploadSheetState, extra: Partial<typeof props> = {}) =>
  render(<UploadSheet {...props} {...extra} state={state} />)

describe('UploadSheet', () => {
  it('states the limits before anything is chosen, and says the PDF is private', () => {
    sheet({ step: 'choose' })
    expect(screen.getByRole('dialog')).toHaveTextContent('Your PDF is private to you.')
    expect(screen.getByText('PDF only. Up to 50 MB and 1,000 pages each.')).toBeInTheDocument()
  })

  it('takes a file from the keyboard through the labelled input', async () => {
    const onFiles = vi.fn()
    sheet({ step: 'choose' }, { onFiles })
    const input = screen.getByLabelText('Choose a PDF to upload')
    expect(input).toHaveAttribute('accept', expect.stringContaining('.pdf'))
    const pdf = new File(['%PDF-1.7'], 'a.pdf', { type: 'application/pdf' })
    await userEvent.upload(input, pdf)
    expect(onFiles).toHaveBeenCalledWith([pdf])
  })

  it('reaches the dropzone with Tab and closes with Escape', async () => {
    const onOpenChange = vi.fn()
    sheet({ step: 'choose' }, { onOpenChange })
    await userEvent.tab()
    expect(document.activeElement).not.toBe(document.body)
    await userEvent.keyboard('{Escape}')
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('offline disables the dropzone and says why', () => {
    sheet({ step: 'choose' }, { online: false })
    expect(screen.getByText('You are offline. Connect to the internet to upload.')).toBeInTheDocument()
    expect(screen.getByLabelText('Choose a PDF to upload')).toBeDisabled()
  })

  it('checking announces itself', () => {
    sheet({ step: 'checking', name: 'taxation.pdf', bytes: 8 * MIB })
    expect(screen.getByRole('status')).toHaveTextContent('Checking the file')
  })

  it('ready shows name, size and pages, then Upload runs', async () => {
    const onUpload = vi.fn()
    sheet({ step: 'ready', file, encrypted: false }, { onUpload })
    expect(screen.getByText('taxation.pdf')).toBeInTheDocument()
    expect(screen.getByText(/8.0 MB · 220 pages/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Upload' }))
    expect(onUpload).toHaveBeenCalled()
  })

  it('a locked file is accepted with a plain note', () => {
    sheet({ step: 'ready', file: { ...file, pages: null }, encrypted: true })
    expect(screen.getByText(/This PDF is locked. It is accepted/)).toBeInTheDocument()
    expect(screen.getByText(/pages counted after upload/)).toBeInTheDocument()
  })

  it('an over-limit file is refused before any byte moves, with the limit and a how-to', async () => {
    const onUpload = vi.fn()
    sheet(
      {
        step: 'refused',
        file: { ...file, bytes: 63 * MIB },
        refusal: { reason: 'too_large', limitMb: 50, bytes: 63 * MIB },
      },
      { onUpload },
    )
    expect(screen.getByRole('alert')).toHaveTextContent('50 MB limit (this file 63 MB)')
    expect(screen.getByText(/Nothing was uploaded/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Upload' })).not.toBeInTheDocument()
    const help = screen.getByRole('button', { name: 'How to shrink a PDF' })
    expect(help).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(help)
    expect(help).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText(/Split a big module/)).toBeInTheDocument()
  })

  it('a wrong type is refused in words', () => {
    sheet({
      step: 'refused',
      file: { ...file, name: 'a.docx', type: 'application/msword' },
      refusal: { reason: 'type' },
    })
    expect(screen.getByRole('alert')).toHaveTextContent('This does not look like a PDF')
  })

  it('a full account refuses with Manage storage', async () => {
    const onManageStorage = vi.fn()
    sheet(
      { step: 'refused', file, refusal: { reason: 'quota', kind: 'storage', used: 500 * MIB, limit: 500 * MIB } },
      { onManageStorage },
    )
    await userEvent.click(screen.getByRole('button', { name: 'Manage storage' }))
    expect(onManageStorage).toHaveBeenCalled()
  })

  it('Choose another goes back', async () => {
    const onChooseAnother = vi.fn()
    sheet({ step: 'ready', file, encrypted: false }, { onChooseAnother })
    await userEvent.click(screen.getByRole('button', { name: 'Choose another' }))
    expect(onChooseAnother).toHaveBeenCalled()
  })

  it('offline blocks Upload on a chosen file', () => {
    sheet({ step: 'ready', file, encrypted: false }, { online: false })
    expect(screen.getByRole('button', { name: 'Upload' })).toBeDisabled()
    expect(screen.getByText('You are offline. Upload needs a connection.')).toBeInTheDocument()
  })
})
