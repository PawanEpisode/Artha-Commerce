import { Button, Container } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

export function NotFound() {
  return (
    <Container className="grid min-h-[60vh] place-items-center py-24 text-center">
      <div>
        <p className="font-display text-7xl font-extrabold text-primary">404</p>
        <h1 className="mt-4 text-2xl font-bold">We could not find that page</h1>
        <p className="mt-2 text-muted-foreground">The link may be old or mistyped.</p>
        <Button variant="cta" arrow className="mt-8" asChild>
          <Link to="/">Go to the home page</Link>
        </Button>
      </div>
    </Container>
  )
}
