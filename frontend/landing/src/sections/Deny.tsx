import { useEffect, useRef, useState } from 'react'
import { CASE_NUMBERS } from '../examples'
import { useInView } from '../hooks/useInView'
import { useReveal } from '../hooks/useReveal'
import { useLang } from '../lang'
import { useScene } from '../scene'

/** Two taps, as in the app. The app waits four seconds for the second one; here nobody is in a hurry, so the words differ. */
type Phase = 'ready' | 'armed' | 'done'

const NEXT: Readonly<Record<Phase, Phase>> = { ready: 'armed', armed: 'done', done: 'ready' }

function GoodFaithNotice({ shown }: { shown: boolean }) {
  const { t, app } = useLang()
  return (
    <div className="fade panel max-w-[30rem] p-6" data-on={shown}>
      <p className="caption">{t('example.invented')}</p>
      <p className="display-md mt-1 font-display font-medium">{app('phone.offer.title')}</p>
      <p className="mt-3 text-text/90">{app('phone.offer.text')}</p>
      <div className="hairline my-5" />
      <p className="font-semibold text-bcc-gold-light">{app('phone.notice.title')}</p>
      <p className="mt-2 text-text/90">{app('phone.notice.text')}</p>
      <p className="caption mt-4">
        {app('phone.case_number')}: {CASE_NUMBERS.stranger}
      </p>
    </div>
  )
}

/** "I do not know this person": two taps, the money turns back (clip H), the notice unfolds. */
export function Deny() {
  const { t, app } = useLang()
  const root = useRef<HTMLElement>(null)
  const inView = useInView(root)
  const [phase, setPhase] = useState<Phase>('ready')
  useReveal(root)
  useScene(inView, 'return', phase !== 'done')

  // Whoever scrolls away after the first tap starts again.
  useEffect(() => {
    if (!inView) setPhase((old) => (old === 'armed' ? 'ready' : old))
  }, [inView])

  const labels: Readonly<Record<Phase, string>> = { ready: app('phone.deny'), armed: t('deny.confirm'), done: t('deny.again') }
  return (
    <section
      aria-labelledby="deny-title"
      className="scrim-left relative flex min-h-[130svh] items-start py-32 lg:items-center"
      id="deny"
      ref={root}
      tabIndex={-1}
    >
      <p className="sr-only">{t('deny.alt')}</p>
      <div className="shell">
        <div className="max-w-[38rem]">
          <h2 className="display display-lg" data-reveal="0" id="deny-title">
            {t('deny.title')}
          </h2>
          <p className="mt-7 text-[1.12rem] text-text/90" data-reveal="1">
            {t('deny.text')}
          </p>
          <div className="mt-9" data-reveal="2">
            <button className="button w-full max-w-[28rem] text-[1.1rem]" onClick={() => setPhase(NEXT[phase])} type="button">
              {labels[phase]}
            </button>
            <p className="sr-only" role="status">
              {phase === 'armed' && t('deny.confirm')}
            </p>
          </div>
          <div aria-live="polite" className="mt-8" data-float>
            <GoodFaithNotice shown={phase === 'done'} />
          </div>
        </div>
      </div>
    </section>
  )
}
