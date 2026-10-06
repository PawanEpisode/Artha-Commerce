import { timeSchema } from './schemas'

export const isValidTime = (value: string): boolean => timeSchema.safeParse(value).success

/** "22:00" becomes "10:00 pm". */
export function formatTime(value: string): string {
  if (!isValidTime(value)) return value
  const [h, m] = value.split(':').map(Number) as [number, number]
  const hour = h % 12 === 0 ? 12 : h % 12
  return `${hour}:${String(m).padStart(2, '0')} ${h < 12 ? 'am' : 'pm'}`
}

/** True when the window runs past midnight (22:00 to 07:00). Start is inclusive and end exclusive, as on the API. */
export const crossesMidnight = (start: string, end: string): boolean => start > end

/** Problem with a quiet-hours pair, in words for the field, or null when the API will accept it. */
export function quietHoursError(start: string, end: string): string | null {
  if (!isValidTime(start) || !isValidTime(end)) return 'Enter a time such as 10:00 pm.'
  if (start === end) return 'Start and end must be different times.'
  return null
}

export function describeQuietHours(start: string, end: string): string {
  const tail = crossesMidnight(start, end) ? ' the next morning' : ''
  return `Quiet from ${formatTime(start)} until ${formatTime(end)}${tail}.`
}
