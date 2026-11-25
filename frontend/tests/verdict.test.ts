import { describe, expect, it } from 'vitest'
import type { CaseFile, CaseState, Tri } from '../src/api/types'
import { fitScale } from '../src/hooks/useFit'
import { barColor, verdictOf } from '../src/verdict'

const THRESHOLDS = { release: 0.8, hold: 0.35, repeated_story: 2 }

function file(state: CaseState, probability?: number, reason: Tri = 'true', thresholds = THRESHOLDS, relation: Tri = 'unknown'): CaseFile {
  const match = probability === undefined ? null : { probability, same_reason: reason, same_relation: relation }
  return { state, match, thresholds } as unknown as CaseFile
}

describe('verdict words', () => {
  it.each([
    [file('awaiting_receiver'), 'pending'],
    [file('awaiting_sender'), 'pending'],
    [file('comparing'), 'comparing'],
    [file('with_specialist'), 'not_compared'],
    [file('credited', 0.97), 'same'],
    [file('credited', 0.8), 'same'],
    [file('with_specialist', 0.97, 'unknown'), 'unclear'],
    [file('with_specialist', 0.6), 'unclear'],
    [file('with_specialist', 0.35, 'false'), 'unclear'],
    [file('held', 0.02, 'false'), 'differ'],
    // The same nonsense on both phones: a low score, but nothing contradicts anything.
    [file('with_specialist', 0.31, 'unknown'), 'unclear'],
    [file('with_specialist', 0.12, 'unknown', THRESHOLDS, 'false'), 'differ'],
    [file('with_specialist', 0.12, 'true'), 'differ'],
  ] as const)('case %#', (input, expected) => {
    expect(verdictOf(input)).toBe(expected)
  })

  it('follow the thresholds of the server', () => {
    const strict = { ...THRESHOLDS, release: 0.9, hold: 0.7 }
    expect(verdictOf(file('with_specialist', 0.85, 'true', strict))).toBe('unclear')
    expect(verdictOf(file('with_specialist', 0.65, 'false', strict))).toBe('differ')
  })

  it('keeps green for credited, amber for a specialist, red for holds', () => {
    expect(barColor(file('held', 0.02, 'false'), 'differ')).toBe('bg-held')
    expect(barColor(file('with_specialist', 0.02, 'false'), 'differ')).toBe('bg-specialist-fill')
    expect(barColor(file('credited', 0.97), 'same')).toBe('bg-credited')
    expect(barColor(file('with_specialist', 0.97), 'same')).toBe('bg-specialist-fill')
    expect(barColor(file('credited', 0.41, 'unknown'), 'unclear')).toBe('bg-line-strong')
    expect(barColor(file('returned', 0.02, 'false'), 'differ')).toBe('bg-line-strong')
    expect(barColor(file('returned', 0.97), 'same')).toBe('bg-line-strong')
  })
})

describe('phone scale', () => {
  it('shrinks to fit and never enlarges', () => {
    expect(fitScale({ width: 400, height: 800 }, { width: 400, height: 400 })).toBe(0.5)
    expect(fitScale({ width: 400, height: 800 }, { width: 200, height: 800 })).toBe(0.5)
    expect(fitScale({ width: 400, height: 800 }, { width: 900, height: 1600 })).toBe(1)
    expect(fitScale({ width: 400, height: 800 }, { width: 0, height: 0 })).toBe(1)
  })
})
