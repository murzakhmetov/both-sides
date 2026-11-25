import type { ReactNode } from 'react'
import type { CaseState, FinalStatus } from '../api/types'
import { useI18n } from '../i18n'
import { CheckIcon, ClockIcon, PauseIcon, PersonIcon, ReturnIcon } from './icons'

/** One place for the colour, the icon and the word of every status. */
interface Look {
  readonly chip: string
  readonly solid: string
  readonly text: string
  readonly icon: (className: string) => ReactNode
}

const FINAL: Readonly<Record<FinalStatus, Look>> = {
  credited: {
    chip: 'bg-credited-soft text-credited',
    solid: 'bg-credited text-surface',
    text: 'text-credited',
    icon: (className) => <CheckIcon className={className} />,
  },
  with_specialist: {
    chip: 'bg-specialist-soft text-specialist',
    solid: 'bg-specialist-fill text-on-specialist',
    text: 'text-specialist',
    icon: (className) => <PersonIcon className={className} />,
  },
  held: {
    chip: 'bg-held-soft text-held',
    solid: 'bg-held text-surface',
    text: 'text-held',
    icon: (className) => <PauseIcon className={className} />,
  },
  returned: {
    chip: 'bg-returned-soft text-returned',
    solid: 'bg-returned text-surface',
    text: 'text-returned',
    icon: (className) => <ReturnIcon className={className} />,
  },
}

const OPEN: Look = {
  chip: 'bg-sunken text-muted',
  solid: 'bg-sunken text-muted',
  text: 'text-muted',
  icon: (className) => <ClockIcon className={className} />,
}

export function isFinal(state: CaseState): state is FinalStatus {
  return state in FINAL
}

export function lookOf(state: CaseState): Look {
  return isFinal(state) ? FINAL[state] : OPEN
}

export function StatusChip({ state, large = false }: { state: CaseState; large?: boolean }) {
  const { t } = useI18n()
  const look = lookOf(state)
  return (
    <span
      className={`inline-flex animate-enter items-center gap-1.5 rounded-full font-bold ${look.chip} ${
        large ? 'px-4 py-1.5 text-lg leading-snug' : 'px-3 py-1 text-sm'
      }`}
      data-print-color
      key={state}
    >
      {look.icon(large ? 'size-5' : 'size-4')}
      {t(`status.${state}`)}
    </span>
  )
}

/** The large status on a phone: icon, word, explanation. */
export function StatusPanel({ state, children }: { state: FinalStatus; children: ReactNode }) {
  const { t } = useI18n()
  const look = FINAL[state]
  return (
    <div>
      <div className="pt-2 text-center">
        <span className={`inline-flex size-18 animate-pop items-center justify-center rounded-full ${look.solid}`}>
          {look.icon('size-10')}
        </span>
        <h1 className={`mt-3 animate-enter text-3xl font-bold tracking-tight ${look.text}`}>{t(`status.${state}`)}</h1>
      </div>
      <div className="mt-2 animate-enter space-y-3.5 text-lg">{children}</div>
    </div>
  )
}
