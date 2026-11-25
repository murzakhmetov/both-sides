import type { PhoneStatus, Side, StageView } from '../api/types'
import { useI18n } from '../i18n'
import { Amount, Avatar } from './people'
import { lookOf } from './status'
import { Waiting } from './ui'

/** Longer answers get smaller letters, so that the result below stays on the screen. */
const LONG_ANSWER = 110

function bubbleSize(text: string): string {
  return text.length > LONG_ANSWER ? 'text-base hall:text-xl' : 'text-2xl hall:text-4xl'
}

/** What this person told the bank, as a chat bubble. Staff screens only. */
export function Spoken({ side, stage, compact = false }: { side: Side; stage: StageView; compact?: boolean }) {
  const { t } = useI18n()
  const file = stage.case
  const answer = side === 'receiver' ? file.receiver_answer : file.sender_answer
  const corner = side === 'receiver' ? 'rounded-bl-md' : 'rounded-br-md'
  const box = compact ? 'rounded-2xl px-3.5 py-2 text-base' : 'rounded-3xl px-5 py-4'
  const bubble = `animate-enter leading-snug font-bold ${box} ${corner}`
  if (answer) {
    const size = compact ? 'bg-surface' : `bg-sunken ${bubbleSize(answer.text)}`
    const lines = compact ? 'line-clamp-2' : 'line-clamp-9 [@media(max-height:1059px)]:line-clamp-5'
    return (
      <p className={`${bubble} ${size}`} title={answer.text}>
        <span className={lines}>{answer.text}</span>
      </p>
    )
  }
  if (side === 'receiver' && file.denied) {
    return <p className={`${bubble} bg-held-soft text-held ${compact ? '' : 'text-2xl hall:text-4xl'}`}>{t('stage.denied')}</p>
  }
  const asked = stage.phones[side] === 'question'
  return (
    <p className={`flex items-center gap-3 text-muted ${compact ? 'py-2 text-base' : 'text-lg hall:text-2xl'}`}>
      {asked && <Waiting />}
      {t(asked || file.decided_at === null ? 'stage.answer_waiting' : 'stage.answer_none')}
    </p>
  )
}

/** What this phone shows at the end, in the words and colours of the phone itself. */
function Result({ status }: { status: PhoneStatus }) {
  const { t } = useI18n()
  if (status === 'question' || status === 'waiting') return null
  const offer = status === 'return_offer'
  const look = lookOf(offer ? 'with_specialist' : status)
  return (
    <p
      className={`flex animate-enter items-center gap-3 text-2xl leading-tight font-bold hall:gap-4 hall:text-4xl ${look.text}`}
      key={status}
    >
      <span className={`inline-flex size-12 shrink-0 animate-pop items-center justify-center rounded-full hall:size-16 ${look.solid}`}>
        {look.icon('size-7 hall:size-9')}
      </span>
      {t(offer ? 'phone.offer.title' : `status.${status}`)}
    </p>
  )
}

function Top({ side, stage }: { side: Side; stage: StageView }) {
  const { lang, t } = useI18n()
  const name = (side === 'receiver' ? stage.case.receiver : stage.case.sender)[lang]
  return (
    <div className="hero px-5 pt-5 pb-10">
      <div className="flex items-center gap-3">
        <Avatar name={name} tone={side === 'receiver' ? 'action' : 'hero'} />
        <p className="min-w-0 text-lg leading-tight hall:text-xl">
          <span className="block text-on-hero-muted">{t(`side.${side}`)}</span>
          <span className="block truncate font-bold">{name}</span>
        </p>
      </div>
      <p className="mt-3 text-center text-lg text-on-hero-muted">
        {t(side === 'receiver' ? 'phone.incoming' : 'phone.outgoing')}
      </p>
      <p className="text-center font-display text-4xl leading-tight font-bold tracking-tight hall:text-6xl">
        <Amount value={stage.case.amount} />
      </p>
    </div>
  )
}

/** One phone as the hall sees it: the person, the question, the answer, the result. */
export function StagePhone({ side, stage }: { side: Side; stage: StageView }) {
  const { t } = useI18n()
  return (
    <section
      aria-label={t(`phone.title.${side}`)}
      className="mx-auto flex h-full max-h-[860px] w-full max-w-[460px] flex-col overflow-hidden rounded-[44px] border-[10px] border-device bg-hero"
    >
      <Top side={side} stage={stage} />
      <div className="-mt-7 flex min-h-0 flex-1 flex-col rounded-t-sheet bg-surface px-5 pt-5 pb-5">
        <div className="flex min-h-32 flex-1 flex-col justify-center gap-4 overflow-hidden pb-3 hall:gap-6">
          <p className="text-xl leading-snug font-bold text-balance hall:text-3xl">{t(`phone.question.${side}`)}</p>
          <div aria-live="polite">
            <Spoken side={side} stage={stage} />
          </div>
        </div>
        <div className="min-h-12 hall:min-h-16">
          <Result status={stage.phones[side]} />
        </div>
      </div>
    </section>
  )
}
