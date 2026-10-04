import type { ComponentProps, ReactNode } from 'react'

import { cn } from './lib/utils'

export function Container({ className, ...props }: ComponentProps<'div'>) {
  return <div className={cn('mx-auto w-full max-w-6xl px-5 sm:px-8', className)} {...props} />
}

interface SectionProps extends Omit<ComponentProps<'section'>, 'title'> {
  eyebrow?: string
  title?: ReactNode
  description?: ReactNode
  align?: 'left' | 'center'
}

/** Standard page section: consistent vertical rhythm and heading block. */
export function Section({
  eyebrow,
  title,
  description,
  align = 'center',
  className,
  children,
  ...props
}: SectionProps) {
  return (
    <section className={cn('py-20 sm:py-28', className)} {...props}>
      <Container>
        {(eyebrow || title || description) && (
          <header className={cn('mb-12 max-w-2xl sm:mb-16', align === 'center' && 'mx-auto text-center')}>
            {eyebrow && <p className="mb-3 text-sm font-semibold tracking-widest text-primary uppercase">{eyebrow}</p>}
            {title && <h2 className="text-3xl font-bold sm:text-4xl lg:text-5xl">{title}</h2>}
            {description && <p className="mt-4 text-lg text-muted-foreground">{description}</p>}
          </header>
        )}
        {children}
      </Container>
    </section>
  )
}
