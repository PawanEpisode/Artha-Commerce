import { Tabs as TabsPrimitive } from 'radix-ui'
import * as React from 'react'

import { cn } from '../../lib/utils'

export const Tabs = TabsPrimitive.Root

export function TabsList({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn('inline-flex items-center gap-1 rounded-xl bg-muted p-1', className)}
      {...props}
    />
  )
}

export function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        'inline-flex h-9 items-center justify-center rounded-lg px-4 text-sm font-semibold text-muted-foreground transition-all outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-soft',
        className,
      )}
      {...props}
    />
  )
}

export const TabsContent = TabsPrimitive.Content
