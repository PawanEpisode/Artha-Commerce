import {
  Button,
  FilterChip,
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
  SyncChip,
  UsageBar,
} from '@artha/design-system'
import { useState } from 'react'

/** Shared primitives added for Smart Notes: SyncChip, UsageBar, FilterChip and Sheet. */
export function NotesPrimitivesShowcase() {
  const [chips, setChips] = useState(['Tag: doubt', 'Chapter: Input tax credit'])
  return (
    <>
      <section className="space-y-4">
        <h2 className="text-xl font-bold">Sync chip</h2>
        <p className="text-sm text-muted-foreground">
          Icon plus words, announced politely. The attention state is a button when it opens something.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <SyncChip state="saved" />
          <SyncChip state="saving" />
          <SyncChip state="offline" count={4} />
          <SyncChip state="attention" count={1} onPress={() => undefined} />
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-bold">Usage bar</h2>
        <div className="grid max-w-xl gap-4">
          <UsageBar label="Storage" used={120} limit={500} format={(n) => `${n} MB`} />
          <UsageBar label="Notes" used={1900} limit={2000} />
          <UsageBar label="Storage" used={500} limit={500} format={(n) => `${n} MB`} fullText="Storage full" />
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-bold">Filter chips and sheet</h2>
        <div className="flex flex-wrap gap-2">
          {chips.map((chip) => (
            <FilterChip
              key={chip}
              removeLabel={`Remove filter ${chip}`}
              onRemove={() => setChips((all) => all.filter((c) => c !== chip))}
            >
              {chip}
            </FilterChip>
          ))}
        </div>
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="outline">Open bottom sheet</Button>
          </SheetTrigger>
          <SheetContent>
            <SheetHeader>
              <SheetTitle>This note changed on another device</SheetTitle>
              <SheetDescription>Choose which version to keep. Nothing is lost.</SheetDescription>
            </SheetHeader>
            <SheetFooter>
              <Button variant="outline">Keep theirs</Button>
              <Button>Keep mine</Button>
            </SheetFooter>
          </SheetContent>
        </Sheet>
      </section>
    </>
  )
}
