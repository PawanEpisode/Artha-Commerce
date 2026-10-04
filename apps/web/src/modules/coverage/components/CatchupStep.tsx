import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
  Alert,
  Button,
  Checkbox,
  Label,
  LoaderCircle,
  Skeleton,
  Switch,
} from '@artha/design-system'

import type { ChapterRow, SubjectRow } from '../lib/types'

export interface CatchupSubject {
  subject: SubjectRow
  chapters: ChapterRow[] | undefined
}

interface Props {
  subjects: CatchupSubject[]
  selected: Set<string>
  alsoRevised: boolean
  pending: boolean
  error?: string
  onToggleChapter: (id: string, on: boolean) => void
  onToggleSubject: (chapterIds: string[], on: boolean) => void
  onAlsoRevised: (v: boolean) => void
  onApply: () => void
  onSkip: () => void
}

/** Step 3: quick catch-up (FR-24). Tick the chapters you have already covered, or a whole paper at once. */
export function CatchupStep({
  subjects,
  selected,
  alsoRevised,
  pending,
  error,
  onToggleChapter,
  onToggleSubject,
  onAlsoRevised,
  onApply,
  onSkip,
}: Props) {
  return (
    <div className="space-y-6">
      <p className="text-muted-foreground">
        Tick what you have already read. We will count it as read and show your starting point. You can change anything
        later.
      </p>
      <Accordion type="multiple">
        {subjects.map(({ subject, chapters }) => {
          const ids = chapters?.map((c) => c.id) ?? []
          const count = ids.filter((id) => selected.has(id)).length
          const all = ids.length > 0 && count === ids.length
          return (
            <AccordionItem key={subject.id} value={subject.id}>
              <AccordionTrigger>
                <span className="flex-1 text-left">{subject.name}</span>
                <span className="mr-2 text-sm font-normal text-muted-foreground">
                  {count} of {chapters ? ids.length : '…'} selected
                </span>
              </AccordionTrigger>
              <AccordionContent>
                {!chapters ? (
                  <Skeleton className="h-24 w-full" />
                ) : ids.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Chapters for this paper are coming soon.</p>
                ) : (
                  <div className="space-y-1">
                    <label
                      htmlFor={`all-${subject.id}`}
                      className="flex min-h-11 cursor-pointer items-center gap-3 font-semibold"
                    >
                      <Checkbox
                        id={`all-${subject.id}`}
                        checked={all ? true : count > 0 ? 'indeterminate' : false}
                        onCheckedChange={(v) => onToggleSubject(ids, v === true)}
                      />
                      Whole paper
                    </label>
                    {chapters.map((c) => (
                      <label
                        key={c.id}
                        htmlFor={`ch-${c.id}`}
                        className="flex min-h-11 cursor-pointer items-center gap-3 pl-6"
                      >
                        <Checkbox
                          id={`ch-${c.id}`}
                          checked={selected.has(c.id)}
                          onCheckedChange={(v) => onToggleChapter(c.id, v === true)}
                        />
                        {c.name}
                      </label>
                    ))}
                  </div>
                )}
              </AccordionContent>
            </AccordionItem>
          )
        })}
      </Accordion>
      <div className="flex items-center gap-3">
        <Switch id="also-revised" checked={alsoRevised} onCheckedChange={onAlsoRevised} />
        <Label htmlFor="also-revised">Also count them as revised once</Label>
      </div>
      {error ? <Alert variant="error">{error}</Alert> : null}
      <div className="flex flex-wrap gap-3">
        <Button size="lg" onClick={onApply} disabled={pending || selected.size === 0}>
          {pending ? <LoaderCircle className="animate-spin" aria-hidden /> : null}
          Apply to {selected.size} chapter{selected.size === 1 ? '' : 's'}
        </Button>
        <Button variant="ghost" onClick={onSkip} disabled={pending}>
          Skip for now
        </Button>
      </div>
    </div>
  )
}
