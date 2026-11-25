import { useCallback, useRef, useState } from 'react'
import { useLang } from '../lang'
import { useInView } from '../hooks/useInView'
import { useParts, useScene } from '../scene'

/** Clip A, then B: on scroll the bills stop in the air. */
export function Hero() {
  const { t } = useLang()
  const root = useRef<HTMLElement>(null)
  const [part, setPart] = useState(0)
  const inView = useInView(root)
  useParts(root, 2, useCallback((next: number) => setPart(next), []))
  useScene(inView, part === 0 ? 'hero' : 'freeze')

  return (
    <section aria-labelledby="hero-title" className="relative h-[210svh]" id="hero" ref={root} tabIndex={-1}>
      <p className="sr-only">{t('hero.alt')}</p>
      <div className="scrim-left sticky top-0 h-svh overflow-hidden">
        <div className="shell relative flex h-full flex-col justify-start pt-[6.7rem] sm:pt-28 lg:justify-center lg:pt-16">
          <div className="grid">
            <div className="fade col-start-1 row-start-1 max-w-[46rem]" data-on={part === 0}>
              {/* Wider windows say this in the bar at the top. */}
              <p className="caption mb-4 text-bcc-gold-light sm:hidden">{t('nav.tag')}</p>
              <h1 className="display display-xl" id="hero-title">
                {t('hero.title')}
              </h1>
              <p className="mt-7 max-w-[33rem] text-[1.15rem] text-text/90">{t('hero.sub')}</p>
              <p className="mt-7 md:hidden">
                <a className="button bg-ink/75" href="/start">
                  {t('nav.demo')}
                </a>
              </p>
              <p className="cue caption mt-8 md:mt-10">
                <span className="-ml-2 rounded-lg bg-ink/80 px-2 py-0.5 text-text">{t('hero.cue')}</span>
              </p>
            </div>
            <div className="fade col-start-1 row-start-1 max-w-[42rem]" data-on={part === 1}>
              <h2 className="display display-lg">{t('freeze.title')}</h2>
              <div className="hairline mt-8 w-full max-w-[26rem]" />
              <p className="mt-6 max-w-[30rem] text-[1.15rem] text-text/90">{t('freeze.text')}</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
