import type { CaseFile } from '../api/types'
import { useI18n, type Key } from '../i18n'
import { AlertIcon, CheckIcon } from './icons'

interface Row {
  readonly key: Key
  readonly value: number
  readonly risky: boolean
}

function rowsOf(file: CaseFile): readonly Row[] {
  const { facts } = file
  return [
    { key: 'fact.account_age', value: facts.account_age_days, risky: facts.risky.includes('new_account') },
    {
      key: 'fact.first_time',
      value: facts.first_time_senders_today,
      risky: facts.risky.includes('many_first_time_senders'),
    },
    { key: 'fact.earlier', value: facts.earlier_transfers, risky: facts.risky.includes('no_earlier_transfers') },
    {
      key: 'fact.similar',
      value: file.similar_receivers,
      risky: file.similar_receivers >= file.thresholds.repeated_story,
    },
  ]
}

function RiskMark({ risky, className }: { risky: boolean; className: string }) {
  const { t } = useI18n()
  // Neutral on purpose: green and amber belong to the statuses.
  const tone = risky ? 'bg-text text-surface' : 'bg-line text-text'
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-bold ${tone} ${className}`}
      data-print-color
    >
      {risky ? <AlertIcon className="size-[1.1em]" /> : <CheckIcon className="size-[1.1em]" />}
      {t(risky ? 'fact.risky' : 'fact.calm')}
    </span>
  )
}

function FactRow({ row, large }: { row: Row; large: boolean }) {
  const { t } = useI18n()
  return (
    <div
      className={`flex items-center justify-between gap-3 py-2 leading-snug ${large ? 'text-base hall:text-xl' : 'text-base'}`}
    >
      <dt className="text-muted">{t(row.key)}</dt>
      <dd className="flex shrink-0 items-center gap-3 whitespace-nowrap">
        <span className={`font-bold ${large ? 'text-xl hall:text-2xl' : 'text-lg'}`} data-numeric>
          {row.value}
        </span>
        <RiskMark className={large ? 'px-2.5 py-0.5 text-sm hall:text-lg' : 'px-2.5 py-0.5 text-sm'} risky={row.risky} />
      </dd>
    </div>
  )
}

function FactTile({ row }: { row: Row }) {
  const { t } = useI18n()
  return (
    <div className="flex flex-col justify-between gap-1 rounded-tile bg-sunken px-3 py-2">
      <dt className="text-sm leading-tight text-muted">{t(row.key)}</dt>
      <dd className="flex flex-wrap items-center justify-between gap-x-1">
        <span className="text-xl leading-tight font-bold" data-numeric>
          {row.value}
        </span>
        <RiskMark className="px-1.5 py-0.5 text-xs" risky={row.risky} />
      </dd>
    </div>
  )
}

function Title({ file, className }: { file: CaseFile; className: string }) {
  const { t } = useI18n()
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4">
      <h2 className={`font-bold ${className}`}>{t('facts.title')}</h2>
      <p className="text-sm text-muted" data-numeric>
        {t('fact.risky_count', { n: file.facts.risky.length })}
      </p>
    </div>
  )
}

/** Side by side, for the middle of the demo page and for low screens. */
export function FactTiles({ file }: { file: CaseFile }) {
  return (
    <div className="@container">
      <Title className="text-base" file={file} />
      <dl className="mt-1.5 grid grid-cols-2 gap-2 @lg:grid-cols-4">
        {rowsOf(file).map((row) => (
          <FactTile key={row.key} row={row} />
        ))}
      </dl>
    </div>
  )
}

export function Facts({ file, large = false }: { file: CaseFile; large?: boolean }) {
  return (
    <div>
      <Title className={large ? 'text-xl' : 'text-lg'} file={file} />
      <dl className="mt-1 divide-y divide-line">
        {rowsOf(file).map((row) => (
          <FactRow key={row.key} large={large} row={row} />
        ))}
      </dl>
    </div>
  )
}
