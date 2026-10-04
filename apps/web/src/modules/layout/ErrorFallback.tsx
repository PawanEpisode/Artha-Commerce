import { useEffect } from 'react'
import { Link } from '@tanstack/react-router'
import { Button } from '~/components/ui/button'
import { Container } from '~/design-system'
import { captureException } from '~/modules/observability'

export function ErrorFallback({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => {
    captureException(error)
  }, [error])

  return (
    <Container className="grid min-h-[60vh] place-items-center py-24 text-center">
      <div>
        <h1 className="text-2xl font-bold">Something went wrong</h1>
        <p className="mt-2 text-muted-foreground">We have been notified. Please try again.</p>
        <div className="mt-8 flex justify-center gap-3">
          <Button onClick={reset}>Try again</Button>
          <Button variant="outline" asChild>
            <Link to="/">Home</Link>
          </Button>
        </div>
      </div>
    </Container>
  )
}
