import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { UploadItem } from '../../lib/upload-manager'
import { UploadProgressChip } from './UploadProgressChip'

vi.mock('@tanstack/react-router', async () => (await import('~/test/router-stub')).routerStub)

const item = (over: Partial<UploadItem> = {}): UploadItem => ({
  id: 'u1',
  fileName: 'taxation.pdf',
  bytes: 10_000_000,
  pages: 120,
  phase: 'uploading',
  loaded: 4_000_000,
  startedAt: 0,
  ...over,
})
const actions = () => ({
  onCancel: vi.fn(),
  onRetry: vi.fn(),
  onDismiss: vi.fn(),
  onKeepBoth: vi.fn(),
  onOpenExisting: vi.fn(),
  onManageStorage: vi.fn(),
})

describe('UploadProgressChip', () => {
  it('is silent and invisible with nothing uploading, but keeps its live region mounted', () => {
    render(<UploadProgressChip items={[]} announcement="" {...actions()} />)
    expect(screen.queryByRole('region', { name: 'Uploads' })).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite')
  })

  it('announces through a polite live region', () => {
    const { rerender } = render(
      <UploadProgressChip items={[item()]} announcement="Uploading taxation.pdf." {...actions()} />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('Uploading taxation.pdf.')
    rerender(
      <UploadProgressChip items={[item({ phase: 'ready' })]} announcement="taxation.pdf is ready." {...actions()} />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('taxation.pdf is ready.')
  })

  it('shows progress in words and bytes, and cancels', async () => {
    const a = actions()
    render(<UploadProgressChip items={[item()]} announcement="" {...a} />)
    expect(screen.getByText('40% · 3.8 MB of 9.5 MB')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Uploading taxation.pdf' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel uploading taxation.pdf' }))
    expect(a.onCancel).toHaveBeenCalledWith('u1')
  })

  it('hides on the library where the same rows are inline', () => {
    render(<UploadProgressChip items={[item()]} announcement="" hidden {...actions()} />)
    expect(screen.queryByRole('region', { name: 'Uploads' })).not.toBeInTheDocument()
  })

  it('a failed upload says why, shows the request id and retries', async () => {
    const a = actions()
    render(
      <UploadProgressChip
        items={[
          item({
            phase: 'failed',
            failure: {
              reason: 'server',
              message: 'Something went wrong on our side.',
              retryable: true,
              requestId: 'req-7',
            },
          }),
        ]}
        announcement=""
        {...a}
      />,
    )
    expect(screen.getByText('Something went wrong on our side.')).toBeInTheDocument()
    expect(screen.getByText('Request req-7')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(a.onRetry).toHaveBeenCalledWith('u1')
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss taxation.pdf' }))
    expect(a.onDismiss).toHaveBeenCalledWith('u1')
  })

  it('a quota failure offers Manage storage and no Retry', async () => {
    const a = actions()
    const failed = item({
      phase: 'failed',
      failure: { reason: 'quota', message: 'There is no room left for this file.', retryable: false },
    })
    render(<UploadProgressChip items={[failed]} announcement="" {...a} />)
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Manage storage' }))
    expect(a.onManageStorage).toHaveBeenCalledWith(failed)
  })

  it('a duplicate offers Open it or Keep both', async () => {
    const a = actions()
    const dup = item({ phase: 'duplicate', duplicateOf: 'orig' })
    render(<UploadProgressChip items={[dup]} announcement="" {...a} />)
    expect(screen.getByText('You already have this file.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Open it' }))
    expect(a.onOpenExisting).toHaveBeenCalledWith(dup)
    await userEvent.click(screen.getByRole('button', { name: 'Keep both' }))
    expect(a.onKeepBoth).toHaveBeenCalledWith('u1')
  })

  it('a scanned file offers to open it and says search needs OCR; a locked one says so', () => {
    const { rerender } = render(
      <UploadProgressChip
        items={[item({ phase: 'ready', scanned: true, documentId: 'd1' })]}
        announcement=""
        {...actions()}
      />,
    )
    expect(screen.getByText(/Scanned: search needs OCR/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open' })).toHaveAttribute('href', '/app/notes/pdf/d1')
    rerender(
      <UploadProgressChip
        items={[item({ phase: 'ready', encrypted: true, documentId: 'd1' })]}
        announcement=""
        {...actions()}
      />,
    )
    expect(screen.getByText(/Locked: opens with your password/)).toBeInTheDocument()
  })

  it('shows at most three rows and counts the rest', () => {
    const items = [1, 2, 3, 4, 5].map((n) => item({ id: `u${n}`, fileName: `f${n}.pdf` }))
    render(<UploadProgressChip items={items} announcement="" {...actions()} />)
    expect(screen.getAllByRole('progressbar')).toHaveLength(3)
    expect(screen.getByText('and 2 more')).toBeInTheDocument()
  })

  it('every action is a 44 px target on a phone', () => {
    render(
      <UploadProgressChip
        items={[
          item({
            phase: 'failed',
            failure: { reason: 'network', message: 'Upload paused, connection lost.', retryable: true },
          }),
        ]}
        announcement=""
        {...actions()}
      />,
    )
    for (const button of screen.getAllByRole('button')) expect(button.className).toMatch(/min-h-11|size-11/)
  })
})
