import type { ReactNode, RefObject } from 'react'
import type { PhoneView } from '../api/types'
import { useI18n } from '../i18n'
import { Amount, Avatar } from './people'
import { BetaNote, Brand, LanguageSwitch, Problem } from './ui'

/** The other person, top left, where a bank app shows whose account it is. */
function OtherPerson({ view }: { view: PhoneView }) {
  const { lang, t } = useI18n()
  const name = view.other_name[lang]
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <Avatar name={name} tone={view.side === 'receiver' ? 'hero' : 'action'} />
      <p className="min-w-0 text-lg leading-tight">
        <span className="block text-on-hero-muted">{t(view.side === 'receiver' ? 'side.sender' : 'side.receiver')}</span>
        <span className="block truncate font-bold">{name}</span>
      </p>
    </div>
  )
}

function Hero({ view }: { view: PhoneView | null }) {
  const { t } = useI18n()
  return (
    <header className="hero px-4 pt-2 pb-11">
      <div className="flex min-h-12 items-center justify-between gap-2">
        {view ? <OtherPerson view={view} /> : <Brand />}
        <LanguageSwitch onHero />
      </div>
      {view && (
        <div className="mt-3 text-center">
          <p className="text-lg leading-tight text-on-hero-muted">
            {t(view.side === 'receiver' ? 'phone.incoming' : 'phone.outgoing')}
          </p>
          <p className="font-display text-5xl leading-tight font-bold tracking-tight">
            <Amount value={view.amount} />
          </p>
        </div>
      )}
    </header>
  )
}

function Footer({ view }: { view: PhoneView | null }) {
  const { t } = useI18n()
  return (
    <footer className="space-y-1 px-5 pt-2 pb-3 text-center text-lg leading-snug text-balance text-muted">
      {view && (
        <p data-numeric>
          {t('phone.case_number')}: <span className="font-semibold text-text">{view.case_number}</span>
        </p>
      )}
      <p>{t('app.prototype')}</p>
      <BetaNote />
    </footer>
  )
}

interface PhoneShellProps {
  readonly view: PhoneView | null
  /** Code of the last failed poll. */
  readonly problem: string
  readonly area: RefObject<HTMLElement | null>
  readonly children: ReactNode
}

/** A coloured top with the amount, and a white sheet that slides over it. */
export function PhoneShell({ view, problem, area, children }: PhoneShellProps) {
  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-md flex-col bg-surface">
      <Hero view={view} />
      <main className="-mt-7 flex-1 rounded-t-sheet bg-surface px-4 pt-4 pb-3" ref={area}>
        <Problem code={problem} />
        {children}
      </main>
      <Footer view={view} />
    </div>
  )
}
