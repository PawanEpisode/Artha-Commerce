import * as React from 'react'

import { cn } from '../../lib/utils'

/** Series colours in their fixed order. The sixth and later fold into "Other" (muted), never a new hue. */
const SERIES_CLASS = ['bg-chart-1', 'bg-chart-2', 'bg-chart-3', 'bg-chart-4', 'bg-chart-5'] as const
const OTHER_CLASS = 'bg-muted-foreground'
export const seriesClass = (index: number) => SERIES_CLASS[index] ?? OTHER_CLASS

export interface ChartSeries {
  key: string
  name: string
}

export interface ChartColumn {
  /** Full label, used in the readout and the table ("Mon 5 Oct"). */
  label: string
  /** Short label under the bar ("5"). Defaults to `label`. */
  short?: string
  values: Record<string, number>
}

interface BarChartProps {
  title: string
  series: ChartSeries[]
  columns: ChartColumn[]
  /** Formats a value for the readout and the table ("1 h 20 m"). */
  format: (value: number) => string
  /** Pixel height of the plot. */
  height?: number
  /** Show only every n-th short label (long ranges). */
  labelEvery?: number
  className?: string
}

const total = (c: ChartColumn) => Object.values(c.values).reduce((a, b) => a + b, 0)

/**
 * Vertical bars, optionally stacked by series. HTML and CSS only (tokens for colour). The values are readable three
 * ways, so colour is never the only channel: a readout line on hover and keyboard focus, a legend, and a table.
 */
export function BarChart({ title, series, columns, format, height = 160, labelEvery = 1, className }: BarChartProps) {
  const [active, setActive] = React.useState<number | null>(null)
  const max = Math.max(1, ...columns.map(total))
  const col = active === null ? null : columns[active]
  return (
    <figure data-slot="bar-chart" className={cn('space-y-3', className)}>
      <figcaption className="text-sm font-semibold">{title}</figcaption>
      <p className="min-h-5 text-sm text-muted-foreground" aria-live="off">
        {col
          ? `${col.label}: ${format(total(col))}${
              series.length > 1
                ? ` (${series
                    .filter((s) => (col.values[s.key] ?? 0) > 0)
                    .map((s) => `${s.name} ${format(col.values[s.key] ?? 0)}`)
                    .join(', ')})`
                : ''
            }`
          : 'Hover or focus a bar for its value.'}
      </p>
      <div
        className="flex items-end gap-0.5 border-b border-border"
        style={{ height }}
        onMouseLeave={() => setActive(null)}
      >
        {columns.map((c, i) => {
          const sum = total(c)
          return (
            <button
              key={c.label + i}
              type="button"
              aria-label={`${c.label}: ${format(sum)}`}
              onMouseEnter={() => setActive(i)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
              className="group flex h-full min-w-0 flex-1 cursor-pointer flex-col-reverse justify-start gap-0.5 rounded-sm px-px outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
            >
              {series.map((s, si) => {
                const v = c.values[s.key] ?? 0
                if (v <= 0) return null
                return (
                  <span
                    key={s.key}
                    className={cn(
                      'block min-h-0.5 w-full first:rounded-b-none last:rounded-t-sm',
                      seriesClass(si),
                      active === i ? 'opacity-100' : 'opacity-90',
                    )}
                    style={{ height: `${(v / max) * 100}%` }}
                  />
                )
              })}
            </button>
          )
        })}
      </div>
      <div className="flex gap-0.5 text-[11px] text-muted-foreground" aria-hidden>
        {columns.map((c, i) => (
          <span key={c.label + i} className="min-w-0 flex-1 truncate text-center">
            {i % labelEvery === 0 ? (c.short ?? c.label) : ''}
          </span>
        ))}
      </div>
      {series.length > 1 ? (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs" aria-label="Legend">
          {series.map((s, i) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span aria-hidden className={cn('size-2.5 rounded-sm', seriesClass(i))} />
              {s.name}
            </li>
          ))}
        </ul>
      ) : null}
      <details className="text-sm">
        <summary className="cursor-pointer rounded-md py-1 font-medium text-primary outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40">
          View as table
        </summary>
        <div className="mt-2 max-h-72 overflow-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">{title}</caption>
            <thead>
              <tr>
                <th scope="col" className="py-1 pr-3 font-semibold">
                  Period
                </th>
                {series.length > 1
                  ? series.map((s) => (
                      <th key={s.key} scope="col" className="py-1 pr-3 font-semibold">
                        {s.name}
                      </th>
                    ))
                  : null}
                <th scope="col" className="py-1 font-semibold">
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {columns.map((c, i) => (
                <tr key={c.label + i} className="border-t border-border">
                  <th scope="row" className="py-1 pr-3 font-normal">
                    {c.label}
                  </th>
                  {series.length > 1
                    ? series.map((s) => (
                        <td key={s.key} className="py-1 pr-3 tabular-nums">
                          {format(c.values[s.key] ?? 0)}
                        </td>
                      ))
                    : null}
                  <td className="py-1 tabular-nums">{format(total(c))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  )
}

export interface HeatCell {
  /** ISO date, used as the key and passed to onSelect. */
  date: string
  /** 0 (no study) to 5. */
  level: number
  /** Position in the week row, 0 for the first day of the week the chart starts on. */
  weekday: number
  /** Accessible name ("5 Oct: 2 h 10 m"). */
  label: string
}

interface HeatmapProps {
  title: string
  cells: HeatCell[]
  onSelect?: (date: string) => void
  weekdayLabels: string[]
  legend: { less: string; more: string }
  className?: string
}

/** Calendar heat map: one column per week, one row per weekday. Every cell is a button with its value as its name. */
export function Heatmap({ title, cells, onSelect, weekdayLabels, legend, className }: HeatmapProps) {
  const lead = cells[0]?.weekday ?? 0
  return (
    <figure data-slot="heatmap" className={cn('space-y-3', className)}>
      <figcaption className="text-sm font-semibold">{title}</figcaption>
      <div className="flex gap-2 overflow-x-auto pb-1">
        <div aria-hidden className="grid grid-rows-7 gap-0.5 pt-px text-[10px] text-muted-foreground">
          {weekdayLabels.map((d, i) => (
            <span key={i} className="grid h-4 items-center">
              {i % 2 === 0 ? d : ''}
            </span>
          ))}
        </div>
        <div className="grid grid-flow-col grid-rows-7 gap-0.5">
          {Array.from({ length: lead }, (_, i) => (
            <span key={`pad-${i}`} aria-hidden className="size-4" />
          ))}
          {cells.map((c) => (
            <button
              key={c.date}
              type="button"
              aria-label={c.label}
              title={c.label}
              onClick={() => onSelect?.(c.date)}
              className={cn(
                'size-4 cursor-pointer rounded-[3px] border border-border outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40',
                `heat-${c.level}`,
              )}
            />
          ))}
        </div>
      </div>
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground" aria-hidden>
        {legend.less}
        {[0, 1, 2, 3, 4, 5].map((l) => (
          <span key={l} className={cn('size-3.5 rounded-[3px] border border-border', `heat-${l}`)} />
        ))}
        {legend.more}
      </div>
    </figure>
  )
}
