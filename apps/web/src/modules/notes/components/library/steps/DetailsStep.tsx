import { SelectField, TextField } from '@artha/design-system'

import { EDITION_MAX, TITLE_MAX, titleProblem } from '../../../lib/document-draft'
import type { SourceKind } from '../../../lib/document-types'
import { SOURCE_KINDS, SOURCE_LABEL } from '../../../lib/library-schema'
import type { Tag } from '../../../lib/types'
import { TagEditor } from '../../TagEditor'

export interface DetailsValue {
  title: string
  source_kind: SourceKind
  edition_label: string
  tag_ids: string[]
}

interface DetailsStepProps {
  value: DetailsValue
  onChange: (change: Partial<DetailsValue>) => void
  tags: readonly Tag[]
  onCreateTag: (name: string) => Promise<Tag | undefined>
  online: boolean
  /** Show the title's mistake only after the student has had the chance to type one. */
  showProblems?: boolean
}

const PRIVATE_KINDS = new Set<SourceKind>(['coaching', 'institute_material'])

/** What the PDF is: its title, where it came from, an edition and tags. All the student has to say is the title. */
export function DetailsStep({ value, onChange, tags, onCreateTag, online, showProblems = true }: DetailsStepProps) {
  const isPrivate = PRIVATE_KINDS.has(value.source_kind)
  return (
    <div className="space-y-6">
      <TextField
        label="Title"
        value={value.title}
        maxLength={TITLE_MAX}
        error={showProblems ? (titleProblem(value.title) ?? undefined) : undefined}
        onChange={(e) => onChange({ title: e.target.value })}
      />

      <div className="grid gap-2">
        <label htmlFor="doc-source" className="text-sm font-semibold">
          Where is it from?
        </label>
        <SelectField
          id="doc-source"
          value={value.source_kind}
          onValueChange={(source_kind) => onChange({ source_kind: source_kind as SourceKind })}
          options={SOURCE_KINDS.map((k) => ({ value: k, label: SOURCE_LABEL[k] }))}
        />
        <p className="text-sm text-muted-foreground">
          {isPrivate ? (
            <>
              <strong className="font-semibold text-foreground">Private to you.</strong> Coaching and institute material
              is never shared: only your own notes and marks can be shared later.
            </>
          ) : (
            'Only your own notes and marks can be shared later, never the PDF itself.'
          )}
        </p>
      </div>

      <TextField
        label="Edition (optional)"
        hint="For example: May 2027 attempt, 2nd edition."
        value={value.edition_label}
        maxLength={EDITION_MAX}
        onChange={(e) => onChange({ edition_label: e.target.value })}
      />

      <div className="grid gap-2">
        <span className="text-sm font-semibold">Tags (optional)</span>
        <TagEditor
          tags={tags}
          selectedIds={value.tag_ids}
          onChange={(tag_ids) => onChange({ tag_ids })}
          onCreate={onCreateTag}
          createDisabledReason={online ? undefined : 'New tags need a connection.'}
        />
      </div>
    </div>
  )
}
