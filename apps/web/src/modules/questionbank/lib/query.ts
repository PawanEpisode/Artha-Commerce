import type { QuestionSearchParams } from './types'

/**
 * Translates the screen's search params (URL names) into the question bank API's QuestionFilter names
 * (`apps/api/modules/questionbank/domain/filters.py`): the API reads `kinds`, `year_from`/`year_to` and `term_codes`,
 * and silently ignores unknown keys, so sending `kind=` used to leave the list unfiltered.
 */
export function buildQuestionQuery(params: QuestionSearchParams): URLSearchParams {
  const query = new URLSearchParams()
  if (params.q) query.set('q', params.q)
  if (params.subject) query.set('subject', params.subject)
  if (params.chapter) query.set('chapter', params.chapter)
  if (params.kind) query.set('kinds', params.kind)
  if (params.difficulty) query.set('difficulty', String(params.difficulty))
  if (params.year) {
    query.set('year_from', String(params.year))
    query.set('year_to', String(params.year))
  }
  if (params.term) query.set('term_codes', params.term)
  if (params.tag) query.set('tag', params.tag)
  if (params.cursor) query.set('cursor', params.cursor)
  if (params.limit) query.set('limit', String(params.limit))
  return query
}
