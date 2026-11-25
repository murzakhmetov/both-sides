import { useId, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { saysTooLittle } from '../answer'
import type { PhoneView, Side } from '../api/types'
import { AlertIcon, CalendarIcon, LawIcon, LockIcon, MessageIcon, ShieldIcon } from '../components/icons'
import { PhoneShell } from '../components/PhoneShell'
import { StatusChip, StatusPanel } from '../components/status'
import { Tracker } from '../components/Tracker'
import { Button, IconCircle, Waiting, errorText } from '../components/ui'
import { formatDeadline } from '../format'
import { useFocusHeading } from '../hooks/useFocusHeading'
import { usePhone, type Phone } from '../hooks/usePhone'
import { useRescueFocus } from '../hooks/useRescueFocus'
import { SETTLE_MS, useSettled } from '../hooks/useSettled'
import { useI18n, useTitle, type Key } from '../i18n'

const MAX_LENGTH = 300
/** The counter appears only when the limit comes close. */
const SHOW_COUNTER_FROM = 240

interface PartProps {
  readonly phone: Phone
  readonly view: PhoneView
}

/** Read aloud by a screen reader when the status changes. */
function spokenStatus(view: PhoneView): Key {
  if (view.status === 'question') return `phone.question.${view.side}`
  if (view.status === 'waiting') return view.answered ? 'phone.waiting.title' : 'phone.first.title'
  return view.status === 'return_offer' ? 'phone.offer.title' : `status.${view.status}`
}

/** What went wrong with the last tap, next to the button that was tapped. */
function ActionError({ phone }: { phone: Phone }) {
  const { t } = useI18n()
  return (
    <div aria-live="polite">
      {phone.error && (
        <p className="mt-2 flex items-start gap-2 text-left text-lg leading-snug font-bold">
          <AlertIcon className="mt-0.5 size-5 shrink-0" />
          {errorText(phone.error, t)}
        </p>
      )}
    </div>
  )
}

function HiddenMessage({ textKey }: { textKey: Key }) {
  const { t } = useI18n()
  return (
    <p className="flex items-center gap-3 rounded-tile bg-sunken px-3.5 py-2.5 text-lg leading-snug text-muted">
      <LockIcon className="size-6 shrink-0 text-accent" />
      {t(textKey)}
    </p>
  )
}

/** Rows of a grouped list: an icon and one fact. */
function FactList({ children }: { children: ReactNode }) {
  return <ul className="divide-y divide-line rounded-card bg-sunken px-4">{children}</ul>
}

function Fact({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <li className="flex items-center gap-3 py-3">
      <IconCircle className="size-11 bg-surface text-accent">{icon}</IconCircle>
      <span className="min-w-0">{children}</span>
    </li>
  )
}

function Denial({ phone }: { phone: Phone }) {
  const { t } = useI18n()
  const armed = phone.denial
  return (
    <div className="relative mt-2.5">
      {/* Above the button and over the other one: nothing moves under the finger. While it is
          shown it takes the taps, so that nobody presses the hidden button through it. */}
      <p
        aria-live="polite"
        className={`absolute inset-x-0 bottom-full mb-0.5 rounded-tile text-center text-lg leading-snug font-bold ${
          armed ? 'animate-enter bg-text px-4 py-2.5 text-surface' : 'pointer-events-none'
        }`}
        id="deny-hint"
      >
        {armed && t('phone.deny_confirm')}
      </p>
      <Button
        aria-describedby="deny-hint"
        className="w-full"
        onClick={() => void phone.act('deny')}
        variant={armed ? 'danger-solid' : 'danger'}
      >
        {armed && (
          <span
            aria-hidden="true"
            className="absolute inset-x-0 bottom-0 h-1.5 origin-left animate-drain bg-surface opacity-70 motion-reduce:hidden"
            key={armed.id}
            style={{ animationDuration: `${armed.seconds}s` }}
          />
        )}
        {t('phone.deny')}
      </Button>
    </div>
  )
}

function Question({ phone, view }: PartProps) {
  const { lang, t } = useI18n()
  const fieldId = useId()
  const receiver = view.side === 'receiver'
  const empty = phone.text.trim().length === 0
  const field = useRef<HTMLTextAreaElement>(null)
  /** The case for which the phone has already asked for the missing half of the answer. */
  const [askedFor, setAskedFor] = useState('')
  const askedAt = useRef(0)
  const tooLittle = saysTooLittle(phone.text)
  const asks = tooLittle && !empty && askedFor === view.case_id
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (empty) return
    if (tooLittle && askedFor !== view.case_id) {
      setAskedFor(view.case_id)
      askedAt.current = performance.now()
      field.current?.focus()
      return
    }
    // The second tap of a double tap has not read the question yet.
    if (asks && performance.now() - askedAt.current < SETTLE_MS) return
    void phone.act('answer', { text: phone.text })
  }
  return (
    <div className="animate-enter">
      {receiver && <HiddenMessage textKey="phone.message_hidden" />}
      <form className={receiver ? 'mt-3' : ''} onSubmit={submit}>
        <h1 className="text-xl font-bold tracking-tight">
          <label htmlFor={fieldId}>{t(`phone.question.${view.side}`)}</label>
        </h1>
        <p className="mt-1 text-lg leading-snug text-muted">
          {t('phone.why')} {!receiver && t('phone.advice.sender')}
        </p>
        <textarea
          aria-describedby={`${fieldId}-note`}
          autoComplete="off"
          className="mt-2.5 block max-h-60 min-h-28 w-full resize-none rounded-tile border-2 border-line-strong bg-surface px-4 py-3 text-lg [field-sizing:content] placeholder:text-muted focus:border-accent focus:outline-offset-0"
          id={fieldId}
          maxLength={MAX_LENGTH}
          onChange={(event) => phone.type(event.target.value)}
          placeholder={t('phone.placeholder')}
          ref={field}
          rows={3}
          value={phone.text}
        />
        <p className="mt-1.5 flex items-start justify-between gap-4 text-lg leading-snug text-muted" id={`${fieldId}-note`}>
          <span>{t('phone.not_shown')}</span>
          {phone.text.length >= SHOW_COUNTER_FROM && (
            <span className="whitespace-nowrap" data-numeric>
              {t('phone.counter', { n: phone.text.length, max: MAX_LENGTH })}
            </span>
          )}
        </p>
        <div aria-live="polite">
          {asks && (
            <p className="mt-2 flex items-start gap-2.5 rounded-tile bg-sunken px-4 py-3 text-lg leading-snug font-bold">
              <AlertIcon className="mt-0.5 size-5 shrink-0" />
              <span>{t('phone.too_little')}</span>
            </p>
          )}
        </div>
        <ActionError phone={phone} />
        <Button className="mt-2.5 w-full" inactive={empty || phone.running !== null} type="submit">
          {t(phone.running === 'answer' ? 'phone.sending' : asks ? 'phone.send_anyway' : 'phone.send')}
        </Button>
      </form>
      {receiver && <Denial phone={phone} />}
      {view.answer_by && (
        <p className="mt-2.5 text-center text-lg leading-snug text-muted">
          {t('phone.answer_by', { date: formatDeadline(view.answer_by, lang) })}
        </p>
      )}
    </div>
  )
}

