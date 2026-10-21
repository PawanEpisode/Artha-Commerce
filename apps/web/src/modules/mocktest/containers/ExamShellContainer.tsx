import React, { useState } from 'react'

import { CountdownTimer } from '../components/CountdownTimer'
import { LeaseOverlay } from '../components/LeaseOverlay'
import { PalettePanel } from '../components/PalettePanel'
import { ReadingBanner } from '../components/ReadingBanner'
import { SectionStrip } from '../components/SectionStrip'
import { SubmitReviewSheet } from '../components/SubmitReviewSheet'
import { useAttempt } from '../hooks/useAttempt'

interface ExamShellContainerProps {
  attemptId: string
  onFinish: (attemptId: string) => void
  onExit?: () => void
}

export const ExamShellContainer: React.FC<ExamShellContainerProps> = ({ attemptId, onFinish, onExit }) => {
  const {
    attempt,
    phase,
    currentPosition,
    remainingMs,
    sectionRemainingMs,
    activeSectionKey,
    answers,
    flags,
    visitedPositions,
    hasLeaseConflict,
    leaseConflictLabel,
    isLoading,
    isSubmitting,
    setAnswer,
    toggleFlag,
    goToPosition,
    handleAcceptInstructions,
    handleStartWriting,
    handleCloseSection,
    handleSubmit,
    handleTakeOverLease,
  } = useAttempt(attemptId)

  const [showSubmitSheet, setShowSubmitSheet] = useState(false)
  const [instructionsAccepted, setInstructionsAccepted] = useState(false)

  if (isLoading || !attempt) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex items-center gap-3 text-sm font-medium text-muted-foreground">
          <svg className="h-5 w-5 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <span>Loading examination environment...</span>
        </div>
      </div>
    )
  }

  // Phase: Instructions
  if (phase === 'instructions') {
    return (
      <div className="mx-auto max-w-3xl space-y-6 p-4 sm:p-8">
        <div className="space-y-6 rounded-3xl border bg-card p-6 shadow-sm sm:p-8">
          <div className="space-y-2 border-b border-border pb-4">
            <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-bold text-primary uppercase">
              {attempt.run_mode.toUpperCase()} MODE
            </span>
            <h1 className="text-2xl font-black text-foreground sm:text-3xl">{attempt.paper_title}</h1>
            <p className="text-sm text-muted-foreground">
              Please read all examination instructions carefully before proceeding.
            </p>
          </div>

          <div className="space-y-4 rounded-2xl border bg-muted/20 p-5 text-sm leading-relaxed text-foreground/90">
            <h3 className="text-base font-bold text-foreground">General Instructions:</h3>
            <ul className="list-disc space-y-2 pl-5 text-sm text-muted-foreground">
              <li>
                The exam duration is <strong>{Math.round(attempt.duration_seconds / 60)} minutes</strong>.
              </li>
              <li>
                A reading time of <strong>{Math.round(attempt.reading_seconds / 60)} minutes</strong> is provided.
              </li>
              <li>You can navigate across questions freely using the question palette on the right.</li>
              <li>Marking scheme: Correct answers receive designated marks. Negative marks apply where specified.</li>
              <li>Only one active browser tab is allowed for this examination session.</li>
            </ul>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <input
              type="checkbox"
              id="inst-check"
              checked={instructionsAccepted}
              onChange={(e) => setInstructionsAccepted(e.target.checked)}
              className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
            />
            <label htmlFor="inst-check" className="cursor-pointer text-sm font-medium text-foreground">
              I have read, understood and agree to follow all examination guidelines.
            </label>
          </div>

          <div className="flex justify-end border-t border-border pt-4">
            <button
              type="button"
              disabled={!instructionsAccepted}
              onClick={handleAcceptInstructions}
              className="min-h-[44px] rounded-xl bg-primary px-6 py-2.5 text-sm font-bold text-primary-foreground shadow-xs transition-all hover:bg-primary/90 disabled:opacity-50"
            >
              Start Examination
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Phase: Done -> Finish
  if (phase === 'done' || phase === 'upload') {
    onFinish(attempt.id)
    return null
  }

  // Active question layout item
  const currentItem = attempt.layout.find((l) => l.pos === currentPosition) || attempt.layout[0]
  const isReading = phase === 'reading'
  const isLastPosition = currentPosition === attempt.layout.length
  const isFirstPosition = currentPosition === 1

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Top Header Bar */}
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b bg-card px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <h2 className="truncate text-sm font-bold text-foreground sm:text-base">{attempt.paper_title}</h2>
          <span className="hidden rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary sm:inline-block">
            Section {currentItem.section}
          </span>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          <CountdownTimer remainingMs={remainingMs} label="Total Time Remaining" />
          {onExit && (
            <button
              type="button"
              onClick={onExit}
              className="min-h-[44px] rounded-xl border px-3.5 py-2 text-xs font-semibold transition-colors hover:bg-muted sm:text-sm"
            >
              Exit
            </button>
          )}
          <button
            type="button"
            onClick={() => setShowSubmitSheet(true)}
            className="min-h-[44px] rounded-xl bg-rose-600 px-4 py-2 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-rose-700 sm:text-sm"
          >
            Submit Exam
          </button>
        </div>
      </header>

      {/* Reading phase banner */}
      {isReading && (
        <div className="bg-background p-4">
          <ReadingBanner onStartWriting={handleStartWriting} />
        </div>
      )}

      {/* Section Strip */}
      <SectionStrip
        sections={attempt.sections}
        activeSectionKey={activeSectionKey}
        currentSectionKey={currentItem.section}
        sectionTiming={attempt.section_timing}
        sectionRemainingMs={sectionRemainingMs}
        onSelectSection={(key) => {
          const firstInSec = attempt.layout.find((l) => l.section === key)
          if (firstInSec) goToPosition(firstInSec.pos)
        }}
        onCloseSection={handleCloseSection}
      />

      {/* Main Examination Work Area */}
      <div className="mx-auto grid w-full max-w-7xl flex-1 grid-cols-1 items-start gap-6 p-4 sm:p-6 lg:grid-cols-4">
        {/* Question Area (3 Cols) */}
        <div className="flex flex-col overflow-hidden rounded-2xl border bg-card shadow-xs lg:col-span-3">
          {/* Question Header */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-muted/30 p-4 text-sm">
            <div className="flex items-center gap-2">
              <span className="font-bold text-foreground">
                Question {currentItem.pos} of {attempt.layout.length}
              </span>
              <span className="text-xs font-medium text-muted-foreground">
                ({currentItem.label || `Q.${currentItem.pos}`})
              </span>
            </div>
            <div className="flex items-center gap-2 font-mono text-xs">
              <span className="font-semibold text-emerald-600">+{currentItem.marks}</span>
              {currentItem.neg > 0 && <span className="font-semibold text-rose-600">-{currentItem.neg}</span>}
            </div>
          </div>

          {/* Choice group banner if applicable */}
          {currentItem.choice_group && (
            <div className="border-b border-indigo-100 bg-indigo-50 px-4 py-2 text-xs font-semibold text-indigo-900 dark:border-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-300">
              Choice Group: Answer required questions from this set.
            </div>
          )}

          {/* Question Body */}
          <div className="min-h-[300px] flex-1 space-y-6 p-6">
            <div className="text-base leading-relaxed font-medium text-foreground">
              Please review and answer the following question according to Institute standards:
            </div>

            {/* Answer Options Picker */}
            <div className="space-y-3 pt-2">
              {['A', 'B', 'C', 'D'].map((optKey, idx) => {
                const optId = `opt-${idx + 1}`
                const currentAnswer = answers[currentItem.pos] as
                  { selected_option_id?: string; selected_option_ids?: string[] } | undefined
                const isSelected =
                  currentAnswer?.selected_option_id === optId ||
                  Boolean(currentAnswer?.selected_option_ids?.includes(optId))

                return (
                  <button
                    key={optKey}
                    type="button"
                    disabled={isReading}
                    onClick={() => setAnswer(currentItem.pos, { selected_option_id: optId })}
                    className={`flex min-h-[44px] w-full items-center gap-3 rounded-xl border p-4 text-left transition-all ${
                      isSelected
                        ? 'border-primary bg-primary/10 font-semibold text-foreground shadow-xs ring-1 ring-primary'
                        : 'border-border bg-card text-foreground hover:bg-muted/50'
                    } ${isReading ? 'cursor-not-allowed opacity-60' : ''}`}
                  >
                    <span
                      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                        isSelected ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
                      }`}
                    >
                      {optKey}
                    </span>
                    <span className="text-sm">Option {optKey}</span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Question Action Footer */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t bg-muted/30 p-4">
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={isFirstPosition}
                onClick={() => goToPosition(currentPosition - 1)}
                className="min-h-[44px] rounded-xl border px-4 py-2 text-xs font-semibold transition-colors hover:bg-muted disabled:opacity-40"
              >
                Previous
              </button>

              <button
                type="button"
                disabled={isReading || !answers[currentItem.pos]}
                onClick={() => setAnswer(currentItem.pos, null)}
                className="min-h-[44px] px-3 py-2 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                Clear Response
              </button>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => toggleFlag(currentItem.pos)}
                className={`min-h-[44px] rounded-xl border px-4 py-2 text-xs font-semibold transition-all ${
                  flags[currentItem.pos]
                    ? 'border-purple-300 bg-purple-50 text-purple-700 dark:border-purple-800 dark:bg-purple-950 dark:text-purple-300'
                    : 'bg-card text-foreground hover:bg-muted'
                }`}
              >
                {flags[currentItem.pos] ? 'Marked for Review' : 'Mark for Review'}
              </button>

              <button
                type="button"
                disabled={isLastPosition}
                onClick={() => goToPosition(currentPosition + 1)}
                className="min-h-[44px] rounded-xl bg-primary px-5 py-2 text-xs font-bold text-primary-foreground shadow-xs transition-colors hover:bg-primary/90"
              >
                Save & Next
              </button>
            </div>
          </div>
        </div>

        {/* Right Palette Panel (1 Col) */}
        <div className="lg:col-span-1">
          <PalettePanel
            layout={attempt.layout}
            currentPosition={currentPosition}
            answers={answers}
            flags={flags}
            visitedPositions={visitedPositions}
            onSelectPosition={goToPosition}
          />
        </div>
      </div>

      {/* Lease Conflict Dialog */}
      {hasLeaseConflict && <LeaseOverlay onTakeOver={handleTakeOverLease} label={leaseConflictLabel} />}

      {/* Pre-submission confirmation sheet */}
      {showSubmitSheet && (
        <SubmitReviewSheet
          layout={attempt.layout}
          sections={attempt.sections}
          answers={answers}
          flags={flags}
          isSubmitting={isSubmitting}
          onConfirm={async () => {
            await handleSubmit()
            setShowSubmitSheet(false)
          }}
          onCancel={() => setShowSubmitSheet(false)}
        />
      )}
    </div>
  )
}
