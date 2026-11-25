import type { ReactNode } from 'react'
import type { AnswerView, CaseFile as File, Side, TrailEntry } from '../api/types'
import { formatAmount, formatDeadline, formatExactPercent, formatMoment } from '../format'
import { hasKey, useI18n, type Key } from '../i18n'
import { CaseActions } from './CaseActions'
import { Facts } from './Facts'
import { CalendarIcon, ClockIcon } from './icons'
import { MatchBar, sourceText } from './MatchBar'
import { Amount, Avatar } from './people'
import { Reasons } from './Reasons'
import { StatusChip } from './status'
import { Button, Card } from './ui'

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="p-5 print:break-inside-avoid print:border print:border-line">
      <h2 className="mb-2 text-lg font-bold">{title}</h2>
      {children}
    </Card>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-x-6 py-2 sm:grid-cols-[180px_1fr]">
      <dt className="text-muted">{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

function Answer({ side, answer, name }: { side: Side; answer: AnswerView | null; name: string }) {
  const { lang, t } = useI18n()
  return (
    <div className="min-w-0">
      <p className="flex items-center gap-2.5 text-muted">
        <Avatar name={name} size="small" tone={side === 'receiver' ? 'action' : 'tile'} />
        <span>
          {t(`side.${side}`)} · <span className="font-semibold text-text">{name}</span>
        </span>
      </p>
      {answer ? (
        <>
          <p className="mt-2 rounded-3xl rounded-tl-md bg-sunken px-4 py-3 text-lg leading-snug font-bold">{answer.text}</p>
          <p className="mt-1 px-1 text-sm text-muted" data-numeric>
            {formatMoment(answer.at, lang)}
          </p>
        </>
      ) : (
        <p className="mt-2 rounded-3xl rounded-tl-md border border-line px-4 py-3 text-lg text-muted">{t('file.no_answer')}</p>
      )}
    </div>
  )
}

function Details({ entry, file }: { entry: TrailEntry; file: File }) {
  const { lang, t } = useI18n()
  if (entry.details.length === 0) return null
  const words = entry.details.map((code) => {
    const key = `reason.${code}`
    return hasKey(key) ? t(key) : code
  })
  const compared = file.match
    ? `${sourceText(file.match, t)}, ${t('match.probability', { p: formatExactPercent(file.match.probability, lang) })}`
    : t('reason.matcher_unavailable')
  return <span className="text-muted"> ({entry.event === 'compared' ? compared : words.join('; ')})</span>
}

function Trail({ file }: { file: File }) {
  const { lang, t } = useI18n()
  return (
    <ol>
      {file.trail.map((entry, index) => {
        const key = `event.${entry.event}`
        return (
          <li
            className="grid gap-x-4 border-l-2 border-line py-1.5 pl-4 sm:grid-cols-[180px_110px_1fr]"
            key={`${entry.at}-${entry.event}-${index}`}
          >
            <span className="text-muted" data-numeric>
              {formatMoment(entry.at, lang)}
            </span>
            <span className="text-muted">{t(`actor.${entry.actor}`)}</span>
            <span>
              <span className="font-semibold">{hasKey(key) ? t(key) : entry.event}</span>
              <Details entry={entry} file={file} />
            </span>
          </li>
        )
      })}
    </ol>
  )
}

function Law() {
  const { t } = useI18n()
  const quotes: readonly Key[] = ['law.payments.suspend', 'law.payments.ask', 'law.payments.block']
  return (
    <div className="space-y-4">
      <div>
        <p className="font-bold">{t('law.payments.title')}</p>
        <ul className="mt-1 space-y-1.5">
          {quotes.map((key) => (
            <li key={key}>{t(key)}</li>
          ))}
        </ul>
      </div>
      <div>
        <p className="font-bold">{t('law.centre.title')}</p>
        <p className="mt-1">{t('law.centre.grounds')}</p>
      </div>
      <p className="text-muted">
        {t('file.law.source')} {t('file.scope')}
      </p>
    </div>
  )
}

function Header({ file }: { file: File }) {
  const { lang, t } = useI18n()
  return (
    <header className="hero rounded-card p-5 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-bold" data-numeric>
          {t('file.title', { id: file.id })}
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          <StatusChip state={file.state} />
          {file.overdue && (
            <span
              className="inline-flex items-center gap-1.5 rounded-full bg-text px-3 py-1 text-sm font-bold text-surface"
              data-print-color
            >
              <ClockIcon className="size-4" /> {t('console.overdue')}
            </span>
          )}
        </div>
      </div>
      <p className="mt-2 font-display text-5xl leading-tight font-bold tracking-tight">
        <Amount value={file.amount} />
      </p>
      <p className="mt-1 flex flex-wrap items-center justify-between gap-x-6 gap-y-1 text-lg">
        <span className="font-semibold">
          {file.sender[lang]} → {file.receiver[lang]}
        </span>
        <span className="inline-flex items-center gap-2 text-on-hero-muted" data-numeric>
          <CalendarIcon /> {t('console.deadline', { date: formatDeadline(file.deadline_at, lang) })}
        </span>
      </p>
    </header>
  )
}

function TransferSection({ file }: { file: File }) {
  const { lang, t } = useI18n()
  return (
    <Section title={t('file.transfer')}>
      <dl className="divide-y divide-line">
        <Row label={t('file.amount')}>
          <span className="font-bold" data-numeric>
            {formatAmount(file.amount)}
          </span>
        </Row>
        <Row label={t('side.sender')}>{file.sender[lang]}</Row>
        <Row label={t('side.receiver')}>{file.receiver[lang]}</Row>
        <Row label={t('file.message')}>{file.transfer.message || <span className="text-muted">{t('file.no_message')}</span>}</Row>
        <Row label={t('file.stopped')}>
          <span data-numeric>{formatMoment(file.stopped_at, lang)}</span>
        </Row>
        <Row label={t('file.deadline')}>
          <span className="font-bold" data-numeric>
            {formatDeadline(file.deadline_at, lang)}
          </span>
          <span className="text-muted"> · {t('file.deadline_note')}</span>
        </Row>
      </dl>
    </Section>
  )
}

function ComparisonSection({ file }: { file: File }) {
  const { t } = useI18n()
  return (
    <Section title={t('file.comparison')}>
      <MatchBar file={file} />
      {file.match?.note && (
        <p className="mt-2 text-sm">
          <span className="text-muted">{t('match.note')}: </span>
          <span lang="en">{file.match.note}</span>
        </p>
      )}
      <div className="mt-5">
        <Facts file={file} />
      </div>
    </Section>
  )
}

interface CaseFileProps {
  readonly file: File
  /** Sends a decision; its reply is the changed file. */
  readonly onApply: (request: () => Promise<File>) => Promise<void>
}

export function CaseFile({ file, onApply }: CaseFileProps) {
  const { lang, t } = useI18n()
  return (
    <article className="mx-auto max-w-4xl animate-fade space-y-3 px-4 py-4 sm:px-6 sm:py-5">
      <Header file={file} />
      <div className="flex flex-wrap items-start justify-between gap-2 py-1" data-no-print>
        <CaseActions file={file} onApply={onApply} />
        <Button onClick={() => window.print()} size="desk" variant="outline">
          {t('console.print')}
        </Button>
      </div>
      <Section title={t('file.answers')}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Answer answer={file.receiver_answer} name={file.receiver[lang]} side="receiver" />
          <Answer answer={file.sender_answer} name={file.sender[lang]} side="sender" />
        </div>
      </Section>
      <ComparisonSection file={file} />
      <TransferSection file={file} />
      <Section title={t('file.reasons')}>
        {file.reasons.length > 0 ? <Reasons codes={file.reasons} withCodes /> : <p className="text-muted">{t('file.no_reasons')}</p>}
      </Section>
      <Section title={t('file.objections')}>
        {file.objections.length === 0 && <p className="text-muted">{t('file.no_objections')}</p>}
        {file.objections.map((objection) => (
          <p key={objection.side}>
            {t(`side.${objection.side}`)}, <span data-numeric>{formatMoment(objection.at, lang)}</span>
          </p>
        ))}
      </Section>
      <Section title={t('file.trail')}>
        <Trail file={file} />
      </Section>
      <Section title={t('file.law')}>
        <Law />
      </Section>
    </article>
  )
}
