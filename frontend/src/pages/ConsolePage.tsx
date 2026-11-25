import { useEffect, useRef, useState } from 'react'
import { errorCode, post } from '../api/client'
import type { CaseFile as File, CaseList, CaseSummary } from '../api/types'
import { CaseFile } from '../components/CaseFile'
import { AvatarPair } from '../components/people'
import { StatusChip } from '../components/status'
import { BetaNote, Button, Problem, TOP_LINK, TopBar } from '../components/ui'
import { formatAmount, formatDeadline } from '../format'
import { useNotice } from '../hooks/useNotice'
import { usePoll } from '../hooks/usePoll'
import { useStaffOnly } from '../hooks/useStaffOnly'
import { useI18n, useTitle } from '../i18n'
import { caseIdOf } from '../routes'

const POLL_MS = 1500

// The status colours stay with the statuses, so "overdue" and "objection" are dark.
function Tag({ text, tone }: { text: string; tone: 'dark' | 'held' | 'plain' }) {
  const tones = {
    dark: 'bg-text text-surface',
    held: 'bg-held-soft text-held',
    plain: 'bg-line text-text',
  }
  return <span className={`rounded-full px-2.5 py-1 text-sm leading-5 font-bold ${tones[tone]}`}>{text}</span>
}

interface RowProps {
  readonly item: CaseSummary
  readonly active: boolean
  readonly selected: boolean
  readonly onSelect: () => void
}

/** One line of the feed: two people, the amount, what happened. */
function CaseRow({ item, active, selected, onSelect }: RowProps) {
  const { lang, t } = useI18n()
  return (
    <li>
      <button
        aria-current={selected ? 'true' : undefined}
        className={`flex w-full gap-3 rounded-tile px-3 py-3 text-left transition-colors duration-150 ${
          selected ? 'bg-sunken ring-2 ring-accent ring-inset' : 'hover:bg-sunken'
        }`}
        onClick={onSelect}
        type="button"
      >
        <AvatarPair receiver={item.receiver[lang]} sender={item.sender[lang]} />
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-3">
            <span className="font-bold">
              {item.sender[lang]} → {item.receiver[lang]}
            </span>
            <span className="font-bold whitespace-nowrap" data-numeric>
              {formatAmount(item.amount)}
            </span>
          </span>
          <span className="flex flex-wrap items-baseline justify-between gap-x-3 text-sm text-muted" data-numeric>
            <span>{item.id}</span>
            <span>{t('console.deadline', { date: formatDeadline(item.deadline_at, lang) })}</span>
          </span>
          <span className="mt-2 flex flex-wrap items-center gap-1.5">
            <StatusChip state={item.state} />
            {item.overdue && <Tag text={t('console.overdue')} tone="dark" />}
            {item.denied && <Tag text={t('console.denied')} tone="held" />}
            {item.objections.length > 0 && <Tag text={t('console.objection')} tone="dark" />}
            {active && <Tag text={t('console.active')} tone="plain" />}
          </span>
          <span className="mt-1.5 block text-sm text-muted" data-numeric>
            {t('fact.risky_count', { n: item.risky.length })}
          </span>
          {item.risky.length > 0 && <span className="block font-mono text-xs text-muted">{item.risky.join(', ')}</span>}
          {item.reasons.length > 0 && (
            <span className="block font-mono text-xs text-muted">{item.reasons.join(', ')}</span>
          )}
        </span>
      </button>
    </li>
  )
}

function useSelectedCase(list: CaseList | null) {
  const [selected, setSelected] = useState<string | null>(() => caseIdOf(window.location.pathname))
  // A narrow screen shows the list or the file, never both.
  const [opened, setOpened] = useState(selected !== null)
  const exists = list?.cases.some((item) => item.id === selected) ?? true

  useEffect(() => {
    if (list && (!selected || !exists)) setSelected(list.active_id)
  }, [exists, list, selected])

  const select = (id: string) => {
    window.history.replaceState(null, '', `/console/${id}`)
    setSelected(id)
    setOpened(true)
  }
  const back = () => {
    window.history.replaceState(null, '', '/console')
    setOpened(false)
  }
  return { selected: exists ? selected : null, opened, select, back }
}

