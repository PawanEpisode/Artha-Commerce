import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@artha/design-system'

/** Shown once, before the first card: what the four answers mean and why being honest helps. */
export function FirstTimeIntro({ onDone }: { onDone: () => void }) {
  return (
    <Card className="mx-auto w-full max-w-xl">
      <CardHeader>
        <CardTitle>How reviewing works</CardTitle>
        <CardDescription>It takes a minute to learn and saves hours later.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ol className="list-decimal space-y-2 pl-5 text-sm">
          <li>Read the question and try to recall the answer before you turn the card.</li>
          <li>
            Turn the card, then tell us how it went: <strong>Again</strong>, <strong>Hard</strong>,{' '}
            <strong>Good</strong> or <strong>Easy</strong>. Each button shows when you will see the card next.
          </li>
          <li>Be honest. Choosing Again is not a failure: it is how the schedule learns what to show you sooner.</li>
        </ol>
        <Button size="lg" className="w-full" onClick={onDone}>
          Start reviewing
        </Button>
      </CardContent>
    </Card>
  )
}