function WaitingPanel({ view }: { view: PhoneView }) {
  const { t } = useI18n()
  return (
    <div className="animate-enter">
      {view.side === 'receiver' && <HiddenMessage textKey="phone.message_waiting" />}
      <div className="px-2 pt-4 text-center">
        <span className="inline-flex size-16 items-center justify-center rounded-full bg-sunken">
          <Waiting />
        </span>
        <h1 className="mt-3 text-2xl font-bold tracking-tight">
          {t(view.answered ? 'phone.waiting.title' : 'phone.first.title')}
        </h1>
        <p className="mt-1 text-lg text-balance text-muted">{t(view.answered ? 'phone.waiting.text' : 'phone.first.text')}</p>
      </div>
      <div className="mt-4">
        <Tracker view={view} />
      </div>
    </div>
  )
}

function Deadline({ view }: { view: PhoneView }) {
  const { lang, t } = useI18n()
  if (!view.deadline_at) return null
  return (
    <Fact icon={<CalendarIcon />}>
      <span className="font-semibold">{t('phone.decision_by', { date: formatDeadline(view.deadline_at, lang) })}</span>
    </Fact>
  )
}

/** Stays on the receiver's phone, also after the money went back. */
function GoodFaithNotice({ view }: { view: PhoneView }) {
  const { t } = useI18n()
  return (
    <section className="rounded-card bg-sunken p-4 text-left">
      <h2 className="flex items-center gap-2.5 text-xl font-bold">
        <ShieldIcon className="size-7 shrink-0 text-accent" />
        {t('phone.notice.title')}
      </h2>
      <p className="mt-2">
        <span className="text-muted">{t('phone.case_number')}: </span>
        <span className="font-bold whitespace-nowrap" data-numeric>
          {view.case_number}
        </span>
      </p>
      <p className="mt-2 leading-snug">{t('phone.notice.text')}</p>
      <p className="mt-2 leading-snug">{t('phone.notice.advice')}</p>
    </section>
  )
}

