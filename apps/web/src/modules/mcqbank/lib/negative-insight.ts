import type { AnswerInsightInput, ConfidenceBandStats, NegativeInsightReport } from './types'

/**
 * Computes negative-marking review insights from graded answers with confidence ratings.
 * Evaluates whether guessing paid off, break-even accuracy, penalties applied,
 * and sure-but-wrong concepts.
 *
 * Parity twin of backend `modules.mcqbank.domain.negative_insight`.
 */
export function computeNegativeInsight(answers: readonly AnswerInsightInput[]): NegativeInsightReport {
  let totalPenalties = 0
  let penalisedCount = 0
  let sureButWrong = 0

  let sampleNeg = 0
  let samplePos = 0

  for (const a of answers) {
    if (a.negative_max > 0 && sampleNeg === 0) {
      sampleNeg = a.negative_max
      samplePos = a.marks_max
    }
  }

  let breakEvenPct: number | null = null
  if (sampleNeg > 0 && samplePos + sampleNeg > 0) {
    breakEvenPct = Math.round((sampleNeg / (samplePos + sampleNeg)) * 1000) / 10
  }

  const bands: Record<1 | 2 | 3, { n: number; correct: number; net: number }> = {
    1: { n: 0, correct: 0, net: 0 },
    2: { n: 0, correct: 0, net: 0 },
    3: { n: 0, correct: 0, net: 0 },
  }

  for (const a of answers) {
    if (a.negative_applied > 0) {
      totalPenalties += a.negative_applied
      penalisedCount += 1
    }

    const conf = a.confidence
    if (conf && conf in bands) {
      const b = bands[conf as 1 | 2 | 3]
      b.n += 1
      if (a.result === 'correct') {
        b.correct += 1
      }
      b.net += a.marks_awarded
    }

    if (conf === 1 && (a.result === 'incorrect' || a.result === 'partial')) {
      sureButWrong += 1
    }
  }

  function buildBandStats(confId: 1 | 2 | 3): ConfidenceBandStats {
    const b = bands[confId]
    const cnt = b.n
    const corr = b.correct
    const acc = cnt > 0 ? Math.round((corr / cnt) * 1000) / 10 : 0
    const payingOff = breakEvenPct !== null && cnt > 0 ? acc > breakEvenPct : null

    return {
      count: cnt,
      correct_count: corr,
      accuracy_pct: acc,
      net_marks: Math.round(b.net * 100) / 100,
      paying_off: payingOff,
    }
  }

  return {
    total_penalties: Math.round(totalPenalties * 100) / 100,
    penalised_count: penalisedCount,
    break_even_pct: breakEvenPct,
    sure_but_wrong_count: sureButWrong,
    sure: buildBandStats(1),
    unsure: buildBandStats(2),
    guess: buildBandStats(3),
  }
}
