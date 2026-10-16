import { DropdownMenu as DropdownMenuPrimitive } from 'radix-ui'
import * as React from 'react'

import { cn } from '../../lib/utils'

export const DropdownMenu = DropdownMenuPrimitive.Root
export const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger
export const DropdownMenuRadioGroup = DropdownMenuPrimitive.RadioGroup

export function DropdownMenuContent({
  className,
  sideOffset = 6,
  align = 'end',
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Content>) {
  return (
    <DropdownMenuPrimitive.Portal>
      <DropdownMenuPrimitive.Content
        data-slot="dropdown-menu-content"
        sideOffset={sideOffset}
        align={align}
        collisionPadding={12}
        className={cn(
          'z-50 max-h-(--radix-dropdown-menu-content-available-height) min-w-52 overflow-y-auto rounded-lg border bg-popover p-1 text-popover-foreground shadow-lift data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0',
          className,
        )}
        {...props}
      />
    </DropdownMenuPrimitive.Portal>
  )
}

const itemBase =
  'relative flex min-h-8 cursor-pointer items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] outline-none select-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 pointer-coarse:min-h-11 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*="size-"])]:size-4'

export function DropdownMenuItem({ className, ...props }: React.ComponentProps<typeof DropdownMenuPrimitive.Item>) {
  return <DropdownMenuPrimitive.Item data-slot="dropdown-menu-item" className={cn(itemBase, className)} {...props} />
}

export function DropdownMenuRadioItem({
  className,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.RadioItem>) {
  return (
    <DropdownMenuPrimitive.RadioItem
      data-slot="dropdown-menu-radio-item"
      className={cn(
        itemBase,
        'data-[state=checked]:bg-secondary data-[state=checked]:text-secondary-foreground',
        className,
      )}
      {...props}
    />
  )
}

export function DropdownMenuLabel({ className, ...props }: React.ComponentProps<typeof DropdownMenuPrimitive.Label>) {
  return (
    <DropdownMenuPrimitive.Label
      data-slot="dropdown-menu-label"
      className={cn('px-2.5 py-1.5 text-[11px] font-medium tracking-wide text-muted-foreground uppercase', className)}
      {...props}
    />
  )
}

export function DropdownMenuSeparator({
  className,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Separator>) {
  return <DropdownMenuPrimitive.Separator className={cn('-mx-1 my-1 h-px bg-border', className)} {...props} />
}
