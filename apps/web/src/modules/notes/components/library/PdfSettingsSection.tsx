import { Alert, Button, Card, Label, SegmentedControl, SwatchPicker, Switch, UsageBar } from '@artha/design-system'
import type { ReactNode } from 'react'

import type { OcrLang, PageTone } from '../../lib/document-types'
import { formatBytes } from '../../lib/format'
import {
  COLOR_KEYS,
  type ColorKey,
  type NotesSettings,
  type NotesSettingsPatch,
  type OcrDefault,
} from '../../lib/library-types'
import { resetDateText } from '../../lib/ocr-copy'
import type { Usage } from '../../lib/types'
import { LegendEditor } from './LegendEditor'

const TONES: ReadonlyArray<{ value: PageTone; label: string }> = [
  { value: 'original', label: 'Original' },
  { value: 'paper', label: 'Paper' },
  { value: 'night', label: 'Night' },
]
const OCR_DEFAULTS: ReadonlyArray<{ value: OcrDefault; label: string }> = [
  { value: 'ask', label: 'Ask me' },
  { value: 'always', label: 'Always' },
  { value: 'never', label: 'Never' },
]

function Row({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      {hint ? <p className="text-sm text-muted-foreground">{hint}</p> : null}
      {children}
    </div>
  )
}

interface PdfSettingsSectionProps {
  settings: NotesSettings
  saving?: boolean
  onChange: (patch: NotesSettingsPatch) => void
}

/** Reading and OCR preferences: colour names, default colour, page tone, finger draws, and what OCR does after an upload. */
export function PdfSettingsSection({ settings, saving, onChange }: PdfSettingsSectionProps) {
  const hindi = settings.capabilities?.ocr_hindi !== false
  return (
    <Card className="space-y-6 p-6">
      <h2 className="font-display text-xl font-bold">PDF reading</h2>
      <LegendEditor
        key={COLOR_KEYS.map((k) => settings.color_legend[k]).join('|')}
        legend={settings.color_legend}
        saving={saving}
        onSave={(color_legend) => onChange({ color_legend })}
      />
      <Row title="Default highlight colour" hint="The colour a new highlight starts with.">
        <SwatchPicker
          label="Default highlight colour"
          showNames
          value={settings.default_color}
          options={COLOR_KEYS.map((key) => ({ key, name: settings.color_legend[key] }))}
          onValueChange={(key) => onChange({ default_color: key as ColorKey })}
        />
      </Row>
      <Row title="Page tone" hint="How PDF pages look while you read. Night suits dark rooms.">
        <SegmentedControl
          label="Page tone"
          value={settings.page_tone}
          options={TONES}
          onValueChange={(page_tone) => onChange({ page_tone })}
        />
      </Row>
      <div className="flex items-start gap-3">
        <Switch
          id="notes-finger-draws"
          checked={settings.finger_draws}
          onCheckedChange={(finger_draws) => onChange({ finger_draws })}
          className="mt-0.5"
        />
        <div className="min-w-0 space-y-1">
          <Label htmlFor="notes-finger-draws">Draw with my finger</Label>
          <p className="text-sm text-muted-foreground">
            Off by default so a finger scrolls the page. A stylus always draws.
          </p>
        </div>
      </div>
      <Row title="Scanned PDFs" hint="OCR makes a scanned PDF searchable. It uses your monthly OCR pages.">
        <SegmentedControl
          label="When a scanned PDF is added"
          value={settings.ocr_default}
          options={OCR_DEFAULTS}
          onValueChange={(ocr_default) => onChange({ ocr_default })}
        />
        <SegmentedControl<OcrLang>
          label="OCR language"
          value={settings.ocr_lang}
          options={[
            { value: 'eng', label: 'English' },
            ...(hindi ? [{ value: 'eng+hin' as const, label: 'English and Hindi' }] : []),
          ]}
          onValueChange={(ocr_lang) => onChange({ ocr_lang })}
        />
      </Row>
    </Card>
  )
}

interface PdfUsageProps {
  usage: Usage
  onManageStorage: () => void
}

/** Storage, PDFs, OCR pages and exports with the numbers written out; "Storage full" offers Manage storage. */
export function PdfUsage({ usage, onManageStorage }: PdfUsageProps) {
  const l = usage.limits
  const used = usage.used
  const storageLimit = (l.max_storage_mb ?? 0) * 1024 * 1024
  const storageFull = storageLimit > 0 && used.storage_bytes >= storageLimit
  const reset = resetDateText(usage.resets_on)
  return (
    <Card className="space-y-4 p-6">
      <h2 className="font-display text-xl font-bold">PDF space and monthly allowance</h2>
      <UsageBar
        label="PDF storage"
        used={used.storage_bytes}
        limit={storageLimit}
        format={formatBytes}
        fullText="Storage full"
      />
      {storageFull ? (
        <Alert variant="error">
          <span className="flex flex-wrap items-center gap-3">
            <span>Storage full. New PDFs cannot be added until you free some space. Your notes keep working.</span>
            <Button size="sm" variant="outline" onClick={onManageStorage}>
              Manage storage
            </Button>
          </span>
        </Alert>
      ) : (
        <Button variant="outline" size="sm" onClick={onManageStorage}>
          Manage storage
        </Button>
      )}
      <UsageBar label="PDFs" used={used.documents ?? 0} limit={l.max_documents ?? 0} fullText="PDF limit reached" />
      <UsageBar
        label="OCR pages this month"
        used={used.ocr_pages ?? 0}
        limit={l.ocr_pages_per_month ?? 0}
        unit="pages"
        fullText="OCR pages used up"
      />
      <UsageBar
        label="Exports this month"
        used={used.exports ?? 0}
        limit={l.exports_per_month ?? 0}
        fullText="Export limit reached"
      />
      {reset ? <p className="text-sm text-muted-foreground">Monthly allowances reset on {reset}.</p> : null}
    </Card>
  )
}
