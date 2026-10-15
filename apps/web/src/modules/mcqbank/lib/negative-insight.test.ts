import { describe, expect, it } from 'vitest'

import { computeNegativeInsight } from './negative-insight'
import type { AnswerInsightInput } from './types'

describe('computeNegativeInsight', () => {
  it('matches the exact ERD 3.5 test vector', () => {
    // 11 guesses: 4 right at +1, 7 wrong at -0.25
    // gives net_guess = 2.25, accuracy = 36.4%, break_even = 20%, paying_off = true
    const answers: AnswerInsightInput[] = []

    // 4 correct guesses
    for (let i = 0; i < 4; i++) {
      answers.push({
        result: 'correct',
        confidence: 3, // guess
        marks_max: 1.0,
        negative_max: 0.25,
        marks_awarded: 1.0,
        negative_applied: 0.0,
      })
    }

    // 7 incorrect guesses
    for (let i = 0; i < 7; i++) {
      answers.push({
        result: 'incorrect',
        confidence: 3, // guess
        marks_max: 1.0,
        negative_max: 0.25,
        marks_awarded: -0.25,
        negative_applied: 0.25,
      })
    }

    const report = computeNegativeInsight(answers)

    expect(report.total_penalties).toBe(1.75)
    expect(report.penalised_count).toBe(7)
    expect(report.break_even_pct).toBe(20.0)
    expect(report.guess.count).toBe(11)
    expect(report.guess.correct_count).toBe(4)
    expect(report.guess.accuracy_pct).toBe(36.4)
    expect(report.guess.net_marks).toBe(2.25)
    expect(report.guess.paying_off).toBe(true)
  })

  it('detects sure-but-wrong answers', () => {
    const answers: AnswerInsightInput[] = [
      {
        result: 'incorrect',
        confidence: 1, // sure
        marks_max: 2.0,
        negative_max: 0.5,
        marks_awarded: -0.5,
        negative_applied: 0.5,
      },
      {
        result: 'correct',
        confidence: 1, // sure
        marks_max: 2.0,
        negative_max: 0.5,
        marks_awarded: 2.0,
        negative_applied: 0.0,
      },
    ]

    const report = computeNegativeInsight(answers)
    expect(report.sure_but_wrong_count).toBe(1)
    expect(report.sure.count).toBe(2)
    expect(report.sure.correct_count).toBe(1)
    expect(report.sure.accuracy_pct).toBe(50.0)
  })
})
