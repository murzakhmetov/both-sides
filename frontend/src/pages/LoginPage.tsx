import { useEffect, useId, useState, type FormEvent } from 'react'
import { errorCode, post } from '../api/client'
import { LockIcon } from '../components/icons'
import { BetaNote, Button, Card, IconCircle, TopBar } from '../components/ui'
import { usePoll } from '../hooks/usePoll'
import { useI18n, useTitle, type Key } from '../i18n'
import { safeNext } from '../routes'

const MAX_LENGTH = 200
const POLL_MS = 3000

const MESSAGES: Readonly<Record<string, Key>> = {
  wrong_password: 'login.wrong',
  locked: 'login.locked',
  rate_limited: 'error.rate_limited',
  offline: 'login.offline',
}

function goOn(): void {
  window.location.assign(safeNext(window.location.search))
}

export function LoginPage() {
  const { t } = useI18n()
  const fieldId = useId()
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const session = usePoll<{ readonly staff: boolean }>('/api/session', POLL_MS)
  const signedIn = session.data?.staff === true
  useTitle(t('login.title'))

  // One login is enough for all tabs, for example after a restart of the server.
  useEffect(() => {
    if (signedIn) goOn()
  }, [signedIn])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (busy || password.length === 0) return
    setBusy(true)
    setError('')
    try {
      await post('/api/login', { password })
      goOn()
    } catch (failure) {
      setError(errorCode(failure))
      setPassword('')
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <TopBar />
      <main className="mx-auto w-full max-w-md flex-1 px-4 py-10">
        <Card className="p-6">
          <IconCircle className="hero size-14">
            <LockIcon className="size-7" />
          </IconCircle>
          <h1 className="mt-3 text-3xl font-bold tracking-tight">{t('login.title')}</h1>
          <p className="mt-2 text-muted">{t('login.text')}</p>
          <form className="mt-5" onSubmit={(event) => void submit(event)}>
            <label className="block font-bold" htmlFor={fieldId}>
              {t('login.password')}
            </label>
            <input
              autoComplete="current-password"
              autoFocus
              className="mt-2 block min-h-14 w-full rounded-tile border-2 border-line-strong bg-surface px-4 text-lg focus:border-accent focus:outline-offset-0"
              id={fieldId}
              maxLength={MAX_LENGTH}
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
            <p aria-live="assertive" className="mt-2 min-h-6 font-bold">
              {error && t(MESSAGES[error] ?? 'error.generic')}
            </p>
            <Button className="mt-2 w-full" inactive={busy || password.length === 0} type="submit">
              {t('login.submit')}
            </Button>
          </form>
        </Card>
        <BetaNote className="mt-4" />
      </main>
    </div>
  )
}
