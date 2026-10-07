import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { NotesSettings } from '../../lib/library-types'
import { makeDocument } from '../../lib/testing-documents'
import { MIB } from '../../lib/upload-check'
import { LegendEditor } from './LegendEditor'
import { PdfSettingsSection, PdfUsage } from './PdfSettingsSection'
import { TrashedDocuments } from './TrashedDocuments'

const legend = { y: 'Important', g: 'Formula', b: 'Section', p: 'Doubt', o: 'Example' }
const settings: NotesSettings = {
  color_legend: legend,
  legend_schema: 1,
  default_color: 'y',
  page_tone: 'original',
  finger_draws: false,
  ocr_default: 'ask',
  ocr_lang: 'eng',
  capabilities: { recall: false, ocr_hindi: true, ai_ocr: false },
}

describe('LegendEditor', () => {
  it('saves five tidied names together', async () => {
    const onSave = vi.fn()
    render(<LegendEditor legend={legend} onSave={onSave} />)
    expect(screen.getByRole('button', { name: 'Save names' })).toBeDisabled()
    const first = screen.getByLabelText('Name for colour 1')
    await userEvent.clear(first)
    await userEvent.type(first, '  Must   know ')
    await userEvent.click(screen.getByRole('button', { name: 'Save names' }))
    expect(onSave).toHaveBeenCalledWith({ ...legend, y: 'Must know' })
  })

  it('refuses an empty, a long and a repeated name, inline, and does not save', async () => {
    const onSave = vi.fn()
    render(<LegendEditor legend={legend} onSave={onSave} />)
    await userEvent.clear(screen.getByLabelText('Name for colour 1'))
    const second = screen.getByLabelText('Name for colour 2')
    await userEvent.clear(second)
    await userEvent.type(second, 'doubt')
    await userEvent.click(screen.getByRole('button', { name: 'Save names' }))
    expect(screen.getByText('Give this colour a name.')).toBeInTheDocument()
    expect(screen.getAllByText('Another colour already has this name.')).toHaveLength(2)
    expect(onSave).not.toHaveBeenCalled()
  })

  it('undoes unsaved changes', async () => {
    render(<LegendEditor legend={legend} onSave={() => undefined} />)
    await userEvent.type(screen.getByLabelText('Name for colour 3'), 'x')
    await userEvent.click(screen.getByRole('button', { name: 'Undo changes' }))
    expect(screen.getByLabelText('Name for colour 3')).toHaveValue('Section')
  })
})

describe('PdfSettingsSection', () => {
  it('changes the default colour, tone, finger drawing and OCR choices', async () => {
    const onChange = vi.fn()
    render(<PdfSettingsSection settings={settings} onChange={onChange} />)
    await userEvent.click(screen.getByRole('radio', { name: 'Formula' }))
    expect(onChange).toHaveBeenLastCalledWith({ default_color: 'g' })
    await userEvent.click(screen.getByRole('radio', { name: 'Paper' }))
    expect(onChange).toHaveBeenLastCalledWith({ page_tone: 'paper' })
    await userEvent.click(screen.getByRole('switch', { name: 'Draw with my finger' }))
    expect(onChange).toHaveBeenLastCalledWith({ finger_draws: true })
    await userEvent.click(screen.getByRole('radio', { name: 'Always' }))
    expect(onChange).toHaveBeenLastCalledWith({ ocr_default: 'always' })
    await userEvent.click(screen.getByRole('radio', { name: 'English and Hindi' }))
    expect(onChange).toHaveBeenLastCalledWith({ ocr_lang: 'eng+hin' })
  })

  it('hides Hindi when the server cannot do it', () => {
    render(
      <PdfSettingsSection
        settings={{ ...settings, capabilities: { recall: false, ocr_hindi: false, ai_ocr: false } }}
        onChange={() => undefined}
      />,
    )
    expect(screen.queryByRole('radio', { name: 'English and Hindi' })).not.toBeInTheDocument()
  })
})

const usage = (storage: number) =>
  ({
    plan: 'free',
    limits: { max_storage_mb: 500, max_documents: 100, ocr_pages_per_month: 300, exports_per_month: 10 },
    used: { storage_bytes: storage, documents: 7, ocr_pages: 120, exports: 2, notes: 0, tags: 0 },
    resets_on: '2026-11-01',
  }) as never

describe('PdfUsage', () => {
  it('writes every meter out in text with the reset date', () => {
    render(<PdfUsage usage={usage(412 * MIB)} onManageStorage={() => undefined} />)
    expect(screen.getByRole('meter', { name: 'PDF storage' })).toHaveAttribute('aria-valuetext', '412 MB of 500 MB')
    expect(screen.getByRole('meter', { name: 'PDFs' })).toHaveAttribute('aria-valuetext', '7 of 100')
    expect(screen.getByRole('meter', { name: 'OCR pages this month' })).toHaveAttribute(
      'aria-valuetext',
      '120 of 300 pages',
    )
    expect(screen.getByRole('meter', { name: 'Exports this month' })).toHaveAttribute('aria-valuetext', '2 of 10')
    expect(screen.getByText(/reset on 1 Nov(ember)? 2026/)).toBeInTheDocument()
  })

  it('storage full says so and Manage storage opens the sheet', async () => {
    const onManageStorage = vi.fn()
    render(<PdfUsage usage={usage(500 * MIB)} onManageStorage={onManageStorage} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Storage full')
    await userEvent.click(screen.getByRole('button', { name: 'Manage storage' }))
    expect(onManageStorage).toHaveBeenCalled()
  })
})

describe('TrashedDocuments', () => {
  const doc = makeDocument({
    title: 'Old scan',
    status: 'ready',
    deleted_at: '2026-10-01T00:00:00Z',
    purge_after: '2026-10-31T00:00:00Z',
    bytes: 5 * MIB,
  })
  it('restores and deletes now, with names that say which PDF', async () => {
    const onRestore = vi.fn()
    const onDeleteNow = vi.fn()
    render(<TrashedDocuments items={[doc]} online onRestore={onRestore} onDeleteNow={onDeleteNow} />)
    await userEvent.click(screen.getByRole('button', { name: 'Restore Old scan' }))
    expect(onRestore).toHaveBeenCalledWith(doc)
    await userEvent.click(screen.getByRole('button', { name: 'Delete Old scan now' }))
    expect(onDeleteNow).toHaveBeenCalledWith(doc)
    expect(screen.getByText(/5.0 MB\. Deleted/)).toBeInTheDocument()
  })
  it('needs a connection', () => {
    render(<TrashedDocuments items={[doc]} online={false} onRestore={() => undefined} onDeleteNow={() => undefined} />)
    expect(screen.getByRole('button', { name: 'Restore Old scan' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Delete Old scan now' })).toBeDisabled()
  })
})
