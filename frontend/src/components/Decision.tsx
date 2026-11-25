import type { CaseFile, StageView } from '../api/types'
import { formatSeconds } from '../format'
import { useI18n, type Key } from '../i18n'
import { ReasonLine, Reasons } from './Reasons'
import { isFinal, lookOf } from './status'
import { Card } from './ui'

/** A short sentence for outcomes that have no reason code. */
function closingNote(file: CaseFile): Key | null {
  const last = file.trail.at(-1)?.event
  if (last === 'decided_release') return 'decision.release_note'
  if (last === 'staff_release' || last === 'staff_return') return 'decision.staff_note'
  return last === 'return_accepted' ? 'decision.accepted_note' : null
}

function Word({ file, large }: { file: CaseFile; large: boolean }) {
  const { t } = useI18n()
  const look = lookOf(file.state)
  if (!isFinal(file.state)) return <p className="text-2xl text-muted">{t('stage.not_yet')}</p>
  const sizes = large ? 'text-4xl xl:text-5xl' : 'text-3xl'
  return (
    <p
      className={`flex animate-enter items-center gap-3 font-display leading-tight font-bold tracking-tight ${sizes} ${look.text}`}
      key={file.state}
    >
      <span
        className={`inline-flex shrink-0 animate-pop items-center justify-center rounded-full ${look.solid} ${large ? 'size-14' : 'size-11'}`}
      >
        {look.icon(large ? 'size-9' : 'size-7')}
      </span>
      {t(`status.${file.state}`)}
    </p>
  )
}

function useSeconds(stage: StageView): string | null {
  const { lang } = useI18n()
  const seconds = stage.seconds ?? stage.running_seconds
  return seconds === null ? null : formatSeconds(seconds, lang)
}

export function Decision({ stage }: { stage: StageView }) {
  const { t } = useI18n()
  const note = closingNote(stage.case)
  const seconds = useSeconds(stage)
  return (
    <Card className="px-6 py-3">
      <h2 className="text-base text-muted">{t('decision.title')}</h2>
      <div aria-live="polite" className="mt-1 flex min-h-14 items-center">
        <Word file={stage.case} large />
      </div>
      {note && <p className="mt-2 text-lg hall:text-xl">{t(note)}</p>}
      {stage.case.reasons.length > 0 && <Reasons className="mt-3 text-lg hall:text-xl" codes={stage.case.reasons} />}
      {seconds !== null && (
        <p className="mt-3 flex animate-fade flex-wrap items-baseline gap-x-2 border-t border-line pt-2">
          <span className="font-display text-5xl leading-tight font-bold tracking-tight xl:text-6xl" data-numeric>
            {seconds}
          </span>
          <span className="text-2xl">{t('stage.seconds_unit')}</span>
          <span className="ml-1 text-base text-muted hall:text-lg">{t('stage.seconds')}</span>
        </p>
      )}
    </Card>
  )
}

/** The same in less height, for the middle of the demo page. */
export function CompactDecision({ stage }: { stage: StageView }) {
  const { t } = useI18n()
  const note = closingNote(stage.case)
  const seconds = useSeconds(stage)
  return (
    <Card className="px-4 py-2.5">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1">
        <div>
          <h2 className="text-sm leading-tight text-muted">{t('decision.title')}</h2>
          <div aria-live="polite" className="mt-0.5 flex min-h-11 items-center">
            <Word file={stage.case} large={false} />
          </div>
        </div>
        {seconds !== null && (
          <div className="animate-fade">
            <p className="font-display text-3xl leading-tight font-bold" data-numeric>
              {seconds} <span className="text-lg font-normal">{t('stage.seconds_unit')}</span>
            </p>
            <p className="max-w-44 text-sm leading-tight text-muted">{t('stage.seconds')}</p>
          </div>
        )}
      </div>
      {note && <p className="mt-1.5 leading-snug font-semibold">{t(note)}</p>}
      {stage.case.reasons.length > 0 && <ReasonLine codes={stage.case.reasons} />}
    </Card>
  )
}
