import { Button, Card, CardContent, Kbd } from '@artha/design-system'

/** Shown once, above the timer. Dismissing it is remembered on the server (`intro_seen`). */
export function FirstRunIntro({ onDismiss }: { onDismiss: () => void }) {
  return (
    <Card>
      <CardContent className="space-y-3 p-6">
        <h2 className="text-lg font-bold">How the focus timer works</h2>
        <ul className="list-disc space-y-1.5 pl-5 text-sm text-muted-foreground">
          <li>Study in focused rounds, then rest. A classic round is 25 minutes, with a 5 minute break.</li>
          <li>After a few rounds you get a longer break. Pick another rhythm any time with a preset.</li>
          <li>The clock runs on our server, so closing the tab or switching devices does not lose your place.</li>
          <li>
            Shortcuts: <Kbd>Space</Kbd> start or pause, <Kbd>S</Kbd> skip a break, <Kbd>E</Kbd> end a round early.
          </li>
        </ul>
        <Button size="sm" onClick={onDismiss}>
          Got it
        </Button>
      </CardContent>
    </Card>
  )
}
