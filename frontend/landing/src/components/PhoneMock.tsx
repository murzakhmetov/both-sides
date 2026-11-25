import type { ReactNode } from 'react'
import { RENT } from '../examples'
import { useLang } from '../lang'
import mark from '../mark.svg'

export type Side = keyof typeof RENT

/** What a phone shows at one step of the story. */
export type PhoneState = 'stopped' | 'question' | 'answered' | 'credited' | 'offer'

interface PhoneMockProps {
  readonly side: Side
  readonly state: PhoneState
  readonly on: boolean
}

function Bubble({ side }: { side: Side }) {
  const { t, lang } = useLang()
  const answer = RENT[side]
  return (
    <div className="rounded-2xl rounded-br-md bg-bcc-green/18 px-3.5 py-2.5 ring-1 ring-bcc-green/45">
      <p className="text-[0.94rem] leading-snug font-semibold" lang={answer.lang}>
        {answer.text}
      </p>
      {lang !== answer.lang && <p className="mt-1.5 text-[0.875rem] leading-snug text-muted">{t(answer.translation)}</p>}
    </div>
  )
}

function Question({ side }: { side: Side }) {
  const { app } = useLang()
  return (
    <>
      {side === 'receiver' && (
        <p className="phone-small text-[0.875rem] leading-snug text-muted">{app('phone.message_hidden')}</p>
      )}
      <p className="mt-2 text-[1rem] leading-snug font-semibold">{app(`phone.question.${side}`)}</p>
      <div className="mt-2.5">
        <Bubble side={side} />
      </div>
      <p className="phone-small mt-2 text-[0.875rem] leading-snug text-muted">{app('phone.not_shown')}</p>
    </>
  )
}

function Credited({ side }: { side: Side }) {
  const { app } = useLang()
  return (
    <>
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-bcc-green text-xl text-ink">✓</span>
      <p className="mt-3 text-[1.15rem] font-semibold text-bcc-green-light">{app('status.credited')}</p>
      <p className="mt-1 text-[0.9rem] leading-snug text-muted">{app(`phone.credited.${side}`)}</p>
    </>
  )
}

function Offer() {
  const { app } = useLang()
  return (
    <>
      <p className="rounded-xl border border-white/25 px-3 py-2.5 text-center text-[0.92rem] font-semibold">{app('phone.deny')}</p>
      <p className="mt-4 text-[1rem] leading-snug font-semibold">{app('phone.offer.title')}</p>
      <p className="mt-3 text-[0.9rem] leading-snug text-bcc-gold-light">{app('phone.notice.title')}</p>
    </>
  )
}

function Screen({ side, state }: { side: Side; state: PhoneState }): ReactNode {
  const { app } = useLang()
  if (state === 'question' || state === 'answered') return <Question side={side} />
  if (state === 'credited') return <Credited side={side} />
  if (state === 'offer') return <Offer />
  return <p className="text-[0.94rem] leading-snug text-muted">{app('phone.step.stopped')}</p>
}

/** A phone drawn in HTML: the question of the app, as the client sees it. */
export function PhoneMock({ side, state, on }: PhoneMockProps) {
  const { t, app } = useLang()
  const receiver = side === 'receiver'
  return (
    <div
      className="phone-mock w-full max-w-[21.5rem] rounded-[2.4rem] border border-white/20 bg-[#0e0e10]/95 p-2 shadow-2xl"
      data-fit
      data-on={on}
    >
      <div className="phone-screen flex flex-col rounded-[1.9rem] border border-white/8 bg-panel px-4 py-3.5">
        <div className="phone-head flex items-center justify-between gap-2 border-b border-white/10 pb-2.5">
          <span className="flex items-center gap-2 text-[0.875rem] font-semibold">
            <img alt="" className="h-4 w-4" height="16" src={mark} width="16" />
            {t('nav.name')}
          </span>
          <span className="text-[0.875rem] text-muted">{t(receiver ? 'how.recipient' : 'how.sender')}</span>
        </div>
        <p className="mt-3 text-[0.875rem] text-muted">{app(receiver ? 'phone.incoming' : 'phone.outgoing')}</p>
        <p className="phone-amount font-display text-[1.6rem] leading-tight font-semibold tracking-tight whitespace-nowrap">{t('how.amount')}</p>
        <p className="text-[0.9rem] text-muted">{t(receiver ? 'how.name.recipient' : 'how.name.sender')}</p>
        <div className="hairline my-3" />
        <Screen side={side} state={state} />
      </div>
    </div>
  )
}

/** The same phone in words, for people who do not see the drawing. */
export function usePhoneWords(): (side: Side, state: PhoneState) => string {
  const { t, app } = useLang()
  return (side, state) => {
    const words: Readonly<Record<PhoneState, readonly string[]>> = {
      stopped: [app('phone.step.stopped')],
      question: [app(`phone.question.${side}`), `«${RENT[side].text}»`, app('phone.not_shown')],
      answered: [app(`phone.question.${side}`), `«${RENT[side].text}»`, app('phone.not_shown')],
      credited: [app('status.credited'), app(`phone.credited.${side}`)],
      offer: [app('phone.deny'), app('phone.offer.title'), app('phone.notice.title')],
    }
    return `${t(side === 'receiver' ? 'how.recipient' : 'how.sender')}: ${words[state].join(' · ')}`
  }
}