function Credited({ view }: { view: PhoneView }) {
  const { t } = useI18n()
  return (
    <StatusPanel state="credited">
      <p className="text-center text-balance text-muted">{t(`phone.credited.${view.side}`)}</p>
      {view.message && (
        <FactList>
          <Fact icon={<MessageIcon />}>
            <span className="block leading-snug text-muted">{t('phone.message_label')}</span>
            <span className="block leading-snug font-bold">{view.message}</span>
          </Fact>
        </FactList>
      )}
      {view.denied && <GoodFaithNotice view={view} />}
    </StatusPanel>
  )
}

function WithSpecialist({ view }: { view: PhoneView }) {
  const { t } = useI18n()
  return (
    <StatusPanel state="with_specialist">
      <p className="text-center text-balance text-muted">{t('phone.specialist.text')}</p>
      <Tracker view={view} />
    </StatusPanel>
  )
}

function Held({ phone, view }: PartProps) {
  const { t } = useI18n()
  const line = useRef<HTMLParagraphElement>(null)
  useRescueFocus(view.objection_sent, line)
  return (
    <StatusPanel state="held">
      <p className="text-center text-balance text-muted">{t('phone.held.text')}</p>
      <FactList>
        <Deadline view={view} />
        <Fact icon={<LawIcon />}>{t('phone.ground', { ground: view.ground })}</Fact>
      </FactList>
      <div className="text-center">
        <p aria-live="polite" className={view.objection_sent ? 'font-bold' : 'text-muted'} ref={line} tabIndex={-1}>
          {t(view.objection_sent ? 'phone.held.sent' : 'phone.held.hint')}
        </p>
        {!view.objection_sent && (
          <Button
            className="mt-3 w-full"
            inactive={phone.running !== null}
            onClick={() => void phone.act('objection')}
            variant="tonal"
          >
            {t('phone.held.object')}
          </Button>
        )}
        <ActionError phone={phone} />
      </div>
    </StatusPanel>
  )
}

function ReturnOffer({ phone, view }: PartProps) {
  const { t } = useI18n()
  const settled = useSettled()
  return (
    <div className="animate-enter space-y-3 text-lg">
      <div className="space-y-2 text-center">
        <StatusChip large state="with_specialist" />
        <h1 className="text-2xl font-bold tracking-tight">{t('phone.offer.title')}</h1>
        <p className="leading-snug text-balance text-muted">{t('phone.offer.text')}</p>
      </div>
      <Button
        className="w-full"
        inactive={phone.running !== null}
        onClick={() => settled() && void phone.act('accept-return')}
      >
        {t('phone.offer.accept')}
      </Button>
      <ActionError phone={phone} />
      <GoodFaithNotice view={view} />
      <p className="text-center leading-snug text-balance text-muted">{t('phone.offer.later')}</p>
    </div>
  )
}

function Returned({ view }: { view: PhoneView }) {
  const { t } = useI18n()
  return (
    <StatusPanel state="returned">
      <p className="text-center text-balance text-muted">{t(`phone.returned.${view.side}`)}</p>
      {view.denied && <GoodFaithNotice view={view} />}
    </StatusPanel>
  )
}

function PhoneBody({ phone, view }: PartProps): ReactNode {
  if (view.status === 'question') return <Question phone={phone} view={view} />
  if (view.status === 'waiting') return <WaitingPanel view={view} />
  const final = {
    credited: <Credited view={view} />,
    with_specialist: <WithSpecialist view={view} />,
    held: <Held phone={phone} view={view} />,
    returned: <Returned view={view} />,
    return_offer: <ReturnOffer phone={phone} view={view} />,
  }[view.status]
  return <div key={view.status}>{final}</div>
}

/** Names the screen: a new transfer or a new status is a new screen. */
function screenName(view: PhoneView | null): string {
  return view ? `${view.case_id} ${view.status}` : ''
}

export function PhonePage({ side }: { side: Side }) {
  const { t } = useI18n()
  const phone = usePhone(side)
  const view = phone.view
  const area = useFocusHeading(screenName(view))
  useTitle(t(`phone.title.${side}`))
  return (
    <PhoneShell area={area} problem={phone.problem} view={view}>
      {view ? (
        <PhoneBody phone={phone} view={view} />
      ) : (
        <p className="pt-6 text-center text-lg text-muted">{t('app.loading')}</p>
      )}
      <p className="sr-only" role="status">
        {view && t(spokenStatus(view))}
      </p>
    </PhoneShell>
  )
}
