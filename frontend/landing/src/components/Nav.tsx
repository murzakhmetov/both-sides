import { useEffect, useState, type ReactNode } from 'react'
import { useLang } from '../lang'
import mark from '../mark.svg'
import { SECTIONS, type SectionId } from '../sections'
import { ScrollTrigger, scrollToId } from '../scroll'
import { LANGS, LANG_FULL_NAMES, LANG_NAMES } from '../texts'
import { MotionButton } from './MotionButton'

const BETA_ID = 'beta-note'

/** The section in the middle of the window. */
function useCurrentSection(): SectionId {
  const [current, setCurrent] = useState<SectionId>('hero')
  useEffect(() => {
    const triggers = SECTIONS.map((id) =>
      ScrollTrigger.create({
        trigger: `#${id}`,
        start: 'top center',
        end: 'bottom center',
        onToggle: (self) => {
          if (self.isActive) setCurrent(id)
        },
      }),
    )
    return () => triggers.forEach((trigger) => trigger.kill())
  }, [])
  return current
}

interface JumpProps {
  readonly to: SectionId
  readonly className: string
  readonly current?: boolean
  readonly children: ReactNode
}

/** A link to a section: scrolls softly and moves the focus. */
function Jump({ to, className, current = false, children }: JumpProps) {
  return (
    <a
      aria-current={current ? 'location' : undefined}
      className={className}
      href={`#${to}`}
      onClick={(event) => {
        event.preventDefault()
        scrollToId(to)
      }}
    >
      {children}
    </a>
  )
}

function LangSwitch() {
  const { lang, setLang, t, app } = useLang()
  return (
    <div aria-label={t('lang.label')} className="flex rounded-[14px] border border-white/15 bg-ink/60 p-1" role="group">
      {LANGS.map((item) => (
        <button
          aria-describedby={item === 'kk' ? BETA_ID : undefined}
          aria-pressed={item === lang}
          className="min-h-11 min-w-11 cursor-pointer rounded-[10px] px-2 text-[0.875rem] leading-tight font-semibold text-muted transition-colors hover:text-text aria-pressed:bg-white/12 aria-pressed:text-text sm:px-2.5"
          key={item}
          lang={item}
          onClick={() => setLang(item)}
          type="button"
        >
          {LANG_NAMES[item]}
          <span className="sr-only"> {LANG_FULL_NAMES[item]}</span>
          {item === 'kk' && (
            <span aria-hidden="true" className="block text-[0.75rem] leading-none font-medium" lang={lang}>
              {app('lang.beta')}
            </span>
          )}
        </button>
      ))}
      <span className="sr-only" id={BETA_ID}>
        {t('lang.beta')}
      </span>
    </div>
  )
}

function Dots({ current }: { current: SectionId }) {
  const { t } = useLang()
  return (
    <nav aria-label={t('nav.sections')} className="fixed top-1/2 right-5 z-30 hidden -translate-y-1/2 lg:block">
      <ol className="flex flex-col">
        {SECTIONS.map((id) => (
          <li key={id}>
            <Jump className="group relative flex h-7 w-7 items-center justify-center" current={current === id} to={id}>
              <span className="h-1.5 w-1.5 rounded-full bg-white/50 transition-all duration-300 group-hover:bg-white group-aria-[current]:h-5 group-aria-[current]:bg-bcc-gold" />
              <span className="pointer-events-none absolute right-8 rounded-lg bg-panel px-3 py-1 text-[0.875rem] whitespace-nowrap opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                {t(`section.${id}`)}
              </span>
            </Jump>
          </li>
        ))}
      </ol>
    </nav>
  )
}

export function Nav() {
  const { t } = useLang()
  const current = useCurrentSection()
  return (
    <>
      <Jump className="button button-gold fixed top-3 left-3 z-50 -translate-y-24 focus:translate-y-0" to="problem">
        {t('skip')}
      </Jump>
      <header className="fixed inset-x-0 top-0 z-40 border-b border-white/8 bg-ink/94 pb-3 backdrop-blur-md">
        <div className="nav-bar shell flex min-h-18 items-center justify-between gap-3 pt-3">
          <Jump className="flex min-h-11 min-w-0 items-center gap-2 sm:gap-3" to="hero">
            <img alt="" className="hidden h-8 w-8 shrink-0 min-[25rem]:block" height="32" src={mark} width="32" />
            <span className="min-w-0 leading-tight">
              <span className="block font-display text-[1.05rem] font-medium tracking-tight whitespace-nowrap">{t('nav.name')}</span>
              <span className="caption hidden leading-tight sm:block">{t('nav.tag')}</span>
            </span>
          </Jump>
          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
            <a className="button hidden min-h-11 px-5 py-2 text-[0.94rem] md:inline-flex" href="/start">
              {t('nav.demo')}
            </a>
            <MotionButton />
            <LangSwitch />
          </div>
        </div>
      </header>
      <Dots current={current} />
    </>
  )
}
