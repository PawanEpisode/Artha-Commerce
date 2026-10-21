import { CheckCircle2, Circle, RotateCcw } from '@artha/design-system'
import React from 'react'

import type { ProgressState } from '../lib/types'

interface StateToggleProps {
  state?: ProgressState
  onChange: (nextState: ProgressState) => void
  disabled?: boolean
  size?: 'sm' | 'md'
}

export const StateToggle: React.FC<StateToggleProps> = ({
  state = 'to_do',
  onChange,
  disabled = false,
  size = 'md',
}) => {
  const isSm = size === 'sm'

  return (
    <div
      className="inline-flex items-center gap-0.5 rounded-xl border bg-muted/30 p-0.5"
      role="group"
      aria-label="Item study status"
    >
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange('to_do')}
        aria-pressed={state === 'to_do'}
        title="Mark as To Do"
        className={`inline-flex items-center gap-1 rounded-lg font-medium transition-all ${
          isSm ? 'min-h-[36px] px-2 py-1 text-xs' : 'min-h-[44px] px-2.5 py-1.5 text-xs'
        } ${
          state === 'to_do'
            ? 'border border-border bg-background font-semibold text-foreground shadow-xs'
            : 'text-muted-foreground hover:bg-background/50 hover:text-foreground'
        } disabled:opacity-50`}
      >
        <Circle className="h-3.5 w-3.5 shrink-0" />
        <span>To Do</span>
      </button>

      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange('done')}
        aria-pressed={state === 'done'}
        title="Mark as Completed"
        className={`inline-flex items-center gap-1 rounded-lg font-medium transition-all ${
          isSm ? 'min-h-[36px] px-2 py-1 text-xs' : 'min-h-[44px] px-2.5 py-1.5 text-xs'
        } ${
          state === 'done'
            ? 'bg-emerald-600 font-semibold text-white shadow-xs'
            : 'text-muted-foreground hover:bg-background/50 hover:text-foreground'
        } disabled:opacity-50`}
      >
        <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
        <span>Done</span>
      </button>

      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange('revise')}
        aria-pressed={state === 'revise'}
        title="Mark for Revision"
        className={`inline-flex items-center gap-1 rounded-lg font-medium transition-all ${
          isSm ? 'min-h-[36px] px-2 py-1 text-xs' : 'min-h-[44px] px-2.5 py-1.5 text-xs'
        } ${
          state === 'revise'
            ? 'bg-amber-600 font-semibold text-white shadow-xs'
            : 'text-muted-foreground hover:bg-background/50 hover:text-foreground'
        } disabled:opacity-50`}
      >
        <RotateCcw className="h-3.5 w-3.5 shrink-0" />
        <span>Revise</span>
      </button>
    </div>
  )
}
