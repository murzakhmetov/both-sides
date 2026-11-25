import { describe, expect, it } from 'vitest'
import { formatAmount, formatDeadline, formatExactPercent, formatMoment, formatPercent, formatSeconds } from '../src/format'

describe('dates', () => {
  it('shows bank time whatever the zone of the string', () => {
    expect(formatDeadline('2026-12-03T18:00:00.000+05:00', 'en')).toBe('3 December, 18:00')
    expect(formatDeadline('2026-12-03T13:00:00.000Z', 'en')).toBe('3 December, 18:00')
  })

  it('has Russian and Kazakh month names of its own', () => {
    expect(formatDeadline('2026-12-03T18:00:00+05:00', 'ru')).toBe('3 декабря, 18:00')
    expect(formatDeadline('2026-12-03T18:00:00+05:00', 'kk')).toBe('3 желтоқсан, 18:00')
  })

  it('crosses midnight and the year in bank time', () => {
    expect(formatMoment('2026-12-31T19:00:05Z', 'en')).toBe('1 January, 00:00:05')
  })

  it('leaves a broken date as it is', () => {
    expect(formatDeadline('not a date', 'ru')).toBe('not a date')
    expect(formatMoment('not a date', 'ru')).toBe('not a date')
  })
})

describe('numbers', () => {
  it('groups amounts with narrow spaces that do not break', () => {
    expect(formatAmount(90000)).toBe('90 000 ₸')
    expect(formatAmount(1234567)).toBe('1 234 567 ₸')
    expect(formatAmount(5)).toBe('5 ₸')
  })

  it('never shows a flat 0 or 100 percent', () => {
    expect(formatPercent(0)).toBe('<1')
    expect(formatPercent(0.004)).toBe('<1')
    expect(formatPercent(0.969)).toBe('96')
    expect(formatPercent(1)).toBe('>99')
  })

  it('never shows a score just under a threshold as the threshold', () => {
    expect(formatPercent(0.7999)).toBe('79')
    expect(formatPercent(0.8)).toBe('80')
    expect(formatPercent(0.3499)).toBe('34')
    expect(formatPercent(0.35)).toBe('35')
    expect(formatPercent(0.29)).toBe('29')
  })

  it('shows the exact score in the decision trail', () => {
    expect(formatExactPercent(0.7999, 'en')).toBe('79.99')
    expect(formatExactPercent(0.06, 'ru')).toBe('6,00')
  })

  it('uses a comma for seconds in Russian and Kazakh', () => {
    expect(formatSeconds(12.34, 'ru')).toBe('12,3')
    expect(formatSeconds(12.34, 'kk')).toBe('12,3')
    expect(formatSeconds(12.34, 'en')).toBe('12.3')
  })
})
