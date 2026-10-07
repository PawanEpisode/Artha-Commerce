import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { MIB } from '../../lib/upload-check'
import { QuotaSheet } from './QuotaSheet'

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)

const largest = [
  { id: 'a', title: 'Big scan', bytes: 40 * MIB },
  { id: 'b', title: 'Module', bytes: 5 * MIB },
]
const props = {
  open: true,
  onOpenChange: () => undefined,
  largest,
  onDownload: () => undefined,
  onDelete: () => undefined,
}
const storage = { kind: 'storage' as const, used: 500 * MIB, limit: 500 * MIB, plan: 'free' }

describe('QuotaSheet', () => {
  it('says what is full in numbers and that typed notes keep working', () => {
    render(<QuotaSheet {...props} quota={storage} />)
    expect(screen.getByRole('dialog')).toHaveTextContent('Your PDF storage is full')
    expect(screen.getByRole('dialog')).toHaveTextContent('Your typed notes keep working')
    expect(screen.getByRole('meter', { name: 'PDF storage' })).toHaveAttribute('aria-valuetext', '500 of 500 MB')
  })

  it('offers Open, Download original and Delete for the largest PDFs', async () => {
    const onDownload = vi.fn()
    const onDelete = vi.fn()
    render(<QuotaSheet {...props} quota={storage} onDownload={onDownload} onDelete={onDelete} />)
    expect(screen.getAllByRole('link', { name: 'Open' })[0]).toHaveAttribute('href', '/app/notes/pdf/a')
    await userEvent.click(screen.getAllByRole('button', { name: /Download original/ })[0] as HTMLElement)
    expect(onDownload).toHaveBeenCalledWith(largest[0])
    await userEvent.click(screen.getAllByRole('button', { name: /Delete/ })[1] as HTMLElement)
    expect(onDelete).toHaveBeenCalledWith(largest[1])
  })

  it('explains the limit on request', async () => {
    render(<QuotaSheet {...props} quota={storage} />)
    const why = screen.getByRole('button', { name: 'Why is there a limit?' })
    expect(why).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(why)
    expect(why).toHaveAttribute('aria-expanded', 'true')
  })

  it('the OCR quota names the reset date and offers no deletions', () => {
    render(
      <QuotaSheet {...props} quota={{ kind: 'ocr', used: 300, limit: 300, plan: 'free', resets_on: '2026-11-01' }} />,
    )
    expect(screen.getByRole('dialog')).toHaveTextContent("You have used this month's OCR pages")
    expect(screen.getByRole('dialog')).toHaveTextContent(/resets on 1 Nov(ember)? 2026/)
    expect(screen.queryByText('Your largest PDFs')).not.toBeInTheDocument()
  })

  it('the PDF count quota is its own message, and an empty list gives advice', () => {
    render(<QuotaSheet {...props} largest={[]} quota={{ kind: 'documents', used: 100, limit: 100, plan: 'free' }} />)
    expect(screen.getByRole('dialog')).toHaveTextContent('number of PDFs your plan allows')
    expect(screen.getByText(/Delete a PDF you no longer need/)).toBeInTheDocument()
  })

  it('renders nothing without a quota', () => {
    render(<QuotaSheet {...props} quota={null} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
