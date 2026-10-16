import { Dialog as DialogPrimitive } from 'radix-ui'
import * as React from 'react'

import { X } from '../../icons'
import { cn } from '../../lib/utils'

export const Dialog = DialogPrimitive.Root
export const DialogTrigger = DialogPrimitive.Trigger
export const DialogClose = DialogPrimitive.Close

/** A modal dialog: focus is trapped, Escape closes it, and focus returns to the control that opened it. */
export function DialogContent({ className, children, ...props }: React.ComponentProps<typeof DialogPrimitive.Content>) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-foreground/40 data-[state=open]:animate-in data-[state=open]:fade-in-0 motion-reduce:animate-none" />
      <DialogPrimitive.Content
        data-slot="dialog-content"
        className={cn(
          'fixed top-1/2 left-1/2 z-50 max-h-[90dvh] w-[min(32rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl border border-border bg-popover p-5 text-popover-foreground shadow-(--shadow-lift) outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 motion-reduce:animate-none',
          className,
        )}
        {...props}
      >
        {children}
        <DialogPrimitive.Close
          aria-label="Close"
          className="absolute top-2.5 right-2.5 grid size-8 cursor-pointer place-items-center rounded-md text-muted-foreground outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40 pointer-coarse:size-11"
        >
          <X className="size-4" aria-hidden />
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
}

export function DialogTitle({ className, ...props }: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return <DialogPrimitive.Title className={cn('pr-10 font-display text-base font-semibold', className)} {...props} />
}

export function DialogDescription({ className, ...props }: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return <DialogPrimitive.Description className={cn('mt-1 text-[13px] text-muted-foreground', className)} {...props} />
}

export function DialogHeader({ className, ...props }: React.ComponentProps<'div'>) {
  return <div data-slot="dialog-header" className={cn('mb-4 space-y-1 pr-10', className)} {...props} />
}

export function DialogFooter({ className, ...props }: React.ComponentProps<'div'>) {
  return <div data-slot="dialog-footer" className={cn('mt-5 flex flex-wrap justify-end gap-2', className)} {...props} />
}
