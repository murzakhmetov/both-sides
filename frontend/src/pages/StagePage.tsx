import type { CaseFile, Side, StageView } from '../api/types'
import { CompactDecision, Decision } from '../components/Decision'
import { Facts, FactTiles } from '../components/Facts'
import { LockIcon, Mark } from '../components/icons'
import { MatchBar } from '../components/MatchBar'
import { Spoken, StagePhone } from '../components/StagePhone'
import { BetaNote, Card, LanguageSwitch, Problem } from '../components/ui'
import { formatAmount } from '../format'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { usePoll } from '../hooks/usePoll'
import { useStaffOnly } from '../hooks/useStaffOnly'
import { hasKey, useI18n, useTitle, type Key } from '../i18n'

const POLL_MS = 700
/** A laptop, or a browser that is not in full screen. The hall screen is taller. */
const SHORT_SCREEN = '(max-height: 1059px)'
const SIDES: readonly Side[] = ['receiver', 'sender']

const STEPS: readonly Key[] = [
  'stage.step.stopped',
  'stage.step.receiver',
  'stage.step.sender',
  'stage.step.compared',
  'stage.step.decided',
]

/** How many of the five steps are done. */
function stepsDone(file: CaseFile): number {
  if (file.decided_at !== null) return STEPS.length
  if (file.state === 'comparing') return 3
  return file.state === 'awaiting_sender' ? 2 : 1
}

/** A denial or a missing answer ends the case before the later steps happen. */
function wasSkipped(file: CaseFile, index: number): boolean {
  if (file.decided_at === null || index === 0 || index === STEPS.length - 1) return false
  const happened = [true, true, file.trail.some((entry) => entry.event === 'sender_asked'), file.match !== null]
  return !happened[index]
}

function Steps({ file, large = false }: { file: CaseFile; large?: boolean }) {
  const { t } = useI18n()
  const done = stepsDone(file)
  return (
    <div>
      <ol className="grid grid-cols-5 gap-2">
        {STEPS.map((key, index) => {
          const skipped = wasSkipped(file, index)
          const reached = index < done && !skipped
          const tone = index <= done && !skipped ? 'font-semibold text-text' : 'text-muted'
          return (
            <li aria-current={index === done ? 'step' : undefined} key={key}>
              <span className={`block h-2 rounded-full transition-colors duration-200 ${reached ? 'bg-accent' : 'bg-line'}`} />
              <span
                className={`mt-1 max-[539px]:sr-only block leading-tight ${large ? 'text-base hall:text-xl' : 'text-sm'} ${tone} ${
                  skipped ? 'line-through' : ''
                }`}
              >
                {t(key)}
              </span>
            </li>
          )
        })}
      </ol>
      <p aria-hidden="true" className="mt-1 font-semibold min-[540px]:hidden">{t(STEPS[Math.min(done, STEPS.length - 1)] ?? 'stage.step.decided')}</p>
    </div>
  )
}

function Header({ stage }: { stage: StageView }) {
  const { t } = useI18n()
  const file = stage.case
  const sceneKey = `scene.${stage.scene ?? ''}.name`
  return (
    <header className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-4">
        <span className="hero inline-flex size-14 shrink-0 items-center justify-center rounded-full">
          <Mark className="size-9" left={file.receiver_answer !== null || file.denied} right={file.sender_answer !== null} />
        </span>
        <div>
          <h1 className="text-2xl leading-tight font-bold tracking-tight xl:text-4xl">{t('stage.title')}</h1>
          <p className="text-lg leading-tight text-muted hall:text-xl">
            {hasKey(sceneKey) && `${t(sceneKey)} · `}
            <span data-numeric>{formatAmount(file.amount)}</span>
          </p>
        </div>
      </div>
      <LanguageSwitch />
    </header>
  )
}

function CompactCenter({ stage }: { stage: StageView }) {
  return (
    <>
      <Card className="px-4 py-2.5">
        <MatchBar file={stage.case} />
      </Card>
      <CompactDecision stage={stage} />
      <Card className="px-4 py-2.5">
        <FactTiles file={stage.case} />
      </Card>
    </>
  )
}

function Center({ stage }: { stage: StageView }) {
  return (
    <>
      <Card className="px-6 py-3">
        <MatchBar file={stage.case} large />
      </Card>
      <Decision stage={stage} />
      <Card className="px-6 py-3">
        <Facts file={stage.case} large />
      </Card>
    </>
  )
}

function FullStage({ stage }: { stage: StageView }) {
  const { t } = useI18n()
  const short = useMediaQuery(SHORT_SCREEN)
  return (
    <>
      <Header stage={stage} />
      <Steps file={stage.case} large />
      <div className={`grid flex-1 gap-4 ${short ? 'lg:grid-cols-[1fr_1.7fr_1fr]' : 'lg:grid-cols-[1fr_1.35fr_1fr]'}`}>
        <StagePhone side="receiver" stage={stage} />
        <div className="flex flex-col justify-center gap-2.5">
          {short ? <CompactCenter stage={stage} /> : <Center stage={stage} />}
        </div>
        <StagePhone side="sender" stage={stage} />
      </div>
      <div className="flex flex-wrap items-center justify-center gap-x-3 text-base text-muted">
        <p className="flex items-center gap-2">
          <LockIcon /> {t('stage.hidden_between')} · {t('app.prototype')}
        </p>
        <BetaNote />
      </div>
    </>
  )
}

/** The phones beside this frame no longer show what was typed, so the answers stand here. */
function Answers({ stage }: { stage: StageView }) {
  const { t } = useI18n()
  return (
    <div className="grid grid-cols-2 gap-2.5">
      {SIDES.map((side) => (
        <section aria-label={t(`phone.title.${side}`)} className="min-w-0" key={side}>
          <p className={`text-sm leading-tight text-muted ${side === 'sender' ? 'text-right' : ''}`}>{t(`side.${side}`)}</p>
          <div aria-live="polite" className="mt-0.5">
            <Spoken compact side={side} stage={stage} />
          </div>
        </section>
      ))}
    </div>
  )
}

/** Inside the demo page the real phones stand on both sides, so only the middle is shown. */
function EmbeddedStage({ stage }: { stage: StageView }) {
  return (
    <>
      <Steps file={stage.case} />
      <Answers stage={stage} />
      <CompactCenter stage={stage} />
    </>
  )
}

export function StagePage({ embedded }: { embedded: boolean }) {
  const { t } = useI18n()
  const poll = usePoll<StageView>('/api/stage', POLL_MS)
  useStaffOnly(poll.errorCode)
  useTitle(t('stage.document'))
  return (
    <>
      <Problem code={poll.errorCode} />
      <main className={`mx-auto flex max-w-[1800px] flex-col ${embedded ? 'gap-2 px-1 py-1' : 'min-h-dvh gap-3 p-4'}`}>
        {!poll.data && <p className="text-lg text-muted">{t('app.loading')}</p>}
        {poll.data && (embedded ? <EmbeddedStage stage={poll.data} /> : <FullStage stage={poll.data} />)}
      </main>
    </>
  )
}
