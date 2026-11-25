import { describe, expect, it } from 'vitest'
import en from '../src/i18n/en.json'
import kk from '../src/i18n/kk.json'
import ru from '../src/i18n/ru.json'
import { DEFAULT_LANG, hasKey, translate } from '../src/i18n'

const KEYS = Object.keys(ru)

function placeholders(text: string): string[] {
  return [...text.matchAll(/\{(\w+)\}/g)].map((found) => found[1] ?? '').sort()
}

describe('texts', () => {
  it('start in Russian', () => {
    expect(DEFAULT_LANG).toBe('ru')
  })

  it.each([
    ['kk', kk],
    ['en', en],
  ] as const)('%s has every key and the same placeholders', (_, texts) => {
    expect(Object.keys(texts)).toEqual(KEYS)
    for (const key of KEYS) {
      const name = key as keyof typeof ru
      expect(placeholders(texts[name]), key).toEqual(placeholders(ru[name]))
      expect(texts[name].trim(), key).not.toBe('')
    }
  })

  it('never name the bank', () => {
    for (const texts of [ru, kk, en]) {
      expect(JSON.stringify(texts)).not.toMatch(/BCC|БЦК|CenterCredit|ЦентрКредит/i)
    }
  })

  it('fill in values and leave unknown placeholders', () => {
    expect(translate('en', 'match.probability', { p: 97 })).toBe('probability 97%')
    expect(translate('en', 'match.probability')).toBe('probability {p}%')
  })

  it('know their own keys', () => {
    expect(hasKey('status.credited')).toBe(true)
    expect(hasKey('toString')).toBe(false)
  })
})
