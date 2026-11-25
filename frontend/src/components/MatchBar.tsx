import type { CaseFile, MatchView } from '../api/types'
import { formatPercent } from '../format'
import { useI18n, type Translate } from '../i18n'
import { barColor, verdictKey, verdictOf } from '../verdict'
import { Waiting } from './ui'

/** The model name of the example cases in bothsides/demo/seed.py. */
const SEEDED_MODEL = 'seeded example'

export function sourceText(match: MatchView, t: Translate): string {
  if (match.model === SEEDED_MODEL) return t('match.source.seeded')
  if (match.source === 'gemini') return t('match.source.gemini', { model: match.model })
  if (match.fallback_code) return t('match.source.fallback', { code: match.fallback_code })
  return t('match.source.offline')
}

function Tri({ label, value }: { label: string; value: MatchView['same_reason'] }) {
  const { t } = useI18n()
  return (
    <span className="whitespace-nowrap">
      <span className="text-muted">{label}: </span>
      <span className="font-bold">{t(`match.tri.${value}`)}</span>
    </span>
  )
}

function Bar({ file, large }: { file: CaseFile; large: boolean }) {
  const { t } = useI18n()
  const verdict = verdictOf(file)
  // Rounded down like the number: a score just under the threshold ends just before its mark.
  const width = file.match ? Math.max(Math.floor(file.match.probability * 100 + 1e-9), 2) : 0
  return (
    <div
      aria-label={t('stage.match')}
      aria-valuemax={100}
      aria-valuemin={0}
      aria-valuenow={width}
      aria-valuetext={t(verdictKey(verdict))}
      className={`relative w-full overflow-hidden rounded-full bg-line ${large ? 'mt-3 h-7' : 'mt-2 h-4'}`}
      data-print-color
      role="meter"
    >
      <div
        className={`h-full rounded-full transition-[width] duration-250 ease-out ${barColor(file, verdict)}`}
        style={{ width: `${width}%` }}
      />
      <span
        aria-hidden="true"
        className="absolute inset-y-0 w-1 -translate-x-1/2 bg-text outline-2 outline-surface"
        style={{ left: `${file.thresholds.release * 100}%` }}
      />
    </div>
  )
}

function Numbers({ file, large }: { file: CaseFile; large: boolean }) {
  const { t } = useI18n()
  const { match } = file
  const threshold = <span>{t('match.threshold', { p: formatPercent(file.thresholds.release) })}</span>
  const size = large ? 'text-base hall:text-lg' : 'text-sm'
  if (!match) return <p className={`mt-2 text-muted ${size}`}>{threshold}</p>
  return (
    <div className={`mt-2 space-y-0.5 ${size}`}>
      <p className="flex flex-wrap gap-x-4">
        <span className="flex flex-wrap gap-x-4 text-muted" data-numeric>
          <span>{t('match.probability', { p: formatPercent(match.probability) })}</span>
          {threshold}
        </span>
        <Tri label={t('match.relation')} value={match.same_relation} />
        <Tri label={t('match.reason')} value={match.same_reason} />
      </p>
      <p className="text-muted">{sourceText(match, t)}</p>
    </div>
  )
}

export function MatchBar({ file, large = false }: { file: CaseFile; large?: boolean }) {
  const { t } = useI18n()
  const verdict = verdictOf(file)
  return (
    <div>
      <p
        className={`font-display leading-tight font-bold tracking-tight ${large ? 'text-3xl xl:text-5xl' : 'text-2xl'}`}
        key={verdict}
      >
        <span className="inline-block animate-enter">{t(verdictKey(verdict))}</span>
        {verdict === 'comparing' && <Waiting className="ml-3" />}
      </p>
      <Bar file={file} large={large} />
      <Numbers file={file} large={large} />
    </div>
  )
}
