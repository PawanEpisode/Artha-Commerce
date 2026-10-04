import { ArrowRight, Button, Container, Reveal } from '@artha/design-system'
import { Link } from '@tanstack/react-router'

export function FinalCta() {
  return (
    <section className="pb-24">
      <Container>
        <Reveal>
          <div className="relative overflow-hidden rounded-3xl bg-primary px-6 py-16 text-center text-primary-foreground sm:px-12">
            <div aria-hidden className="absolute -top-20 -right-20 size-72 rounded-full bg-accent/30 blur-3xl" />
            <div aria-hidden className="absolute -bottom-24 -left-16 size-72 rounded-full bg-highlight/30 blur-3xl" />
            <h2 className="relative mx-auto max-w-2xl text-3xl font-extrabold sm:text-5xl">
              Your next attempt starts today.
            </h2>
            <p className="relative mx-auto mt-4 max-w-xl text-lg text-primary-foreground/80">
              Create a free account and get your first study plan in minutes.
            </p>
            <Button size="lg" variant="secondary" className="relative mt-8" asChild>
              <Link to="/login">
                Get started free <ArrowRight />
              </Link>
            </Button>
          </div>
        </Reveal>
      </Container>
    </section>
  )
}
