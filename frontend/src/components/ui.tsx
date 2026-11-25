import type { ButtonHTMLAttributes, MouseEvent, ReactNode } from 'react'
import { LANGS, hasKey, useI18n, type Lang, type Translate } from '../i18n'
import { Mark } from './icons'

type Variant = 'primary' | 'tonal' | 'outline' | 'danger' | 'danger-solid' | 'quiet'

const VARIANTS: Readonly<Record<Variant, string>> = {
  primary: 'bg-action text-on-action hover:bg-action-strong',
  tonal: 'bg-sunken text-text hover:bg-line',
  outline: 'border border-line-strong bg-surface text-text hover:bg-sunken',
  danger: 'bg-held-soft text-held hover:ring-2 hover:ring-held hover:ring-inset',
  'danger-solid': 'bg-held text-surface',
  quiet: 'text-text hover:bg-sunken',
}

const SIZES = {
  phone: 'min-h-13 px-6 text-lg',
  desk: 'min-h-11 px-5 text-base',
  small: 'min-h-11 px-4 text-sm',
} as const

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly variant?: Variant
  readonly size?: keyof typeof SIZES
  /** Not possible now. The button keeps the keyboard focus, unlike a disabled one. */
  readonly inactive?: boolean
}

export function Button({
  variant = 'primary',
  size = 'phone',
  className = '',
  type = 'button',
  inactive = false,
  onClick,
  ...rest
}: ButtonProps) {
  const click = (event: MouseEvent<HTMLButtonElement>) => {
    if (inactive) {
      event.preventDefault()
      return
    }
    onClick?.(event)
  }
  return (
    <button
      aria-disabled={inactive || undefined}
      className={`relative inline-flex touch-manipulation items-center justify-center gap-2 overflow-hidden rounded-full font-bold transition duration-150 motion-safe:active:scale-[0.98] aria-disabled:cursor-default aria-disabled:opacity-50 ${SIZES[size]} ${VARIANTS[variant]} ${className}`}
      onClick={click}
      type={type}
      {...rest}
    />
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-card bg-surface shadow-(--shadow) ${className}`}>{children}</section>
}

/** An icon in a circle, like the rows of a bank app. */
export function IconCircle({ children, className = 'size-11 bg-sunken text-accent' }: { children: ReactNode; className?: string }) {
  return <span className={`inline-flex shrink-0 items-center justify-center rounded-full ${className}`}>{children}</span>
}

/** Three dots that breathe while the bank works. */
export function Waiting({ className = '' }: { className?: string }) {
  return (
    <span aria-hidden="true" className={`inline-flex gap-1.5 ${className}`}>
      {['[animation-delay:0ms]', '[animation-delay:200ms]', '[animation-delay:400ms]'].map((delay) => (
        <span className={`size-2.5 animate-breathe rounded-full bg-accent ${delay}`} key={delay} />
      ))}
    </span>
  )
}

/** The chosen option of a group is a filled pill, so it differs by much more than a tint. */
export function choiceClass(chosen: boolean): string {
  return chosen ? 'bg-text text-surface' : 'text-muted hover:text-text'
}

function heroChoiceClass(chosen: boolean): string {
  return chosen ? 'bg-action text-on-action' : 'text-on-hero'
}

const LANG_LABELS: Readonly<Record<Lang, string>> = { ru: 'РУС', kk: 'ҚАЗ', en: 'ENG' }
const LANG_NAMES: Readonly<Record<Lang, string>> = { ru: 'Русский', kk: 'Қазақша', en: 'English' }

export function LanguageSwitch({ onHero = false }: { onHero?: boolean }) {
  const { lang, setLang, t } = useI18n()
  const choice = onHero ? heroChoiceClass : choiceClass
  return (
    <div
      aria-label={t('lang.label')}
      className={`flex shrink-0 rounded-full ${onHero ? 'bg-hero-chip' : 'bg-sunken'}`}
      role="group"
    >
      {LANGS.map((item) => (
        <button
          aria-label={item === 'kk' ? `${LANG_NAMES[item]} (${t('lang.beta')})` : LANG_NAMES[item]}
          aria-pressed={item === lang}
          className={`flex min-h-12 min-w-12 touch-manipulation flex-col items-center justify-center rounded-full px-1.5 text-sm leading-tight font-bold transition-colors duration-150 ${choice(item === lang)}`}
          key={item}
          lang={item}
          onClick={() => setLang(item)}
          type="button"
        >
          {LANG_LABELS[item]}
          {item === 'kk' && <span className="text-xs leading-none font-normal">{t('lang.beta')}</span>}
        </button>
      ))}
    </div>
  )
}

/** Shown on Kazakh screens until a native speaker has read the texts. */
export function BetaNote({ className = '' }: { className?: string }) {
  const { lang, t } = useI18n()
  if (lang !== 'kk') return null
  return <p className={`text-muted ${className}`}>{t('lang.beta_note')}</p>
}

/** A sentence for an error code of the server. */
export function errorText(code: string, t: Translate): string {
  if (code === 'offline') return t('app.offline')
  const key = `error.${code}`
  return t(hasKey(key) ? key : 'error.generic')
}

/** Says why the screen may be out of date. A missing login is handled elsewhere. */
export function Problem({ code }: { code: string }) {
  const { t } = useI18n()
  return (
    <div data-no-print role="status">
      {code !== '' && code !== 'login_required' && (
        <p className="m-2 animate-fade rounded-tile bg-text px-4 py-2 text-center text-lg leading-snug font-semibold text-surface">
          {errorText(code, t)}
        </p>
      )}
    </div>
  )
}

export function Brand() {
  return (
    <span className="inline-flex items-center gap-2 text-lg font-bold whitespace-nowrap">
      <Mark /> Both sides
    </span>
  )
}

/** A link in the bar at the top. */
export const TOP_LINK = 'inline-flex min-h-11 items-center rounded-full px-4 text-base font-bold hover:bg-sunken'

/** The bar at the top of the staff pages. */
export function TopBar({ children }: { children?: ReactNode }) {
  return (
    <header
      className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 bg-surface px-4 py-1.5 shadow-(--shadow) sm:px-6 dark:border-b dark:border-line"
      data-no-print
    >
      <a className="rounded-full text-accent" href="/start">
        <Brand />
      </a>
      {children && (
        <div className="flex flex-wrap items-center gap-2 max-sm:order-last max-sm:w-full sm:ml-auto">{children}</div>
      )}
      <LanguageSwitch />
    </header>
  )
}