/** On a narrow screen the focus goes along when the list and the file change places. */
function useSwapFocus(opened: boolean) {
  const list = useRef<HTMLElement>(null)
  const file = useRef<HTMLElement>(null)
  const before = useRef(opened)

  useEffect(() => {
    if (before.current === opened) return
    before.current = opened
    if (opened && list.current?.offsetParent === null) file.current?.focus()
    if (!opened) list.current?.querySelector<HTMLElement>('[aria-current="true"]')?.focus()
  }, [opened])

  return { list, file }
}

export function ConsolePage() {
  const { t } = useI18n()
  useTitle(t('console.title'))
  const list = usePoll<CaseList>('/api/cases', POLL_MS)
  const { selected, opened, select, back } = useSelectedCase(list.data)
  const areas = useSwapFocus(opened)
  const file = usePoll<File>(selected ? `/api/cases/${selected}` : null, POLL_MS)
  const [notice, setNotice] = useNotice()
  useStaffOnly(list.errorCode)
  const shown = file.data && file.data.id === selected ? file.data : null

  // After a reset the open case is gone. The list shows what there is, so this is no error.
  const gone = file.errorCode === 'not_found'
  const refreshList = list.refresh
  useEffect(() => {
    if (gone) refreshList()
  }, [gone, refreshList])

  const open = useRef(selected)
  useEffect(() => {
    open.current = selected
  }, [selected])

  const apply = async (request: () => Promise<File>) => {
    const decided = selected
    try {
      await file.apply(request)
    } catch (failure) {
      // The case itself shows its errors, but this person has opened another one.
      if (open.current !== decided) setNotice(errorCode(failure))
      throw failure
    } finally {
      list.refresh()
    }
  }
  const signOut = async () => {
    try {
      await post('/api/logout')
      window.location.assign('/start')
    } catch (failure) {
      setNotice(errorCode(failure))
    }
  }
  return (
    <div className="flex min-h-dvh flex-col lg:h-dvh print:h-auto">
      <TopBar>
        <a className={TOP_LINK} href="/demo">
          {t('demo.title')}
        </a>
        <Button onClick={() => void signOut()} size="desk" variant="quiet">
          {t('app.logout')}
        </Button>
      </TopBar>
      <Problem code={notice || list.errorCode || (gone ? '' : file.errorCode)} />
      <div className="grid min-h-0 flex-1 lg:grid-cols-[430px_1fr] print:block">
        <nav
          aria-label={t('console.cases')}
          className={`bg-surface lg:block lg:overflow-y-auto dark:border-r dark:border-line ${opened ? 'hidden' : ''}`}
          data-no-print
          ref={areas.list}
        >
          <h1 className="px-5 pt-4 pb-2 text-2xl font-bold tracking-tight">{t('console.title')}</h1>
          <ul className="space-y-1 px-2 pb-3">
            {list.data?.cases.map((item) => (
              <CaseRow
                active={item.id === list.data?.active_id}
                item={item}
                key={item.id}
                onSelect={() => select(item.id)}
                selected={item.id === selected}
              />
            ))}
          </ul>
          <BetaNote className="px-5 pb-4" />
        </nav>
        <main
          className={`min-w-0 lg:block lg:overflow-y-auto print:block print:overflow-visible ${opened ? '' : 'hidden'}`}
          ref={areas.file}
          tabIndex={-1}
        >
          <div className="px-4 pt-4 sm:px-6 lg:hidden" data-no-print>
            <Button onClick={back} size="desk" variant="outline">
              {t('console.back')}
            </Button>
          </div>
          {shown ? (
            <CaseFile file={shown} key={shown.id} onApply={apply} />
          ) : (
            <p className="p-6 text-lg text-muted">{t(selected ? 'app.loading' : 'console.choose')}</p>
          )}
        </main>
      </div>
    </div>
  )
}
