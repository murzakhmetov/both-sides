import { useRef } from 'react'
import { auc, groups } from '../../../../evaluation/results/offline.json'
import { useReveal } from '../hooks/useReveal'
import { useLang } from '../lang'
import { useSceneOnScroll } from '../scene'
import type { Lang, TextKey } from '../texts'

/** Why BCC: the duty of the law, written on the monolith. */
export function Why() {
  const { t } = useLang()
  const root = useRef<HTMLElement>(null)
  useSceneOnScroll(root, 'monolith')
  useReveal(root)
  return (
    <section
      aria-labelledby="why-title"
      className="relative flex min-h-svh items-center justify-center py-28"
      id="why"
      ref={root}
      tabIndex={-1}
    >
      <div className="monolith-card">
        <h2 className="display display-md text-bcc-gold-light" data-reveal="0" id="why-title">
          {t('why.title')}
        </h2>
        <p className="mt-6 text-[1.08rem] font-medium" data-reveal="1">
          {t('why.text')}
        </p>
        <div className="hairline my-7" data-reveal="2" />
        <p className="text-[1rem] text-text/90" data-reveal="3">
          {t('why.found')}
        </p>
      </div>
    </section>
  )
}

const CHIPS: readonly TextKey[] = ['status.ai', 'status.gemini', 'status.demo', 'status.next']
const GROUPS = ['honest', 'stranger', 'other_transfer', 'told_one_line'] as const

/** Two digits, with a comma in Russian and Kazakh. */
function twoDigits(value: number, lang: Lang): string {
  const text = value.toFixed(2)
  return lang === 'en' ? text : text.replace('.', ',')
}

/** Only numbers that the evaluation script printed and saved. */
function Numbers() {
  const { t, lang } = useLang()
  const all = auc['all others']
  const pairs = GROUPS.reduce((sum, group) => sum + groups[group].pairs, 0)
  return (
    <div className="panel mt-10 p-6 sm:p-8">
      <p className="text-text/90">{t('status.numbers', { n: pairs })}</p>
      <dl className="mt-6 grid gap-x-10 gap-y-5 md:grid-cols-2">
        <div>
          <dt className="caption">{t('status.auc')}</dt>
          <dd className="display display-md mt-1">
            {twoDigits(all.auc, lang)}{' '}
            <span className="font-body text-[0.94rem] tracking-normal text-muted">
              {t('status.interval', { low: twoDigits(all.interval[0] ?? 0, lang), high: twoDigits(all.interval[1] ?? 0, lang) })}
            </span>
          </dd>
        </div>
        <div>
          <dt className="caption">{t('status.released')}</dt>
          <dd className="mt-2 grid gap-1.5">
            {GROUPS.map((group) => (
              <p key={group}>
                <strong className="font-semibold">
                  {t('status.of', { a: groups[group].released, b: groups[group].pairs })}
                </strong>{' '}
                <span className="text-muted">{t(`status.group.${group}`)}</span>
              </p>
            ))}
          </dd>
        </div>
      </dl>
      <div className="hairline my-6" />
      <p className="text-text/90">{t('status.limit')}</p>
    </div>
  )
}

/** The honest status of the AI part. */
export function Status() {
  const { t } = useLang()
  const root = useRef<HTMLElement>(null)
  useSceneOnScroll(root, 'line')
  useReveal(root)
  return (
    <section aria-labelledby="status-title" className="scrim-full relative py-32 lg:py-44" id="status" ref={root} tabIndex={-1}>
      <div className="shell relative">
        <h2 className="display display-lg" data-reveal="0" id="status-title">
          {t('status.title')}
        </h2>
        <ul className="mt-9 flex flex-wrap gap-3" data-reveal="1">
          {CHIPS.map((key) => (
            <li
              className="flex items-center gap-3 rounded-full border border-bcc-green/55 bg-bcc-green/10 px-5 py-2.5 text-[0.98rem] font-medium"
              key={key}
            >
              <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-full bg-bcc-green" />
              {t(key)}
            </li>
          ))}
        </ul>
        <div data-reveal="2">
          <Numbers />
        </div>
      </div>
    </section>
  )
}

export function Closing() {
  const { t, lang } = useLang()
  const root = useRef<HTMLElement>(null)
  useSceneOnScroll(root, 'hero')
  useReveal(root)
  return (
    <section
      aria-labelledby="closing-title"
      className="scrim-left relative flex min-h-svh flex-col justify-between pt-36"
      id="closing"
      ref={root}
      tabIndex={-1}
    >
      <div className="shell">
        <h2 className="display display-xl max-w-[46rem]" data-reveal="0" id="closing-title">
          {t('closing.title')}
        </h2>
        <p className="mt-9" data-reveal="1">
          <a className="button button-gold" href="/start">
            {t('nav.demo')}
          </a>
        </p>
        <p className="mt-9 text-[1.05rem] text-muted" data-reveal="2">
          {t('closing.team')} ·{' '}
          <a className="whitespace-nowrap text-text underline decoration-white/35 underline-offset-4" href={`tel:${t('closing.contact').replace(/\s/g, '')}`}>
            {t('closing.contact')}
          </a>
        </p>
      </div>
      <footer className="mt-24 bg-ink/85 py-7">
        <div className="shell caption grid gap-1.5">
          <p className="text-text">{t('footer.note')}</p>
          <p>{t('footer.ai')}</p>
          {lang === 'kk' && <p>{t('lang.beta')}</p>}
        </div>
      </footer>
    </section>
  )
}
