import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { VersionRow } from '../lib/types'
import { VersionPanel } from './VersionPanel'

const versions: VersionRow[] = [
  { rev: 3, title: 'T', source: 'autosave', chars: 120, created_at: '2026-10-05T10:00:00Z' },
  { rev: 2, title: 'T', source: 'manual', chars: 100, created_at: '2026-10-04T10:00:00Z' },
]

const base = {
  open: true,
  onOpenChange: () => undefined,
  versions,
  isPending: false,
  isError: false,
  onRetry: () => undefined,
  currentRev: 3,
  currentBody: 'now text',
  selectedRev: undefined,
  onSelect: () => undefined,
  detail: undefined,
  detailPending: false,
  mode: 'view' as const,
  onMode: () => undefined,
  onRestore: () => undefined,
  restoring: false,
  online: true,
}

describe('VersionPanel', () => {
  it('lists versions newest first and marks the current one', async () => {
    const onSelect = vi.fn()
    render(<VersionPanel {...base} onSelect={onSelect} />)
    expect(screen.getByText('Version 3 (current)')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Version 2/ }))
    expect(onSelect).toHaveBeenCalledWith(2)
  })

  it('shows loading, an error with retry, and an empty history', async () => {
    const onRetry = vi.fn()
    const { rerender } = render(<VersionPanel {...base} versions={undefined} isPending />)
    expect(screen.getByText('Loading versions…')).toBeInTheDocument()
    rerender(<VersionPanel {...base} versions={undefined} isError onRetry={onRetry} />)
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalled()
    rerender(<VersionPanel {...base} versions={[]} />)
    expect(screen.getByText(/No earlier versions yet/)).toBeInTheDocument()
  })

  it('restores an older version, but not the current one, and not offline', async () => {
    const onRestore = vi.fn()
    const detail = {
      rev: 2,
      title: 'T',
      body_md: 'old text',
      source: 'manual' as const,
      created_at: '2026-10-04T10:00:00Z',
    }
    const { rerender } = render(<VersionPanel {...base} selectedRev={2} detail={detail} onRestore={onRestore} />)
    await userEvent.click(screen.getByRole('button', { name: 'Restore version 2' }))
    expect(onRestore).toHaveBeenCalledWith(versions[1])
    rerender(<VersionPanel {...base} selectedRev={2} detail={detail} online={false} />)
    expect(screen.getByRole('button', { name: 'Restore version 2' })).toBeDisabled()
    expect(screen.getByText('Restoring needs a connection.')).toBeInTheDocument()
    rerender(<VersionPanel {...base} selectedRev={3} detail={{ ...detail, rev: 3 }} />)
    expect(screen.getByRole('button', { name: 'Restore version 3' })).toBeDisabled()
  })

  it('compares an old version with the current text in words', () => {
    const detail = {
      rev: 2,
      title: 'T',
      body_md: 'a\nold line',
      source: 'manual' as const,
      created_at: '2026-10-04T10:00:00Z',
    }
    render(<VersionPanel {...base} selectedRev={2} detail={detail} mode="compare" currentBody={'a\nnew line'} />)
    const region = screen.getByRole('region', { name: 'Differences from the current text' })
    expect(region).toHaveTextContent('Then only')
    expect(region).toHaveTextContent('Now only')
  })
})
