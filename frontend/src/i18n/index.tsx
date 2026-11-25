import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import en from './en.json'
import kk from './kk.json'
import ru from './ru.json'

export type Lang = 'ru' | 'kk' | 'en'
export type Key = keyof typeof ru
export type Params = Readonly<Record<string, string | number>>
export type Translate = (key: Key, params?: Params) => string

export const LANGS: readonly Lang[] = ['ru', 'kk', 'en']
export const DEFAULT_LANG: Lang = 'ru'

const TEXTS: Readonly<Record<Lang, Readonly<Record<Key, string>>>> = { ru, kk, en }
const STORAGE_PREFIX = 'bothsides.lang.'

export function translate(lang: Lang, key: Key, params: Params = {}): string {
  const text: string = TEXTS[lang][key]
  return text.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in params ? String(params[name]) : whole,
  )
}

export function hasKey(key: string): key is Key {
  return Object.hasOwn(ru, key)
}

function isLang(value: string | null): value is Lang {
  return value !== null && (LANGS as readonly string[]).includes(value)
}

// Each screen remembers its own language, so the two phones may differ.
function readLang(screen: string): Lang {
  try {
    const stored = window.localStorage.getItem(STORAGE_PREFIX + screen)
    return isLang(stored) ? stored : DEFAULT_LANG
  } catch {
    return DEFAULT_LANG
  }
}

function writeLang(screen: string, lang: Lang): void {
  try {
    window.localStorage.setItem(STORAGE_PREFIX + screen, lang)
  } catch {
    // Private windows may refuse storage. The choice then lasts for this page only.
  }
}

interface I18n {
  readonly lang: Lang
  readonly setLang: (lang: Lang) => void
  readonly t: Translate
}

const I18nContext = createContext<I18n | null>(null)

export function I18nProvider({ screen, children }: { screen: string; children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => readLang(screen))

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  // The stage inside the demo page follows the language of the demo page at once.
  useEffect(() => {
    const follow = (event: StorageEvent) => {
      if (event.key === STORAGE_PREFIX + screen && isLang(event.newValue)) setLangState(event.newValue)
    }
    window.addEventListener('storage', follow)
    return () => window.removeEventListener('storage', follow)
  }, [screen])

  const setLang = useCallback(
    (next: Lang) => {
      writeLang(screen, next)
      setLangState(next)
    },
    [screen],
  )

  const value = useMemo<I18n>(
    () => ({ lang, setLang, t: (key, params) => translate(lang, key, params) }),
    [lang, setLang],
  )
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18n {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n needs an I18nProvider')
  return value
}

export function useTitle(title: string): void {
  useEffect(() => {
    document.title = `${title} · Both sides`
  }, [title])
}
