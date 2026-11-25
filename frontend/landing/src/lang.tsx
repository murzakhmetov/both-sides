import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import appEn from '../../src/i18n/en.json'
import appKk from '../../src/i18n/kk.json'
import appRu from '../../src/i18n/ru.json'
import { LANGS, TEXTS, fill, type Lang, type TextKey, type Values } from './texts'

/** The app's own words: statuses, questions and reasons stay the same on both pages. */
const APP_TEXTS = { en: appEn, ru: appRu, kk: appKk } as const
export type AppKey = keyof typeof appEn

const STORAGE_KEY = 'both-sides-landing-lang'
const DEFAULT_LANG: Lang = 'en'

interface LangState {
  readonly lang: Lang
  readonly setLang: (lang: Lang) => void
  readonly t: (key: TextKey, values?: Values) => string
  readonly app: (key: AppKey, values?: Values) => string
  /** The words for a reason code of the server, or null for a code this page does not know. */
  readonly reason: (code: string) => string | null
}

const LangContext = createContext<LangState | null>(null)

function isAppKey(key: string): key is AppKey {
  return Object.hasOwn(appEn, key)
}

/** See {@link LangState.reason}. */
export function reasonText(lang: Lang, code: string): string | null {
  const key = `reason.${code}`
  return isAppKey(key) ? APP_TEXTS[lang][key] : null
}

function isLang(value: unknown): value is Lang {
  return LANGS.some((lang) => lang === value)
}

/** A private window may refuse storage; the page then starts in English. */
function storedLang(): Lang {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY)
    return isLang(saved) ? saved : DEFAULT_LANG
  } catch {
    return DEFAULT_LANG
  }
}

function remember(lang: Lang): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    // Nothing to do: the choice lasts until the page is closed.
  }
}

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setCurrent] = useState<Lang>(storedLang)

  const setLang = useCallback((next: Lang) => {
    remember(next)
    setCurrent(next)
  }, [])

  useEffect(() => {
    document.documentElement.lang = lang
    document.title = TEXTS[lang]['meta.title']
    document.querySelector('meta[name="description"]')?.setAttribute('content', TEXTS[lang]['meta.description'])
  }, [lang])

  const state = useMemo<LangState>(
    () => ({
      lang,
      setLang,
      t: (key, values) => fill(TEXTS[lang][key], values),
      app: (key, values) => fill(APP_TEXTS[lang][key], values),
      reason: (code) => reasonText(lang, code),
    }),
    [lang, setLang],
  )
  return <LangContext value={state}>{children}</LangContext>
}

export function useLang(): LangState {
  const state = useContext(LangContext)
  if (!state) throw new Error('useLang needs a LangProvider')
  return state
}
