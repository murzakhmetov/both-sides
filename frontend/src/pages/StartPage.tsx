import type { ReactNode } from 'react'
import type { StatusView } from '../api/types'
import { ChevronIcon, FolderIcon, LockIcon, PhoneIcon, ScreenIcon } from '../components/icons'
import { BetaNote, Brand, Card, IconCircle, LanguageSwitch, Problem, Waiting } from '../components/ui'
import { usePoll } from '../hooks/usePoll'
import { hasKey, useI18n, useTitle, type Key } from '../i18n'

const POLL_MS = 5000
const STEPS: readonly Key[] = ['start.how.1', 'start.how.2', 'start.how.3', 'start.how.4']
const SCENES = ['brother', 'sister', 'stranger'] as const

interface LinkItem {
  readonly href: string
  readonly label: Key
  readonly icon: ReactNode
}

const PHONES: readonly LinkItem[] = [
  { href: '/receiver', label: 'phone.title.receiver', icon: <PhoneIcon /> },
  { href: '/sender', label: 'phone.title.sender', icon: <PhoneIcon /> },
]
const STAFF: readonly LinkItem[] = [
  { href: '/demo', label: 'demo.title', icon: <ScreenIcon /> },
  { href: '/stage', label: 'stage.document', icon: <ScreenIcon /> },
  { href: '/console', label: 'console.title', icon: <FolderIcon /> },
]

interface LinksProps {
  readonly title: string
  readonly text: string
  readonly items: readonly LinkItem[]
  readonly locked: boolean
}

function Links({ title, text, items, locked }: LinksProps) {
  const { t } = useI18n()
  return (
    <Card className="px-5 pt-5 pb-3">
      <h2 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
        {title}
        {locked && <LockIcon className="size-5 text-muted" />}
      </h2>
      <p className="text-muted">{text}</p>
      <ul className="mt-2">
        {items.map((item) => (
          <li key={item.href}>
            <a
              className="-mx-2 flex min-h-16 items-center gap-3 rounded-tile px-2 text-lg font-bold hover:bg-sunken"
              href={item.href}
            >
              <IconCircle>{item.icon}</IconCircle>
              <span className="flex-1">{t(item.label)}</span>
              <ChevronIcon className="size-5 text-muted" />
            </a>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function Matcher({ status }: { status: StatusView | null }) {
  const { t } = useI18n()
  if (!status) return <Waiting />
  const { matcher } = status
  if (matcher.active === 'gemini') {
    const stateKey = `start.model.${matcher.model_state}`
    return (
      <>
        <p className="text-2xl font-bold tracking-tight">{t('start.matcher.gemini', { model: matcher.model })}</p>
        {hasKey(stateKey) && <p className="mt-1">{t(stateKey)}</p>}
        <p className="mt-1 text-muted">{t('start.matcher.gemini_note')}</p>
      </>
    )
  }
  const reasonKey = `start.matcher.offline.${matcher.reason}`
  return (
    <>
      <p className="text-2xl font-bold tracking-tight">{t('start.matcher.offline')}</p>
      {hasKey(reasonKey) && <p className="mt-1">{t(reasonKey)}</p>}
      <p className="mt-1 text-muted">{t('start.honest')}</p>
    </>
  )
}

/** A numbered row of a list. */
function Numbered({ number, children }: { number: number; children: ReactNode }) {
  return (
    <li className="flex gap-3.5 py-2.5">
      <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-sunken font-bold text-accent" data-numeric>
        {number}
      </span>
      <span className="pt-1">{children}</span>
    </li>
  )
}

function Hero() {
  const { t } = useI18n()
  return (
    <div className="hero">
      <header className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-2 sm:px-6">
        <Brand />
        <LanguageSwitch onHero />
      </header>
      <div className="mx-auto max-w-5xl px-4 pt-8 pb-24 sm:px-6 sm:pt-14 sm:pb-28">
        <h1 className="max-w-3xl text-4xl leading-[1.05] font-extrabold tracking-tight sm:text-7xl">{t('start.title')}</h1>
        <p className="mt-4 max-w-2xl text-lg text-on-hero-muted sm:text-xl">{t('start.lead')}</p>
      </div>
    </div>
  )
}

export function StartPage() {
  const { t } = useI18n()
  const status = usePoll<StatusView>('/api/status', POLL_MS)
  const sandbox = status.data?.sandbox ?? false
  // Until the server has said which of the two it is, neither sentence is right.
  const told = (online: Parameters<typeof t>[0], laptop: Parameters<typeof t>[0]) => (status.data ? t(sandbox ? online : laptop) : '\u00a0')
  useTitle(t('start.title'))
  return (
    <div className="flex min-h-dvh flex-col">
      <Hero />
      <main className="mx-auto -mt-16 w-full max-w-5xl flex-1 px-4 pb-10 sm:px-6">
        <Problem code={status.errorCode} />
        <div className="grid gap-4 md:grid-cols-2">
          <Links items={PHONES} locked={false} text={told('start.phones.online', 'start.phones.text')} title={t('start.phones')} />
          <Links items={STAFF} locked={status.data !== null && !sandbox} text={told('start.staff.online', 'start.staff.text')} title={t('start.staff')} />
        </div>

        <Card className="mt-4 p-5">
          <h2 className="text-base text-muted">{t('start.matcher')}</h2>
          <div aria-live="polite" className="mt-0.5">
            <Matcher status={status.data} />
          </div>
        </Card>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <Card className="p-5">
            <h2 className="text-2xl font-bold tracking-tight">{t('start.how')}</h2>
            <ol className="mt-1">
              {STEPS.map((key, index) => (
                <Numbered key={key} number={index + 1}>
                  {t(key)}
                </Numbered>
              ))}
            </ol>
          </Card>
          <Card className="p-5">
            <h2 className="text-2xl font-bold tracking-tight">{t('start.scenes')}</h2>
            <ol className="mt-1">
              {SCENES.map((scene, index) => (
                <Numbered key={scene} number={index + 1}>
                  <span className="block font-bold">{t(`scene.${scene}.name`)}</span>
                  <span className="block text-muted">{t(`scene.${scene}.text`)}</span>
                </Numbered>
              ))}
            </ol>
          </Card>
        </div>
      </main>
      <footer className="px-4 pb-6 text-center text-muted sm:px-6">
        <p>{t('app.prototype')}</p>
        <BetaNote className="mt-1" />
      </footer>
    </div>
  )
}
