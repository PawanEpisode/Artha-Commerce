import {
  Button,
  Eraser,
  FileDropzone,
  FloatingToolbar,
  FloatingToolbarButton,
  FloatingToolbarSeparator,
  Hand,
  Highlighter,
  MousePointer2,
  PenLine,
  SegmentedControl,
  StickyNote,
  type SwatchKey,
  type SwatchOption,
  SwatchPicker,
  SwatchShape,
  Type,
  Underline,
} from '@artha/design-system'
import { useRef, useState } from 'react'

/** The student's own legend: names come from the app, never from the colour. */
const HIGHLIGHTS: SwatchOption[] = [
  { key: 'y', name: 'Formula or rule' },
  { key: 'g', name: 'Definition' },
  { key: 'b', name: 'Example' },
  { key: 'p', name: 'Doubt' },
  { key: 'o', name: 'Exam favourite' },
]
const PENS: SwatchOption[] = [
  { key: 'i1', name: 'Graphite' },
  { key: 'i2', name: 'Red pen' },
  { key: 'i3', name: 'Blue pen' },
  { key: 'i4', name: 'Green pen' },
  { key: 'i5', name: 'Purple pen' },
]
const LONG_LEGEND: SwatchOption[] = [
  { key: 'y', name: 'Section 17(5) blocked credits: read again before the revision test' },
  { key: 'g', name: 'Definition' },
  { key: 'p', name: 'Doubt to ask on Saturday', disabled: true },
]

const TONES = [
  { tone: 'original', title: 'Original page' },
  { tone: 'paper', title: 'Paper page' },
  { tone: 'night', title: 'Night page' },
] as const

type Tool = 'select' | 'highlight' | 'underline' | 'pen' | 'text' | 'note' | 'erase' | 'pan'
const TOOLS: Array<{ value: Tool; label: string; icon: React.ReactNode }> = [
  { value: 'select', label: 'Select', icon: <MousePointer2 aria-hidden /> },
  { value: 'highlight', label: 'Highlight', icon: <Highlighter aria-hidden /> },
  { value: 'underline', label: 'Underline', icon: <Underline aria-hidden /> },
  { value: 'pen', label: 'Pen', icon: <PenLine aria-hidden /> },
  { value: 'text', label: 'Text', icon: <Type aria-hidden /> },
  { value: 'note', label: 'Note', icon: <StickyNote aria-hidden /> },
  { value: 'erase', label: 'Eraser', icon: <Eraser aria-hidden /> },
  { value: 'pan', label: 'Move', icon: <Hand aria-hidden /> },
]

const HIGHLIGHT_CLASS: Record<string, string> = {
  y: 'bg-highlight-yellow/(--mark-fill-alpha) border-highlight-yellow-edge',
  g: 'bg-highlight-green/(--mark-fill-alpha) border-highlight-green-edge',
  b: 'bg-highlight-blue/(--mark-fill-alpha) border-highlight-blue-edge',
  p: 'bg-highlight-pink/(--mark-fill-alpha) border-highlight-pink-edge',
  o: 'bg-highlight-orange/(--mark-fill-alpha) border-highlight-orange-edge',
}

/** A sample page in one tone: highlights blend (multiply, or screen at night), the edge stroke keeps 3:1, pens draw normally. */
function PageTone({ tone, title }: { tone: (typeof TONES)[number]['tone']; title: string }) {
  return (
    <div
      data-page-tone={tone}
      className="page-surface min-w-0 space-y-2 rounded-xl border border-border p-4 text-sm leading-relaxed"
    >
      <p className="text-xs font-semibold">{title}</p>
      <p>
        Input tax credit is{' '}
        {(['y', 'g', 'b', 'p', 'o'] as const).map((key, i) => (
          <span key={key}>
            <span className={`mark-blend border-b-2 ${HIGHLIGHT_CLASS[key]}`}>
              {['blocked', 'credit', 'reverse', 'supply', 'invoice'][i]}
            </span>{' '}
          </span>
        ))}
        when the rule applies.
      </p>
      <svg viewBox="0 0 200 24" className="h-6 w-full" fill="none" strokeWidth="3" strokeLinecap="round" aria-hidden>
        <path d="M4 12 Q 14 2 24 12 T 44 12" className="stroke-ink-1" />
        <path d="M54 12 Q 64 2 74 12 T 94 12" className="stroke-ink-2" />
        <path d="M104 12 Q 114 2 124 12 T 144 12" className="stroke-ink-3" />
        <path d="M154 12 Q 164 2 174 12 T 194 12" className="stroke-ink-4" />
        <path d="M4 20 H 60" className="stroke-ink-5" />
      </svg>
    </div>
  )
}

