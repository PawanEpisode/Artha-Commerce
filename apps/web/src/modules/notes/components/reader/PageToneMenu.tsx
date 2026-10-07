import {
  Alert,
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
  Palette,
} from '@artha/design-system'

import type { PageTone } from '../../lib/document-types'

export const TONE_LABEL: Record<PageTone, string> = { original: 'Original', paper: 'Paper', night: 'Night' }
const TONE_HELP: Record<PageTone, string> = {
  original: 'The page as printed',
  paper: 'Warm paper, easy on the eyes',
  night: 'Dark page, marks stay bright',
}

export interface PageToneMenuProps {
  tone: PageTone
  onToneChange: (tone: PageTone) => void
}

/** Original, Paper or Night. The reader puts `data-page-tone` on the pages; Night inverts the page, never the marks. */
export function PageToneMenu({ tone, onToneChange }: PageToneMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="size-11" aria-label={`Page tone: ${TONE_LABEL[tone]}`}>
          <Palette aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel>Page tone</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={tone} onValueChange={(v) => onToneChange(v as PageTone)}>
          {(Object.keys(TONE_LABEL) as PageTone[]).map((t) => (
            <DropdownMenuRadioItem key={t} value={t} className="min-h-11 flex-col items-start gap-0">
              <span className="font-semibold">{TONE_LABEL[t]}</span>
              <span className="text-xs text-muted-foreground">{TONE_HELP[t]}</span>
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export interface NightToneHintProps {
  onAccept: () => void
  onDismiss: () => void
}

/** Offered once when the app is in the Dark theme and the page is bright. */
export function NightToneHint({ onAccept, onDismiss }: NightToneHintProps) {
  return (
    <Alert variant="info">
      <div className="flex flex-wrap items-center gap-2">
        <span className="min-w-48 flex-1">Reading at night? Try the Night page tone.</span>
        <Button size="sm" onClick={onAccept} className="min-h-11">
          Use Night
        </Button>
        <Button size="sm" variant="ghost" onClick={onDismiss} className="min-h-11">
          Not now
        </Button>
      </div>
    </Alert>
  )
}
