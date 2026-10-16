import { Tabs as TabsPrimitive } from 'radix-ui'
import * as React from 'react'

import { cn } from '../../lib/utils'

export const Tabs = TabsPrimitive.Root

export function TabsList({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn('inline-flex items-center gap-0.5 rounded-md bg-muted p-0.5', className)}
      {...props}
    />
  )
}

export function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        'inline-flex h-7 cursor-pointer items-center justify-center rounded px-3 text-[13px] font-medium text-muted-foreground transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/50 data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-soft pointer-coarse:h-10',
        className,
      )}
      {...props}
    />
  )
}

export const TabsContent = TabsPrimitive.Content
