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
  StepDialog,
  SyncChip,
  UsageBar,
} from '@artha/design-system'
import { useState } from 'react'

/** Shared primitives added for Smart Notes: SyncChip, UsageBar, FilterChip and Sheet. */
export function NotesPrimitivesShowcase() {
  const [chips, setChips] = useState(['Tag: doubt', 'Chapter: Input tax credit'])
  const [stepsOpen, setStepsOpen] = useState(false)
  const [step, setStep] = useState(0)
  const stepNames = ['Details', 'Filing', 'Pages']
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
          <UsageBar label="PDF storage" used={412} limit={500} unit="MB" />
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

      <section className="space-y-4">
        <h2 className="text-xl font-bold">Step dialog</h2>
        <p className="text-sm text-muted-foreground">
          A modal for a short flow: progress, one heading per step, Back and the primary action pinned at the bottom.
        </p>
        <Button
          variant="outline"
          onClick={() => {
            setStep(0)
            setStepsOpen(true)
          }}
        >
          Open step dialog
        </Button>
        <StepDialog
          open={stepsOpen}
          onOpenChange={setStepsOpen}
          title="Upload a PDF"
          description="Your PDF is private to you."
          steps={stepNames}
          current={step}
          onStepSelect={setStep}
          stepTitle={stepNames[step] ?? ''}
          stepDescription="Everything here is optional."
          onBack={step > 0 ? () => setStep(step - 1) : undefined}
          action={
            step < stepNames.length - 1 ? (
              <Button onClick={() => setStep(step + 1)}>Next</Button>
            ) : (
              <Button variant="cta" onClick={() => setStepsOpen(false)}>
                Upload
              </Button>
            )
          }
        >
          <p className="text-sm">The fields of the {stepNames[step]?.toLowerCase()} step go here.</p>
        </StepDialog>
      </section>
    </>
  )
}