/** Annotation primitives for the PDF editor (F-03): page tones and mark tokens, SwatchPicker, FloatingToolbar, FileDropzone, tool pill. */
export function AnnotationPrimitivesShowcase() {
  const [highlight, setHighlight] = useState<SwatchKey>('y')
  const [pen, setPen] = useState<SwatchKey>('i2')
  const [applied, setApplied] = useState('Nothing applied yet')
  const [tool, setTool] = useState<Tool>('highlight')
  const [toolbarOpen, setToolbarOpen] = useState(false)
  const opener = useRef<HTMLButtonElement>(null)
  const selection = useRef<HTMLSpanElement>(null)
  const [picked, setPicked] = useState('No file chosen')

  return (
    <>
      <section className="space-y-4">
        <h2 className="text-xl font-bold">Page tones and mark colours</h2>
        <p className="text-sm text-muted-foreground">
          Put <code>data-page-tone=&quot;original|paper|night&quot;</code> and <code>page-surface</code> on the page
          wrapper and <code>mark-blend</code> on a mark layer: highlights multiply on original and paper and screen on
          night (<code>--mark-blend</code>). Tokens: <code>bg-highlight-yellow</code> (also green, blue, pink, orange),{' '}
          <code>border-highlight-yellow-edge</code> (the 3:1 stroke and underline colour), <code>stroke-ink-1</code> to{' '}
          <code>ink-5</code>, <code>bg-page-original|paper|night</code>. Fills hold 1.5:1 (a pale fill cannot reach
          3:1); edges and pens hold 3:1 on every page tone in every theme (<code>check:contrast</code>).
        </p>
        <div className="grid gap-3 md:grid-cols-3">
          {TONES.map((t) => (
            <PageTone key={t.tone} {...t} />
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-bold">Swatch picker</h2>
        <p className="text-sm text-muted-foreground">
          Props: <code>label</code>, <code>options</code> (<code>key</code> y g b p o i1 to i5, <code>name</code> from
          the student&apos;s legend, <code>disabled</code>), <code>value</code> or <code>defaultValue</code>,{' '}
          <code>onValueChange</code>, <code>onSelect</code> (also on the colour already chosen), <code>size</code>{' '}
          sm|md|lg, <code>showNames</code>. A shape and a check mark carry the meaning, not only the colour. Arrow keys
          move the choice.
        </p>
        <div className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-2">
            <p className="text-sm font-semibold">Highlights, size md</p>
            <SwatchPicker
              label="Highlight colour"
              options={HIGHLIGHTS}
              value={highlight}
              onValueChange={setHighlight}
              onSelect={(key) => setApplied(`Applied ${key}`)}
            />
            <p role="status" className="text-sm text-muted-foreground">
              {applied}
            </p>
          </div>
          <div className="space-y-2">
            <p className="text-sm font-semibold">Pens, size lg</p>
            <SwatchPicker label="Pen colour" options={PENS} value={pen} onValueChange={setPen} size="lg" />
          </div>
          <div className="space-y-2">
            <p className="text-sm font-semibold">Size sm (target stays 44 px)</p>
            <SwatchPicker label="Highlight colour, small" options={HIGHLIGHTS} defaultValue="g" size="sm" />
          </div>
          <div className="space-y-2">
            <p className="text-sm font-semibold">Nothing selected, one disabled, names shown</p>
            <SwatchPicker label="Legend" options={LONG_LEGEND} showNames className="flex-col items-stretch" />
          </div>
        </div>
        <div className="space-y-2">
          <p className="text-sm font-semibold">Shapes on the page, and the pulse</p>
          <p className="text-sm text-muted-foreground">
            <code>SwatchShape</code> draws the shape that goes with a colour (<code>swatch</code> y g b p o, i1 to i5)
            so a mark on the page never relies on colour alone. <code>mark-pulse</code> rings a mark found from the list
            once; with reduced motion it is a still ring.
          </p>
          <div className="flex flex-wrap items-center gap-4">
            {(['y', 'g', 'b', 'p', 'o'] as const).map((key) => (
              <span key={key} className="size-6 text-highlight-yellow-edge">
                <SwatchShape swatch={key} />
              </span>
            ))}
            <span className="mark-pulse inline-block rounded-sm bg-highlight-yellow px-2 py-1 text-sm text-swatch-marker">
              Found from the list
            </span>
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-bold">Floating toolbar</h2>
        <p className="text-sm text-muted-foreground">
          Props: <code>open</code>, <code>onOpenChange</code>, <code>anchor</code> (rect, element or function),{' '}
          <code>label</code>, <code>scrollContainer</code>, <code>side</code>, <code>returnFocusRef</code>,{' '}
          <code>autoFocus</code>, <code>focusKey</code> (default F10 moves focus into it). Arrow keys, Home and End move
          inside; Escape closes and returns focus to the button below.
        </p>
        <p
          data-page-tone="original"
          className="page-surface max-w-prose rounded-xl border border-border p-3 text-sm leading-relaxed"
        >
          Under section 17(5) credit on{' '}
          <span
            ref={selection}
            className="mark-blend border-b-2 border-highlight-yellow-edge bg-highlight-yellow/(--mark-fill-alpha)"
          >
            motor vehicles and conveyance
          </span>{' '}
          is blocked unless the supplier is in the same line of business.
        </p>
        <Button ref={opener} variant="outline" aria-expanded={toolbarOpen} onClick={() => setToolbarOpen((v) => !v)}>
          {toolbarOpen ? 'Hide selection toolbar' : 'Show selection toolbar'}
        </Button>
        <FloatingToolbar
          open={toolbarOpen}
          onOpenChange={setToolbarOpen}
          anchor={() => selection.current}
          label="Selection tools"
          returnFocusRef={opener}
        >
          <FloatingToolbarButton aria-label="Highlight">
            <Highlighter aria-hidden />
          </FloatingToolbarButton>
          <FloatingToolbarButton aria-label="Underline">
            <Underline aria-hidden />
          </FloatingToolbarButton>
          <FloatingToolbarButton aria-label="Add note">
            <StickyNote aria-hidden />
          </FloatingToolbarButton>
          <FloatingToolbarSeparator />
          <SwatchPicker
            label="Highlight colour"
            options={HIGHLIGHTS}
            value={highlight}
            onValueChange={setHighlight}
            size="sm"
          />
        </FloatingToolbar>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-bold">Tool pill (SegmentedControl with icons)</h2>
        <p className="text-sm text-muted-foreground">
          One active tool. <code>icon</code> on each option, <code>size=&quot;lg&quot;</code> for 44 px targets,{' '}
          <code>iconOnlyOnMobile</code> keeps the label as the accessible name below 640 px.
        </p>
        <div className="max-w-full overflow-x-auto">
          <SegmentedControl
            label="Tool"
            value={tool}
            onValueChange={setTool}
            options={TOOLS}
            size="lg"
            iconOnlyOnMobile
          />
        </div>
        <p role="status" className="text-sm text-muted-foreground">
          Active tool: {tool}
        </p>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-bold">File dropzone</h2>
        <p className="text-sm text-muted-foreground">
          Props: <code>onFiles</code>, <code>onReject</code>, <code>accept</code>, <code>maxSizeBytes</code>,{' '}
          <code>multiple</code>, <code>title</code>, <code>hint</code>, <code>messages</code>, <code>error</code>,{' '}
          <code>disabled</code>, <code>reason</code>. No upload logic inside; tab to it and press Enter or Space.
        </p>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <FileDropzone
              accept=".pdf,application/pdf"
              maxSizeBytes={200 * 1024 * 1024}
              hint="PDF, up to 200 MB"
              messages={{ type: 'Only PDF files are accepted.', size: 'That PDF is over 200 MB.' }}
              onFiles={(files) => setPicked(`${files.length} file ready`)}
            />
            <p role="status" className="text-sm text-muted-foreground">
              {picked}
            </p>
          </div>
          <FileDropzone
            multiple
            hint="PDF or images, up to 20 files"
            error="Upload failed. Check your connection and try again."
            onFiles={() => undefined}
          />
          <FileDropzone
            disabled
            reason="Storage full. Free up space to add more."
            hint="PDF, up to 200 MB"
            onFiles={() => undefined}
          />
          <FileDropzone
            title="A very long call to action that has to wrap inside a narrow phone screen without any sideways scrolling"
            hint="docs-with-a-very-long-unbroken-description-of-the-limits-that-keeps-going-and-going.pdf"
            onFiles={() => undefined}
          />
        </div>
      </section>
    </>
  )
}
