import {
  Bold,
  Button,
  cn,
  Code,
  Heading2,
  ImageIcon,
  Italic,
  List,
  ListOrdered,
  ListTodo,
  type LucideIcon,
  SegmentedControl,
  Sigma,
  Table,
  Textarea,
} from '@artha/design-system'
import { useDeferredValue, useLayoutEffect, useRef, useState } from 'react'

import {
  bulletList,
  cycleHeading,
  type Edit,
  insertFormula,
  insertImage,
  insertTable,
  numberedList,
  taskList,
  toggleInline,
} from './edit-actions'
import { PROFILES, type RichTextProfile } from './profiles'
import { RichText } from './RichText'
import { charCount } from './text'

export interface PickedImage {
  attachmentId: string
  /** Empty string means the student marked the image decorative. */
  alt: string
}

interface RichTextEditorProps {
  value: string
  onChange: (value: string) => void
  /** Accessible name of the text box ("Note text"). */
  label: string
  profile?: RichTextProfile
  placeholder?: string
  readOnly?: boolean
  /** Opens whatever picks and uploads an image and resolves with it, or null when cancelled. Hides the button when absent. */
  onPickImage?: () => Promise<PickedImage | null>
  /** When set the image button is disabled and this says why ("Images need a connection"). */
  imageDisabledReason?: string
  resolveImage?: (attachmentId: string) => string | undefined
  textareaId?: string
  describedBy?: string
  className?: string
}

interface ToolbarItem {
  key: string
  label: string
  icon: LucideIcon
  run: (edit: Edit) => Edit
}

const WARN_AT = 0.9

/**
 * Markdown plus KaTeX editor: a toolbar (headings, lists, table, formula, task list, image), the text box and a live
 * preview in the shared reading style. Below the `lg` breakpoint the student switches between Write and Preview; on a
 * wide screen they sit side by side. The value is always plain Markdown.
 */
