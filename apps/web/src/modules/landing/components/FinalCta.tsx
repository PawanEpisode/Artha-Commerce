import { Button, Container, Reveal } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

export function FinalCta() {
  return (
    <section className="pb-14 sm:pb-16">
      <Container>
        <Reveal>
          <div className="relative overflow-hidden rounded-lg bg-primary px-6 py-12 text-center text-primary-foreground sm:px-12">
            <div aria-hidden className="absolute -top-20 -right-20 size-72 rounded-full bg-accent/30 blur-3xl" />
            <div aria-hidden className="absolute -bottom-24 -left-16 size-72 rounded-full bg-highlight/30 blur-3xl" />
            <h2 className="relative mx-auto max-w-2xl text-2xl font-semibold sm:text-3xl">
              Your next attempt starts today.
            </h2>
            <p className="relative mx-auto mt-3 max-w-xl text-base text-primary-foreground/80">
              Create a free account and get your first study plan in minutes.
            </p>
            <Button size="lg" variant="secondary" arrow className="relative mt-6" asChild>
              <Link to="/login">Create my free account</Link>
            </Button>
          </div>
        </Reveal>
      </Container>
    </section>
  )
}
