import { Button, DatePicker, FlipCard, ProgressCounter, type Rating, RatingButtons } from '@artha/design-system'
import { useState } from 'react'

const PREVIEWS = { 1: '10 min', 2: '2 d', 3: '5 d', 4: '12 d' } as const

/** The four review components together, laid out as the review screen will use them. */
export function RecallPrimitivesShowcase() {
  const [flipped, setFlipped] = useState(false)
  const [done, setDone] = useState(12)
  const [last, setLast] = useState<Rating | null>(null)
  const [until, setUntil] = useState<string | null>(null)

  const rate = (rating: Rating) => {
    setLast(rating)
    setDone((n) => Math.min(n + 1, 30))
    setFlipped(false)
  }

  return (
    <section aria-labelledby="recall-primitives" className="space-y-4">
      <h2 id="recall-primitives" className="text-xl font-bold">
        Recall review
      </h2>
      <div className="mx-auto grid w-full max-w-xl gap-4">
        <ProgressCounter done={done} total={30} label="Cards reviewed" />
        <FlipCard
          flipped={flipped}
          onFlip={() => setFlipped(true)}
          swipeEnabled
          onSwipe={(dir) => rate(dir === 'right' ? 3 : 1)}
          front={<p className="text-lg font-semibold">What does the Shankar-Zorn test measure?</p>}
          back={<p className="text-lg">Placeholder answer shown after the flip.</p>}
        />
        {flipped ? <RatingButtons onRate={rate} previews={PREVIEWS} /> : null}
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {last ? `Last answer: ${last}` : 'No answer yet'}
        </p>
        {flipped ? null : (
          <Button variant="outline" onClick={() => setDone(12)}>
            Reset counter
          </Button>
        )}
        <DatePicker
          label="Vacation ends on"
          hint="Reviews resume the next morning."
          value={until}
          onValueChange={setUntil}
          min="2026-10-10"
        />
      </div>
    </section>
  )
}