export function RichTextEditor({
  value,
  onChange,
  label,
  profile = 'note',
  placeholder = 'Start typing, or paste a formula',
  readOnly = false,
  onPickImage,
  imageDisabledReason,
  resolveImage,
  textareaId,
  describedBy,
  className,
}: RichTextEditorProps) {
  const rules = PROFILES[profile]
  const ref = useRef<HTMLTextAreaElement>(null)
  const pending = useRef<{ start: number; end: number } | null>(null)
  const [view, setView] = useState<'write' | 'preview'>('write')
  const [roving, setRoving] = useState(0)
  const preview = useDeferredValue(value)
  const chars = charCount(value)
  const nearLimit = chars >= rules.maxChars * WARN_AT

  // Put the cursor where the last toolbar action wants it, once React has written the new value.
  useLayoutEffect(() => {
    const target = pending.current
    const el = ref.current
    if (!target || !el) return
    pending.current = null
    el.focus()
    el.setSelectionRange(target.start, target.end)
  }, [value])

  const apply = (action: (edit: Edit) => Edit) => {
    const el = ref.current
    if (!el || readOnly) return
    const next = action({ value, start: el.selectionStart, end: el.selectionEnd })
    pending.current = { start: next.start, end: next.end }
    onChange(next.value)
    if (next.value === value) el.setSelectionRange(next.start, next.end)
  }

  const items: ToolbarItem[] = [
    {
      key: 'heading',
      label: 'Heading',
      icon: Heading2,
      run: (e) => cycleHeading(e, rules.headings?.[0], rules.headings?.[1]),
    },
    { key: 'bold', label: 'Bold', icon: Bold, run: (e) => toggleInline(e, '**', 'bold text') },
    { key: 'italic', label: 'Italic', icon: Italic, run: (e) => toggleInline(e, '*', 'italic text') },
    { key: 'code', label: 'Code', icon: Code, run: (e) => toggleInline(e, '`', 'code') },
    { key: 'bullets', label: 'Bulleted list', icon: List, run: bulletList },
    { key: 'numbers', label: 'Numbered list', icon: ListOrdered, run: numberedList },
    ...(rules.taskLists ? [{ key: 'tasks', label: 'Task list', icon: ListTodo, run: taskList }] : []),
    { key: 'table', label: 'Table', icon: Table, run: (e) => insertTable(e) },
    {
      key: 'formula',
      label: 'Formula',
      icon: Sigma,
      run: (e) => insertFormula(e, e.value.slice(e.start, e.end).includes('\n')),
    },
  ]

  const addImage = async () => {
    if (!onPickImage || readOnly) return
    const el = ref.current
    const at = { start: el?.selectionStart ?? value.length, end: el?.selectionEnd ?? value.length }
    const picked = await onPickImage()
    if (!picked) return
    const next = insertImage({ value, ...at }, picked.attachmentId, picked.alt)
    pending.current = { start: next.start, end: next.end }
    onChange(next.value)
  }

  const buttons = items.length + (onPickImage ? 1 : 0)
  const onToolbarKey = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const move = { ArrowRight: 1, ArrowLeft: -1 }[event.key as 'ArrowRight' | 'ArrowLeft']
    const target =
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? buttons - 1
          : move === undefined
            ? null
            : (roving + move + buttons) % buttons
    if (target === null) return
    event.preventDefault()
    setRoving(target)
    event.currentTarget.querySelectorAll<HTMLButtonElement>('button')[target]?.focus()
  }

  return (
    <div data-slot="rich-text-editor" className={cn('space-y-3', className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        {!readOnly ? (
          <div
            role="toolbar"
            aria-label="Formatting"
            aria-controls={textareaId}
            onKeyDown={onToolbarKey}
            className="flex max-w-full flex-wrap gap-1 rounded-xl border border-border bg-card p-1"
          >
            {items.map((item, index) => (
              <Button
                key={item.key}
                type="button"
                variant="ghost"
                size="icon"
                className="size-11"
                aria-label={item.label}
                title={item.label}
                tabIndex={roving === index ? 0 : -1}
                onFocus={() => setRoving(index)}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => apply(item.run)}
              >
                <item.icon aria-hidden />
              </Button>
            ))}
            {onPickImage ? (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-11"
                aria-label="Add image"
                title={imageDisabledReason ?? 'Add image'}
                disabled={Boolean(imageDisabledReason)}
                tabIndex={roving === items.length ? 0 : -1}
                onFocus={() => setRoving(items.length)}
                onClick={() => void addImage()}
              >
                <ImageIcon aria-hidden />
              </Button>
            ) : null}
          </div>
        ) : (
          <span />
        )}
        <SegmentedControl
          className="lg:hidden"
          label="Editor view"
          value={view}
          onValueChange={setView}
          options={[
            { value: 'write', label: 'Write' },
            { value: 'preview', label: 'Preview' },
          ]}
        />
      </div>
      {imageDisabledReason && onPickImage ? (
        <p className="text-xs text-muted-foreground">{imageDisabledReason}</p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className={cn(view === 'preview' && 'hidden lg:block')}>
          <Textarea
            ref={ref}
            id={textareaId}
            aria-label={label}
            aria-describedby={describedBy}
            value={value}
            readOnly={readOnly}
            spellCheck
            placeholder={placeholder}
            onChange={(e) => onChange(e.target.value)}
            className="min-h-[45dvh] resize-y font-mono text-base leading-relaxed md:text-base"
          />
        </div>
        <section
          aria-label="Preview"
          className={cn(
            'min-h-24 min-w-0 overflow-x-auto rounded-lg border border-border bg-card px-4 py-3',
            view === 'write' && 'hidden lg:block',
          )}
        >
          {preview.trim() === '' ? (
            <p className="text-sm text-muted-foreground">The preview appears here as you type.</p>
          ) : (
            <RichText markdown={preview} profile={profile} resolveImage={resolveImage} />
          )}
        </section>
      </div>

      {nearLimit ? (
        <p
          role="status"
          className={cn('text-sm', chars > rules.maxChars ? 'font-semibold text-destructive' : 'text-muted-foreground')}
        >
          {chars.toLocaleString('en-IN')} of {rules.maxChars.toLocaleString('en-IN')} characters
          {chars > rules.maxChars ? '. Too long to save: shorten it or split it into two notes.' : '.'}
        </p>
      ) : null}
    </div>
  )
}
