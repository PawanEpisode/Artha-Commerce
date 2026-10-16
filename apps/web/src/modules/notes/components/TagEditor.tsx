import { Button, Check, Input, Plus } from '@artha/design-system'
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
    <div className="space-y-2">
      {tags.length === 0 ? (
        <p className="text-[13px] text-muted-foreground">You have no tags yet. Make one below.</p>
      ) : (
        <ul aria-label="Your tags" className="flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <li key={tag.id}>
              <button
                type="button"
                aria-pressed={selected.has(tag.id)}
                onClick={() => toggle(tag.id)}
                className="inline-flex min-h-6 items-center gap-1 rounded-md border border-input bg-card px-2 text-xs font-medium outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 aria-pressed:border-primary aria-pressed:bg-secondary aria-pressed:text-secondary-foreground pointer-coarse:min-h-10"
              >
                {selected.has(tag.id) ? <Check aria-hidden className="size-3" /> : null}
                {tag.name}
              </button>
            </li>
          ))}
        </ul>
      )}
      <form
        className="space-y-1"
        onSubmit={(event) => {
          event.preventDefault()
          void create()
        }}
      >
        <div className="flex items-center gap-1.5">
          <label htmlFor="new-tag" className="sr-only">
            New tag
          </label>
          <Input
            id="new-tag"
            placeholder="New tag"
            value={name}
            maxLength={30}
            onChange={(e) => setName(e.target.value)}
            disabled={Boolean(createDisabledReason)}
            aria-describedby={createDisabledReason ? 'new-tag-hint' : undefined}
            className="min-w-0 flex-1"
          />
          <Button
            type="submit"
            variant="outline"
            size="sm"
            disabled={busy || !name.trim() || Boolean(createDisabledReason)}
          >
            <Plus aria-hidden /> Add tag
          </Button>
        </div>
        {createDisabledReason ? (
          <p id="new-tag-hint" className="text-xs text-muted-foreground">
            {createDisabledReason}
          </p>
        ) : null}
      </form>
    </div>
  )
}
