import { Button, Check, Plus, TextField } from '@artha/design-system'
import { useState } from 'react'

import type { Tag } from '../lib/types'

interface TagEditorProps {
  tags: readonly Tag[]
  selectedIds: readonly string[]
  onChange: (ids: string[]) => void
  /** Makes a new tag and resolves with it (null when it could not be made). */
  onCreate: (name: string) => Promise<Tag | undefined>
  /** Why a new tag cannot be made right now ("Tags need a connection"). */
  createDisabledReason?: string
}

/** Pick tags from your own list, or make one. Each tag is a toggle button, so state is text and `aria-pressed`. */
export function TagEditor({ tags, selectedIds, onChange, onCreate, createDisabledReason }: TagEditorProps) {
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const selected = new Set(selectedIds)

  const toggle = (id: string) => onChange(selected.has(id) ? selectedIds.filter((x) => x !== id) : [...selectedIds, id])

  const create = async () => {
    const trimmed = name.trim()
    if (!trimmed || busy) return
    setBusy(true)
    const tag = await onCreate(trimmed)
    setBusy(false)
    if (tag) {
      setName('')
      if (!selected.has(tag.id)) onChange([...selectedIds, tag.id])
    }
  }

  return (
    <div className="space-y-3">
      {tags.length === 0 ? (
        <p className="text-sm text-muted-foreground">You have no tags yet. Make one below.</p>
      ) : (
        <ul aria-label="Your tags" className="flex flex-wrap gap-2">
          {tags.map((tag) => (
            <li key={tag.id}>
              <button
                type="button"
                aria-pressed={selected.has(tag.id)}
                onClick={() => toggle(tag.id)}
                className="inline-flex min-h-11 items-center gap-1.5 rounded-full border border-input bg-card px-4 text-sm font-medium outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40 aria-pressed:border-primary aria-pressed:bg-secondary aria-pressed:text-secondary-foreground"
              >
                {selected.has(tag.id) ? <Check aria-hidden className="size-4" /> : null}
                {tag.name}
              </button>
            </li>
          ))}
        </ul>
      )}
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          void create()
        }}
      >
        <div className="min-w-0 flex-1">
          <TextField
            label="New tag"
            value={name}
            maxLength={30}
            onChange={(e) => setName(e.target.value)}
            disabled={Boolean(createDisabledReason)}
            hint={createDisabledReason}
          />
        </div>
        <Button type="submit" variant="outline" disabled={busy || !name.trim() || Boolean(createDisabledReason)}>
          <Plus aria-hidden /> Add tag
        </Button>
      </form>
    </div>
  )
}
