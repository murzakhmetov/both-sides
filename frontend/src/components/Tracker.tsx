import type { PhoneView } from '../api/types'
import { formatDeadline } from '../format'
import { useI18n } from '../i18n'
import { CheckIcon, ClockIcon } from './icons'

type State = 'done' | 'now' | 'later'

const CIRCLE: Readonly<Record<State, string>> = {
  done: 'bg-accent text-surface',
  now: 'bg-surface text-accent ring-2 ring-accent ring-inset',
  later: 'bg-surface ring-2 ring-line-strong ring-inset',
}

const TEXT: Readonly<Record<State, string>> = { done: '', now: 'font-bold', later: 'text-muted' }

export function statesOf(view: Pick<PhoneView, 'answered' | 'status'>): readonly State[] {
  const answer: State = view.answered ? 'done' : view.status === 'waiting' ? 'now' : 'later'
  return ['done', answer, answer === 'now' ? 'later' : 'now']
}

/** Where the transfer stands: what is done and what comes next. Says nothing about the other person. */
export function Tracker({ view }: { view: PhoneView }) {
  const { lang, t } = useI18n()
  const decision = view.deadline_at
    ? t('phone.decision_by', { date: formatDeadline(view.deadline_at, lang) })
    : t('phone.step.decision')
  const texts = [t('phone.step.stopped'), t('phone.step.answer'), decision]
  const states = statesOf(view)
  return (
    <ol className="relative rounded-card bg-sunken px-4 py-2 text-left text-lg leading-snug before:absolute before:top-8 before:bottom-8 before:left-8 before:w-0.5 before:bg-line-strong">
      {texts.map((text, index) => {
        const state = states[index] ?? 'later'
        return (
          <li
            aria-current={state === 'now' ? 'step' : undefined}
            className={`relative flex items-center gap-3.5 py-1.5 ${TEXT[state]}`}
            key={index}
          >
            <span className={`inline-flex size-9 shrink-0 items-center justify-center rounded-full ${CIRCLE[state]}`}>
              {state === 'done' && <CheckIcon />}
              {state === 'now' && <ClockIcon />}
            </span>
            <span>
              {text}
              {state === 'done' && <span className="sr-only">, {t('phone.step.done')}</span>}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
