import { useRef } from 'react'
import { useReveal } from '../hooks/useReveal'
import { useLang } from '../lang'
import { useSceneOnScroll } from '../scene'

const ARTICLE = 'https://www.bcc.kz/about/press-center/safe-account/'

/** The problem: clip C. */
export function Problem() {
  const { t } = useLang()
  const root = useRef<HTMLElement>(null)
  useSceneOnScroll(root, 'whisper')
  useReveal(root)
  return (
    <section
      aria-labelledby="problem-title"
      className="scrim-left relative flex min-h-[125svh] items-start py-32 lg:items-center"
      id="problem"
      ref={root}
      tabIndex={-1}
    >
      <p className="sr-only">{t('problem.alt')}</p>
      <div className="shell">
        <div className="max-w-[40rem]">
          <h2 className="display display-lg" data-reveal="0" id="problem-title">
            {t('problem.title')}
          </h2>
          <p className="mt-8 max-w-[31rem] text-[1.12rem] text-text/90" data-reveal="1">
            {t('problem.line1')}
          </p>
          <p className="mt-4 max-w-[31rem] text-[1.12rem] text-text/90" data-reveal="2">
            {t('problem.line2')}
          </p>
          <p className="mt-6" data-reveal="3">
            <a
              className="inline-flex min-h-12 items-center gap-2 border-b border-bcc-gold/60 text-bcc-gold-light transition-colors hover:border-bcc-gold-light"
              href={ARTICLE}
              rel="noreferrer"
              target="_blank"
            >
              {t('problem.link')} <span aria-hidden="true">↗</span>
              <span className="sr-only">({t('link.new_tab')})</span>
            </a>
          </p>
        </div>
      </div>
    </section>
  )
}

/** The insight: text only, huge, over a still. */
export function Insight() {
  const { t } = useLang()
  const root = useRef<HTMLElement>(null)
  useSceneOnScroll(root, 'terraces')
  useReveal(root)
  const words = t('insight.title').split(' ')
  return (
    <section
      aria-labelledby="insight-title"
      className="scrim-full relative flex min-h-[120svh] items-center py-32"
      id="insight"
      ref={root}
      tabIndex={-1}
    >
      <div className="shell">
        <h2 aria-label={t('insight.title')} className="display display-xl max-w-[16ch]" id="insight-title">
          {words.map((word, index) => (
            <span aria-hidden="true" className="inline-block whitespace-pre" data-reveal={index} key={`${word}-${index}`}>
              {word}{' '}
            </span>
          ))}
        </h2>
      </div>
    </section>
  )
}
