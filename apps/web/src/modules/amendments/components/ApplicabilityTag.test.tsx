import { TooltipProvider } from '@artha/design-system'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ApplicabilityTag } from './ApplicabilityTag'

describe('ApplicabilityTag', () => {
  it('renders applies status with attempt label inside TooltipProvider', () => {
    render(
      <TooltipProvider>
        <ApplicabilityTag
          applicability={{
            state: 'applies',
            reason: 'Applicable for June 2026 attempt',
          }}
          targetTerm="June 2026"
        />
      </TooltipProvider>,
    )

    expect(screen.getByText('Applies to June 2026')).toBeInTheDocument()
  })

  it('renders unknown status when applicability is unknown', () => {
    render(
      <TooltipProvider>
        <ApplicabilityTag
          applicability={{
            state: 'unknown',
            reason: 'Official notice awaited',
          }}
        />
      </TooltipProvider>,
    )

    expect(screen.getByText('Applicability unknown')).toBeInTheDocument()
  })

  it('renders not_applicable status', () => {
    render(
      <TooltipProvider>
        <ApplicabilityTag
          applicability={{
            state: 'not_applicable',
            reason: 'Relevant only for December 2026 onwards',
          }}
        />
      </TooltipProvider>,
    )

    expect(screen.getByText('Not applicable to your attempt')).toBeInTheDocument()
  })
})
