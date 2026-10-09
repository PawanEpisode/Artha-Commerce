import { cva, type VariantProps } from 'class-variance-authority'
import { Dialog as DialogPrimitive } from 'radix-ui'
import * as React from 'react'

import { X } from '../../icons'
import { cn } from '../../lib/utils'

export const Sheet = DialogPrimitive.Root
export const SheetTrigger = DialogPrimitive.Trigger
export const SheetClose = DialogPrimitive.Close

const sheetVariants = cva(
  'fixed z-50 flex flex-col overflow-y-auto border-border bg-popover text-popover-foreground shadow-(--shadow-lift) outline-none data-[state=open]:animate-in motion-reduce:animate-none',
  {
    variants: {
      side: {
        /** Thumb-reachable on phones. Safe-area padding keeps the last control above the home indicator. */
        bottom:
          'inset-x-0 bottom-0 mx-auto max-h-[90dvh] w-full max-w-2xl rounded-t-2xl border-t p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] data-[state=open]:slide-in-from-bottom sm:p-6',
        right: 'inset-y-0 right-0 h-dvh w-[min(26rem,100vw)] border-l p-5 data-[state=open]:slide-in-from-right sm:p-6',
      },
    },
    defaultVariants: { side: 'bottom' },
  },
)

/**
 * A panel that slides in from the bottom (default, phones) or the right. Radix Dialog underneath, so focus is trapped,
 * Escape closes it and focus returns to the control that opened it. Give it a `SheetTitle`.
 */
export function SheetContent({
  className,
  children,
  side,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content> & VariantProps<typeof sheetVariants>) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-foreground/40 data-[state=open]:animate-in data-[state=open]:fade-in-0 motion-reduce:animate-none" />
      <DialogPrimitive.Content data-slot="sheet-content" className={cn(sheetVariants({ side }), className)} {...props}>
        {children}
        <DialogPrimitive.Close
          aria-label="Close"
          className="absolute top-3 right-3 grid size-11 cursor-pointer place-items-center rounded-lg text-muted-foreground outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40"
        >
          <X className="size-4" aria-hidden />
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
}

export function SheetHeader({ className, ...props }: React.ComponentProps<'div'>) {
  return <div data-slot="sheet-header" className={cn('mb-4 space-y-1 pr-10', className)} {...props} />
}

export function SheetFooter({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="sheet-footer"
      className={cn('mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end', className)}
      {...props}
    />
  )
}

export function SheetTitle({ className, ...props }: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return <DialogPrimitive.Title className={cn('font-display text-xl font-bold', className)} {...props} />
}

export function SheetDescription({ className, ...props }: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return <DialogPrimitive.Description className={cn('text-sm text-muted-foreground', className)} {...props} />
}
