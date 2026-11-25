import { useCallback, useRef, useState } from 'react'
import { MediaLayer } from '../components/Backdrop'
import { CASE_NUMBERS, MOTHER } from '../examples'
import { SOON, useInView } from '../hooks/useInView'
import { useTall } from '../hooks/useMediaQuery'
import { useLang, type AppKey } from '../lang'
import type { SceneId } from '../media'
import { useParts, useSceneOnScroll } from '../scene'
import type { TextKey } from '../texts'

const QUOTES = [
  { label: 'verdict.file.recipient', answer: MOTHER.receiver },
  { label: 'verdict.file.sender', answer: MOTHER.sender },
] as const

/** The example of scene 2: what a specialist finds ready. */
function CaseFileCard({ shown }: { shown: boolean }) {
  const { t, app, lang } = useLang()
  const rows: readonly (readonly [TextKey, string])[] = [
    ['verdict.file.facts', t('verdict.file.facts.value')],
    ['verdict.file.law', app('law.payments.title')],
    ['verdict.file.deadline', t('verdict.file.deadline.value')],
  ]
  return (
    <div className="fade case-file panel w-full max-w-[24rem] p-5 text-[0.92rem]" data-on={shown}>
      <p className="caption">{t('example.invented')}</p>
      <div className="mt-1 flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <p className="font-semibold whitespace-nowrap">
          {t('verdict.file')} {CASE_NUMBERS.mother}
        </p>
        <p className="rounded-full bg-bcc-gold/15 px-3 py-1 text-[0.875rem] font-semibold whitespace-nowrap text-bcc-gold-light">
          {app('status.with_specialist')}
        </p>
      </div>
      <div className="hairline my-3" />
      <dl className="grid gap-2.5">
        {QUOTES.map(({ label, answer }) => (
          <div key={label}>
            <dt className="text-[0.875rem] text-muted">{t(label)}</dt>
            <dd className="font-semibold">
              <span lang={answer.lang}>«{answer.text}»</span>
              {lang !== answer.lang && <span className="ml-2 font-normal text-muted">{t(answer.translation)}</span>}
            </dd>
          </div>
        ))}
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="text-[0.875rem] text-muted">{t(label)}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

interface PanelTextProps {
  readonly status: AppKey
  readonly title: TextKey
  readonly text: TextKey
  readonly alt: TextKey
}

function PanelText({ status, title, text, alt }: PanelTextProps) {
  const { t, app } = useLang()
  return (
    <div className="verdict-text scrim-bottom">
      <p className="text-[0.94rem] font-semibold text-bcc-gold-light">{app(status)}</p>
      <h3 className="display display-md mt-2">{t(title)}</h3>
      <p className="mt-3 text-[1.1rem] text-text/90">{t(text)}</p>
      <p className="sr-only">{t(alt)}</p>
    </div>
  )
}

interface PictureProps {
  readonly id: SceneId
  readonly active: boolean
  readonly near: boolean
  readonly over?: boolean
}

function Picture({ id, active, near, over = false }: PictureProps) {
  const aspect = useTall() ? '9x16' : '16x9'
  return <MediaLayer active={active} aspect={aspect} id={id} near={near} over={over} />
}

/** Split outcome: clip F on the left, G on the right. One plays at a time. */
export function Verdict() {
  const { t } = useLang()
  const root = useRef<HTMLDivElement>(null)
  const [part, setPart] = useState(0)
  const inView = useInView(root)
  const soon = useInView(root, SOON)
  useSceneOnScroll(root, 'terraces')
  useParts(root, 2, useCallback((next: number) => setPart(next), []))

  return (
    <section aria-labelledby="verdict-title" className="relative" id="verdict" tabIndex={-1}>
      <h2 className="sr-only" id="verdict-title">
        {t('verdict.title')}
      </h2>
      <div className="relative h-[230svh]" ref={root}>
        <div className="verdict-grid sticky top-0 grid h-svh grid-rows-2 overflow-hidden bg-ink lg:grid-rows-1" data-part={part}>
          <article className="verdict-panel" data-on={part === 0}>
            <Picture active={inView && part === 0} id="match" near={soon} over={part === 1} />
            <PanelText alt="verdict.match.alt" status="status.credited" text="verdict.match.text" title="verdict.match.title" />
          </article>
          <article className="verdict-panel verdict-panel-file" data-on={part === 1}>
            <Picture active={inView && part === 1} id="mismatch" near={soon} />
            <div className="absolute inset-x-0 top-[5.8rem] z-10 hidden justify-end pr-16 pl-8 lg:flex" data-float>
              <CaseFileCard shown={part === 1} />
            </div>
            <PanelText
              alt="verdict.mismatch.alt"
              status="status.with_specialist"
              text="verdict.mismatch.text"
              title="verdict.mismatch.title"
            />
          </article>
        </div>
      </div>
      <div className="relative bg-ink px-5 py-10 lg:hidden">
        <CaseFileCard shown />
      </div>
    </section>
  )
}
