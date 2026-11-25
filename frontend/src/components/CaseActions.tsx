import { useEffect, useRef, useState } from 'react'
import { errorCode, post } from '../api/client'
import type { CaseFile } from '../api/types'
import { formatAmount } from '../format'
import { useRescueFocus } from '../hooks/useRescueFocus'
import { useI18n, type Key } from '../i18n'
import { Button, errorText } from './ui'

type Action = 'release' | 'return'

/** A double click or a held key must not reach the question that has just appeared. */
const TOO_EARLY_MS = 500

function stateText(file: CaseFile): Key | null {
  if (file.state === 'credited' || file.state === 'returned') return 'console.closed'
  return file.state === 'with_specialist' || file.state === 'held' ? null : 'console.running'
}

/** "Release" and "Return", each with one question before the money moves. */
export function CaseActions({ file, onApply }: { file: CaseFile; onApply: (request: () => Promise<CaseFile>) => Promise<void> }) {
  const { t } = useI18n()
  const [asked, setAsked] = useState<Action | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const shownAt = useRef(Number.NEGATIVE_INFINITY)
  const acted = useRef(false)
  const buttons = useRef<HTMLDivElement>(null)
  const line = useRef<HTMLParagraphElement>(null)
  const closedText = stateText(file)
  const open = closedText === null
  useRescueFocus(!open, line)

  // The focus follows what this person did, not what others do with the case.
  useEffect(() => {
    if (!acted.current) return
    acted.current = false
    const target = open ? buttons.current?.querySelector('button') : line.current
    target?.focus()
  }, [asked, open])

  const ask = (action: Action | null) => {
    if (performance.now() - shownAt.current < TOO_EARLY_MS) return
    shownAt.current = performance.now()
    acted.current = true
    setError('')
    setAsked(action)
  }

  const close = async (action: Action) => {
    if (busy || performance.now() - shownAt.current < TOO_EARLY_MS) return
    setBusy(true)
    setError('')
    try {
      await onApply(() => post<CaseFile>(`/api/cases/${file.id}/${action}`))
    } catch (failure) {
      setError(errorCode(failure))
    } finally {
      acted.current = true
      setBusy(false)
      setAsked(null)
    }
  }

  const amount = formatAmount(file.amount)
  return (
    <div>
      {open && (
        <div className="flex flex-wrap gap-2" ref={buttons}>
          {asked === null ? (
            <>
              <Button onClick={() => ask('release')} size="desk">
                {t('console.release')}
              </Button>
              <Button onClick={() => ask('return')} size="desk" variant="outline">
                {t('console.return')}
              </Button>
            </>
          ) : (
            <>
              <Button inactive={busy} key="cancel" onClick={() => ask(null)} size="desk" variant="quiet">
                {t('console.cancel')}
              </Button>
              <Button
                inactive={busy}
                key="confirm"
                onClick={() => void close(asked)}
                size="desk"
                variant={asked === 'release' ? 'primary' : 'outline'}
              >
                {t(asked === 'release' ? 'console.confirm_release' : 'console.confirm_return', { amount })}
              </Button>
            </>
          )}
        </div>
      )}
      <p className={closedText ? 'text-muted' : error ? 'mt-2 font-bold' : ''} ref={line} role="status" tabIndex={-1}>
        {closedText ? t(closedText) : error && errorText(error, t)}
      </p>
    </div>
  )
}
