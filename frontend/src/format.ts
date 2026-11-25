import type { Lang } from './i18n'

// Some browsers have no Kazakh month names, so dates are put together here.
const MONTHS: Readonly<Record<Lang, readonly string[]>> = {
  ru: ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
  kk: ['қаңтар', 'ақпан', 'наурыз', 'сәуір', 'мамыр', 'маусым', 'шілде', 'тамыз', 'қыркүйек', 'қазан', 'қараша', 'желтоқсан'],
  en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
}

// Kazakhstan has one zone, UTC+5. A fixed shift avoids old time-zone tables in browsers.
const BANK_OFFSET_MS = 5 * 60 * 60 * 1000

const NARROW_SPACE = ' '

export function formatAmount(amount: number): string {
  const digits = Math.trunc(amount).toString()
  return `${digits.replace(/\B(?=(\d{3})+(?!\d))/g, NARROW_SPACE)}${NARROW_SPACE}₸`
}

function twoDigits(value: number): string {
  return String(value).padStart(2, '0')
}

function bankTime(iso: string): Date | null {
  const time = new Date(iso).getTime()
  return Number.isNaN(time) ? null : new Date(time + BANK_OFFSET_MS)
}

function dayAndMonth(date: Date, lang: Lang): string {
  return `${date.getUTCDate()} ${MONTHS[lang][date.getUTCMonth()] ?? ''}`
}

/** 3 December, 18:00 in bank time. */
export function formatDeadline(iso: string, lang: Lang): string {
  const date = bankTime(iso)
  if (!date) return iso
  return `${dayAndMonth(date, lang)}, ${twoDigits(date.getUTCHours())}:${twoDigits(date.getUTCMinutes())}`
}

/** 26 November, 12:00:05 in bank time. */
export function formatMoment(iso: string, lang: Lang): string {
  const date = bankTime(iso)
  return date ? `${formatDeadline(iso, lang)}:${twoDigits(date.getUTCSeconds())}` : iso
}

/**
 * Never shows a flat 0 or 100: no score is that certain. Rounds down, so that a
 * score just under a threshold is not shown as the threshold itself.
 */
export function formatPercent(probability: number): string {
  if (probability < 0.01) return '<1'
  if (probability > 0.99) return '>99'
  // 0.29 * 100 is a little less than 29 in floating point.
  return String(Math.floor(probability * 100 + 1e-9))
}

function decimal(value: number, digits: number, lang: Lang): string {
  const text = value.toFixed(digits)
  return lang === 'en' ? text : text.replace('.', ',')
}

/** With two decimals, for the decision trail. */
export function formatExactPercent(probability: number, lang: Lang): string {
  return decimal(probability * 100, 2, lang)
}

export function formatSeconds(seconds: number, lang: Lang): string {
  return decimal(seconds, 1, lang)
}
