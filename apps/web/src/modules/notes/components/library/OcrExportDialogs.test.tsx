import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { ExportJob } from '../../lib/document-types'
import { defaultExportForm } from '../../lib/export-options'
import { ExportDialog } from './ExportDialog'
import { ExportJobStatus } from './ExportJobStatus'
import { OcrDialog } from './OcrDialog'

const legend = { y: 'Important', g: 'Formula', b: 'Section', p: 'Doubt', o: 'Example' }
const scanned = {
  title: 'Old scan',
  status: 'ready' as const,
  page_count: 320,
  ocr_pages_total: 0,
  ocr_pages_done: 0,
  ocr_status: 'none' as const,
  can_copy: true,
}
const usage = (used: number, limit = 500) =>
  ({ limits: { ocr_pages_per_month: limit }, used: { ocr_pages: used }, resets_on: '2026-11-01' }) as never
const ocr = {
  open: true,
  onOpenChange: () => undefined,
  doc: scanned,
  usage: usage(0),
  lang: 'eng' as const,
  onLangChange: () => undefined,
  online: true,
  onStart: () => undefined,
}

describe('OcrDialog', () => {
  it('offers the estimate, the meter and the language, and Not now closes', async () => {
    const onOpenChange = vi.fn()
    render(<OcrDialog {...ocr} onOpenChange={onOpenChange} />)
    expect(screen.getByText('About 25 minutes, uses 320 of 500 pages this month.')).toBeInTheDocument()
    expect(screen.getByRole('meter', { name: 'OCR pages this month' })).toHaveAttribute('aria-valuetext', '0 of 500')
    expect(screen.getByRole('radio', { name: 'English' })).toBeChecked()
    await userEvent.click(screen.getByRole('button', { name: 'Not now' }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('starts OCR and changes the language from the keyboard', async () => {
    const onStart = vi.fn()
    const onLangChange = vi.fn()
    render(<OcrDialog {...ocr} onStart={onStart} onLangChange={onLangChange} />)
    await userEvent.click(screen.getByRole('radio', { name: 'English and Hindi' }))
    expect(onLangChange).toHaveBeenCalledWith('eng+hin')
    await userEvent.click(screen.getByRole('button', { name: 'Make searchable' }))
    expect(onStart).toHaveBeenCalledWith()
  })

  it('traps focus in the dialog and closes with Escape', async () => {
    const onOpenChange = vi.fn()
    render(<OcrDialog {...ocr} onOpenChange={onOpenChange} />)
    expect(screen.getByRole('dialog')).toHaveTextContent('Make this PDF searchable')
    await userEvent.keyboard('{Escape}')
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('hides the Hindi choice when the server cannot read it', () => {
    render(<OcrDialog {...ocr} hindiAvailable={false} />)
    expect(screen.queryByRole('radio', { name: 'English and Hindi' })).not.toBeInTheDocument()
  })

  it('over the monthly allowance: names the reset date and offers the first pages that fit', async () => {
    const onStart = vi.fn()
    render(<OcrDialog {...ocr} usage={usage(380)} onStart={onStart} />)
    expect(screen.getByRole('alert')).toHaveTextContent('You have 120 OCR pages left this month. They reset on')
    expect(screen.getByRole('alert')).toHaveTextContent(/1 Nov(ember)? 2026/)
    expect(screen.queryByRole('button', { name: 'Make searchable' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Read the first 120 pages' }))
    expect(onStart).toHaveBeenCalledWith('1-120')
  })

  it('with nothing left it only offers to close', () => {
    render(<OcrDialog {...ocr} usage={usage(500)} />)
    expect(screen.getByRole('alert')).toHaveTextContent('You have no OCR pages left this month.')
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
  })

  it('locked, copy-restricted, running and done each have their own state', () => {
    const { rerender } = render(<OcrDialog {...ocr} doc={{ ...scanned, status: 'needs_password' }} />)
    expect(screen.getByText(/Locked: search and OCR need the password/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Make searchable' })).not.toBeInTheDocument()
    rerender(<OcrDialog {...ocr} doc={{ ...scanned, can_copy: false }} />)
    expect(screen.getByText(/does not allow copying its text/)).toBeInTheDocument()
    rerender(
      <OcrDialog {...ocr} doc={{ ...scanned, ocr_status: 'running', ocr_pages_done: 120, ocr_pages_total: 320 }} />,
    )
    expect(screen.getByText('OCR 120 of 320, searchable as pages finish')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Keep reading' })).toBeInTheDocument()
    rerender(<OcrDialog {...ocr} doc={{ ...scanned, ocr_status: 'done' }} />)
    expect(screen.getByText('This PDF is already searchable.')).toBeInTheDocument()
  })

  it('offline cannot start, and a refusal shows in words', () => {
    render(<OcrDialog {...ocr} online={false} error="This PDF is still being prepared." />)
    expect(screen.getByText('You are offline. OCR needs a connection.')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('still being prepared')
    expect(screen.queryByRole('button', { name: 'Make searchable' })).not.toBeInTheDocument()
  })
})

const exportProps = {
  open: true,
  onOpenChange: () => undefined,
  doc: { title: 'Taxation', page_count: 200 },
  form: defaultExportForm(),
  onFormChange: () => undefined,
  legend,
  tags: [{ id: 't1', name: 'Revise', color: null }] as never,
  blocked: null,
  online: true,
  busy: false,
  onSubmit: () => undefined,
}

describe('ExportDialog', () => {
  it("names colours by the student's legend, never as bare colours", () => {
    render(<ExportDialog {...exportProps} />)
    for (const name of Object.values(legend)) expect(screen.getByRole('checkbox', { name })).toBeInTheDocument()
    expect(screen.getByLabelText('Pages (optional)')).toBeInTheDocument()
    expect(screen.getByText(/Leave empty for all 200 pages/)).toBeInTheDocument()
  })

  it('edits through the form and submits with the keyboard', async () => {
    const onFormChange = vi.fn()
    const onSubmit = vi.fn()
    render(<ExportDialog {...exportProps} onFormChange={onFormChange} onSubmit={onSubmit} />)
    await userEvent.click(screen.getByRole('checkbox', { name: 'Formula' }))
    expect(onFormChange).toHaveBeenCalledWith(expect.objectContaining({ colors: ['g'] }))
    await userEvent.click(screen.getByRole('button', { name: 'Revise' }))
    expect(onFormChange).toHaveBeenCalledWith(expect.objectContaining({ tags: ['t1'] }))
    await userEvent.click(screen.getByRole('switch', { name: /Add my notes at the end/ }))
    expect(onFormChange).toHaveBeenCalledWith(expect.objectContaining({ appendix: true }))
    screen.getByLabelText('Pages (optional)').focus()
    await userEvent.keyboard('{Enter}')
    expect(onSubmit).toHaveBeenCalled()
  })

  it.each([
    ['restricted', /does not allow copying/],
    ['locked', /PDF is locked/],
    ['not_ready', /still being prepared/],
  ] as const)('is disabled with a reason when %s', (blocked, text) => {
    render(<ExportDialog {...exportProps} blocked={blocked} />)
    expect(screen.getByRole('alert')).toHaveTextContent(text)
    expect(screen.getByRole('button', { name: 'Build export' })).toBeDisabled()
  })

  it('needs at least one kind of mark, shows a page error, and is disabled offline', () => {
    const { rerender } = render(<ExportDialog {...exportProps} form={{ ...defaultExportForm(), include: [] }} />)
    expect(screen.getByText('Choose at least one kind of mark.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Build export' })).toBeDisabled()
    rerender(<ExportDialog {...exportProps} pagesError="This PDF has 200 pages." />)
    expect(screen.getByText('This PDF has 200 pages.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Build export' })).toBeDisabled()
    rerender(<ExportDialog {...exportProps} online={false} />)
    expect(screen.getByText('You are offline. Exports need a connection.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Build export' })).toBeDisabled()
  })

  it('shows the job status and a server refusal', () => {
    render(
      <ExportDialog {...exportProps} error="You have reached this month's export limit." status={<p>status area</p>} />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('export limit')
    expect(screen.getByText('status area')).toBeInTheDocument()
  })
})

const job = (over: Partial<ExportJob>): ExportJob => ({
  id: 'j1',
  kind: 'pdf',
  document_id: 'd1',
  status: 'queued',
  progress: 0,
  page_count: 200,
  error_code: null,
  download_url: null,
  expires_at: null,
  options: {},
  created_at: '2026-10-08T00:00:00Z',
  ...over,
})

describe('ExportJobStatus', () => {
  it('shows queued, running with percent, and a polite status', () => {
    const { rerender } = render(<ExportJobStatus job={job({})} onDownload={() => undefined} />)
    expect(screen.getByRole('status')).toHaveTextContent('Waiting to start')
    rerender(<ExportJobStatus job={job({ status: 'running', progress: 40 })} onDownload={() => undefined} />)
    expect(screen.getByRole('status')).toHaveTextContent('Building your export… 40%')
    expect(screen.getByRole('progressbar', { name: 'Export progress' })).toBeInTheDocument()
  })

  it('offers Download when done and says how long the link lasts', async () => {
    const onDownload = vi.fn()
    render(
      <ExportJobStatus
        job={job({ status: 'done', progress: 100, download_url: 'https://x' })}
        onDownload={onDownload}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Download' }))
    expect(onDownload).toHaveBeenCalled()
    expect(screen.getByText(/works for 24 hours/)).toBeInTheDocument()
  })

  it('too large: suggests a range and builds it in one tap', async () => {
    const onRetryPages = vi.fn()
    render(
      <ExportJobStatus
        job={job({ status: 'failed', error_code: 'export_too_large', details: { suggested_pages: '1-120' } })}
        onDownload={() => undefined}
        onRetryPages={onRetryPages}
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Try pages 1-120')
    await userEvent.click(screen.getByRole('button', { name: 'Export pages 1-120' }))
    expect(onRetryPages).toHaveBeenCalledWith('1-120')
  })

  it('expired offers to build again; a plain failure offers Try again', async () => {
    const onRetry = vi.fn()
    const { rerender } = render(
      <ExportJobStatus job={job({ status: 'expired' })} onDownload={() => undefined} onRetry={onRetry} />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('This export has expired')
    await userEvent.click(screen.getByRole('button', { name: 'Build it again' }))
    rerender(
      <ExportJobStatus
        job={job({ status: 'failed', error_code: 'failed' })}
        onDownload={() => undefined}
        onRetry={onRetry}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledTimes(2)
  })

  it('a restricted failure has no retry', () => {
    render(
      <ExportJobStatus
        job={job({ status: 'failed', error_code: 'restricted' })}
        onDownload={() => undefined}
        onRetry={() => undefined}
      />,
    )
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })
})
