import { Input, Search, SegmentedControl } from '@artha/design-system'

import type { CardFilter } from '../lib/types'

interface Props {
  filter: CardFilter
  onChange: (updated: Partial<CardFilter>) => void
  className?: string
}

export function ApplicabilityFilter({ filter, onChange, className }: Props) {
  return (
    <div className={`flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between ${className ?? ''}`}>
      <div className="flex flex-wrap items-center gap-2">
        <SegmentedControl
          label="Filter by applicability"
          value={filter.applies ?? 'mine'}
          onValueChange={(val) => onChange({ applies: val as 'mine' | 'all' })}
          options={[
            { value: 'mine', label: 'Applies to me' },
            { value: 'all', label: 'All attempts' },
          ]}
        />

        <SegmentedControl
          label="Filter by review state"
          value={filter.state ?? ''}
          onValueChange={(val) => onChange({ state: val as CardFilter['state'] })}
          options={[
            { value: '', label: 'All' },
            { value: 'unreviewed', label: 'Unreviewed' },
            { value: 'reviewed', label: 'Reviewed' },
            { value: 'saved', label: 'Saved' },
          ]}
        />
      </div>

      <div className="relative w-full sm:w-64">
        <Search className="absolute top-2.5 left-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          type="search"
          placeholder="Search provision, law, title..."
          className="h-9 pl-9 text-xs sm:text-sm"
          value={filter.q ?? ''}
          onChange={(e) => onChange({ q: e.target.value })}
        />
      </div>
    </div>
  )
}
