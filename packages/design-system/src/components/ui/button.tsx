import { cva, type VariantProps } from 'class-variance-authority'
import { Slot } from 'radix-ui'
import * as React from 'react'

import { ArrowRight, LoaderCircle } from '../../icons'
import { cn } from '../../lib/utils'

export const buttonVariants = cva(
  "group/btn relative inline-flex shrink-0 items-center justify-center gap-2 rounded-lg text-sm font-semibold whitespace-nowrap transition-all outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 active:translate-y-px disabled:pointer-events-none disabled:opacity-50 aria-busy:cursor-progress aria-disabled:pointer-events-none aria-disabled:opacity-50 motion-reduce:transition-none motion-reduce:active:translate-y-0 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground shadow-soft hover:brightness-110',
        /** The one primary call to action on a view: solid, lifted, arrow slides on hover. */
        cta: 'bg-primary text-primary-foreground shadow-lift ring-1 ring-primary-foreground/15 ring-inset hover:-translate-y-0.5 hover:brightness-110 active:translate-y-0 active:shadow-soft motion-reduce:hover:translate-y-0',
        accent: 'bg-accent text-accent-foreground shadow-soft hover:brightness-105',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/70',
        outline: 'border border-input bg-card text-foreground hover:bg-muted',
        ghost: 'text-foreground hover:bg-muted',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        sm: 'h-9 px-3.5',
        default: 'h-11 px-5',
        lg: 'h-12 rounded-xl px-7 text-base',
        xl: 'h-14 rounded-xl px-8 text-base sm:text-lg',
        icon: 'size-10',
      },
      fullWidth: { true: 'w-full', false: '' },
    },
    defaultVariants: { variant: 'default', size: 'default', fullWidth: false },
  },
)

export interface ButtonProps extends React.ComponentProps<'button'>, VariantProps<typeof buttonVariants> {
  asChild?: boolean
  /** Shows a spinner, sets aria-busy and blocks clicks. Not combined with asChild. */
  loading?: boolean
  /** Adds a trailing arrow that nudges right on hover. Pair with `variant="cta"` for primary calls to action. */
  arrow?: boolean
}

function ArrowAdornment() {
  return (
    <ArrowRight
      aria-hidden
      className="transition-transform group-hover/btn:translate-x-1 motion-reduce:transition-none motion-reduce:group-hover/btn:translate-x-0"
    />
  )
}

export function Button({
  className,
  variant,
  size,
  fullWidth,
  asChild = false,
  loading = false,
  arrow = false,
  children,
  disabled,
  ...props
}: ButtonProps) {
  const classes = cn(buttonVariants({ variant, size, fullWidth }), className)
  if (asChild) {
    return (
      <Slot.Root data-slot="button" className={classes} {...props}>
        <Slot.Slottable>{children}</Slot.Slottable>
        {arrow ? <ArrowAdornment /> : null}
      </Slot.Root>
    )
  }
  return (
    <button
      data-slot="button"
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? <LoaderCircle aria-hidden className="animate-spin motion-reduce:animate-none" /> : null}
      {children}
      {arrow && !loading ? <ArrowAdornment /> : null}
    </button>
  )
}

export interface ButtonLinkProps extends React.ComponentProps<'a'>, VariantProps<typeof buttonVariants> {
  /**
   * Render the single child instead of an anchor, so a router link keeps its own behaviour:
   * `<ButtonLink asChild><Link to="/courses">Browse</Link></ButtonLink>`.
   */
  asChild?: boolean
  arrow?: boolean
}

/** A link that looks like a Button. One source of button styling for navigation. */
export function ButtonLink({
  className,
  variant,
  size,
  fullWidth,
  asChild = false,
  arrow = false,
  children,
  ...props
}: ButtonLinkProps) {
  const Comp = asChild ? Slot.Root : 'a'
  return (
    <Comp data-slot="button-link" className={cn(buttonVariants({ variant, size, fullWidth }), className)} {...props}>
      <Slot.Slottable>{children}</Slot.Slottable>
      {arrow ? <ArrowAdornment /> : null}
    </Comp>
  )
}
