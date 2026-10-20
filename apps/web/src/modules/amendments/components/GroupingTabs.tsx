import { Tabs, TabsList, TabsTrigger } from '@artha/design-system'

export type GroupingMode = 'paper' | 'chapter' | 'type' | 'flat'

interface Props {
  value: GroupingMode
  onChange: (mode: GroupingMode) => void
  className?: string
}

export function GroupingTabs({ value, onChange, className }: Props) {
  return (
    <div className={`flex items-center gap-2 ${className ?? ''}`}>
      <span className="text-xs font-medium text-muted-foreground">Group by:</span>
      <Tabs value={value} onValueChange={(val) => onChange(val as GroupingMode)}>
        <TabsList className="h-8">
          <TabsTrigger value="paper" className="px-2.5 py-1 text-xs">
            Paper
          </TabsTrigger>
          <TabsTrigger value="chapter" className="px-2.5 py-1 text-xs">
            Chapter
          </TabsTrigger>
          <TabsTrigger value="type" className="px-2.5 py-1 text-xs">
            Type
          </TabsTrigger>
          <TabsTrigger value="flat" className="px-2.5 py-1 text-xs">
            Flat List
          </TabsTrigger>
        </TabsList>
      </Tabs>
    </div>
  )
}
