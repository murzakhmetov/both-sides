import { useCallback, useRef, useState } from 'react'
import { PhoneMock, usePhoneWords, type PhoneState, type Side } from '../components/PhoneMock'
import { useFit } from '../hooks/useFit'
import { useInView } from '../hooks/useInView'
import { useLang } from '../lang'
import { useParts, useScene } from '../scene'
import type { TextKey } from '../texts'

interface Frame {
  readonly text: TextKey
  readonly receiver: PhoneState
  readonly sender: PhoneState
  /** The phone people should look at; both when empty. */
  readonly focus: Side | null
  readonly lock: boolean
  readonly verdict: boolean
}

const FIRST: Frame = { text: 'how.1', receiver: 'stopped', sender: 'stopped', focus: null, lock: false, verdict: false }

const FRAMES: readonly Frame[] = [
  FIRST,
  { text: 'how.2', receiver: 'question', sender: 'stopped', focus: 'receiver', lock: true, verdict: false },
  { text: 'how.3', receiver: 'answered', sender: 'question', focus: 'sender', lock: true, verdict: false },
  { text: 'how.4', receiver: 'answered', sender: 'answered', focus: null, lock: true, verdict: false },
  { text: 'how.5', receiver: 'credited', sender: 'credited', focus: null, lock: false, verdict: true },
  { text: 'how.6', receiver: 'offer', sender: 'stopped', focus: 'receiver', lock: false, verdict: false },
]

/** The first steps happen in two separate rooms, the rest at the core. */
const CORE_FROM_STEP = 3

function Lock({ shown }: { shown: boolean }) {
  const { t } = useLang()
  return (
    <div className="fade flex flex-col items-center gap-3 text-center" data-on={shown}>
      <span className="flex h-14 w-14 items-center justify-center rounded-full border border-white/25 bg-ink/70">
        <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.6" viewBox="0 0 24 24">
          <rect height="10" rx="2.5" width="15" x="4.5" y="10.5" />
          <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
        </svg>
      </span>
      <span className="caption max-w-[9.5rem] rounded-xl bg-ink/75 px-3 py-1 text-text">{t('how.lock')}</span>
    </div>
  )
}

/** All steps as a list, with the words of both phones, and a short note when the step changes. */
function ForScreenReaders({ step }: { step: number }) {
  const { t } = useLang()
  const words = usePhoneWords()
  return (
    <div className="sr-only">
      <p>{t('how.alt')}</p>
      <ol>
        {FRAMES.map((frame) => (
          <li key={frame.text}>
            <p>{t(frame.text)}</p>
            <p>{words('receiver', frame.receiver)}</p>
            <p>{words('sender', frame.sender)}</p>
          </li>
        ))}
      </ol>
      <p aria-live="polite">{t('how.step', { n: step + 1, total: FRAMES.length })}</p>
    </div>
  )
}

function Phones({ frame }: { frame: Frame }) {
  const { app, lang } = useLang()
  const area = useRef<HTMLDivElement>(null)
  useFit(area, frame.text, lang)
  const lit = (side: Side) => frame.focus === null || frame.focus === side
  return (
    <div
      aria-hidden="true"
      className="how-phones shell grid min-h-0 flex-1 grid-cols-1 items-center justify-items-center gap-4 md:grid-cols-[1fr_auto_1fr] md:gap-5 xl:gap-8"
      ref={area}
    >
      <div
        className="how-phone w-full justify-items-center md:justify-items-end"
        data-float
        data-front={frame.focus !== 'sender'}
      >
        <PhoneMock on={lit('receiver')} side="receiver" state={frame.receiver} />
      </div>
      <div className="relative hidden w-36 place-items-center md:grid xl:w-44">
        <div className="col-start-1 row-start-1">
          <Lock shown={frame.lock} />
        </div>
        <p
          className="fade col-start-1 row-start-1 rounded-full bg-bcc-green px-5 py-2 text-center text-[0.94rem] font-semibold whitespace-nowrap text-ink"
          data-on={frame.verdict}
        >
          {app('verdict.same')}
        </p>
      </div>
      <div
        className="how-phone w-full justify-items-center md:justify-items-start"
        data-float
        data-front={frame.focus === 'sender'}
      >
        <PhoneMock on={lit('sender')} side="sender" state={frame.sender} />
      </div>
    </div>
  )
}

function StepBar({ step }: { step: number }) {
  const { t } = useLang()
  return (
    <div aria-hidden="true" className="how-steps scrim-bottom relative z-10 pt-6 pb-6 lg:pb-12">
      <div className="shell">
        <p className="caption text-text">{t('how.step', { n: step + 1, total: FRAMES.length })}</p>
        <div className="mt-2 grid">
          {FRAMES.map((frame, index) => (
            <p
              className="fade col-start-1 row-start-1 max-w-[52rem] text-[1rem] leading-snug font-medium sm:text-[1.3rem]"
              data-on={index === step}
              key={frame.text}
            >
              {t(frame.text)}
            </p>
          ))}
        </div>
        <div className="how-progress mt-5 grid max-w-[30rem] grid-cols-6 gap-2">
          {FRAMES.map((frame, index) => (
            <span
              className="h-0.5 rounded-full bg-white/45 transition-colors duration-500 data-[on=true]:bg-bcc-gold"
              data-on={index <= step}
              key={frame.text}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

/** Sticky sequence of the six steps: clip D, then E. */
export function How() {
  const { t } = useLang()
  const root = useRef<HTMLElement>(null)
  const [step, setStep] = useState(0)
  const inView = useInView(root)
  useParts(root, FRAMES.length, useCallback((next: number) => setStep(next), []))
  useScene(inView, step < CORE_FROM_STEP ? 'chambers' : 'core')

  return (
    <section aria-labelledby="how-title" className="relative h-[620svh]" id="how" ref={root} tabIndex={-1}>
      <div className="how-stage sticky top-0 flex h-svh flex-col overflow-hidden bg-ink/45">
        <div className="how-title shell pt-24">
          <h2 className="display display-md" id="how-title">
            {t('how.title')}
          </h2>
        </div>
        <ForScreenReaders step={step} />
        <Phones frame={FRAMES[step] ?? FIRST} />
        <StepBar step={step} />
      </div>
    </section>
  )
}
