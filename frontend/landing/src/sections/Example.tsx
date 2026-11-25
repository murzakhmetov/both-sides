import { useEffect, useRef, useState } from 'react'
import { MOTHER } from '../examples'
import { useReducedMotion } from '../hooks/useMediaQuery'
import { useReveal } from '../hooks/useReveal'
import { useLang } from '../lang'
import { useSceneOnScroll } from '../scene'
import { gsap } from '../scroll'
import type { TextKey } from '../texts'

interface CardProps {
  readonly side: 'left' | 'right'
  readonly label: TextKey
  readonly answer: (typeof MOTHER)[keyof typeof MOTHER]
  /** A short mark on the card that lights up when the stories have met. */
  readonly tag?: { readonly text: TextKey; readonly on: boolean }
}

/** A puzzle piece: the left one has a round knob, the right one a pointed hole. They cannot fit. */
function AnswerCard({ side, label, answer, tag }: CardProps) {
  const { t, lang } = useLang()
  return (
    <div className={`answer-card panel answer-${side} relative flex min-h-[13rem] flex-col justify-center p-7 sm:p-9`}>
      <span aria-hidden="true" className={side === 'left' ? 'knob' : 'notch'} />
      {tag && (
        <p
          className="fade absolute -top-5 right-6 rounded-full border border-bcc-gold/60 bg-panel-2 px-4 py-1.5 text-[0.88rem] font-semibold text-bcc-gold-light"
          data-on={tag.on}
        >
          {t(tag.text)}
        </p>
      )}
      <p className="caption">{t(label)}</p>
      <p className="display-md mt-3 font-display font-medium" lang={answer.lang}>
        «{answer.text}»
      </p>
      {lang !== answer.lang && <p className="mt-3 text-muted">{t(answer.translation)}</p>}
    </div>
  )
}

/** The mother story: two answers that visibly do not fit together. */
export function Example() {
  const { t, app } = useLang()
  const root = useRef<HTMLElement>(null)
  const cards = useRef<HTMLDivElement>(null)
  const still = useReducedMotion()
  const [met, setMet] = useState(false)
  useSceneOnScroll(root, 'terraces')
  useReveal(root)

  useEffect(() => {
    const group = cards.current
    if (!group) return undefined
    if (still) {
      setMet(true)
      return undefined
    }
    const context = gsap.context(() => {
      gsap
        .timeline({
          scrollTrigger: {
            trigger: group,
            start: 'top 82%',
            end: 'top 46%',
            scrub: 0.6,
            onUpdate: (self) => setMet(self.progress > 0.94),
          },
        })
        .fromTo('.answer-left', { xPercent: -26, rotate: -2.5 }, { xPercent: 0, rotate: 0, ease: 'none' }, 0)
        .fromTo('.answer-right', { xPercent: 26, rotate: 2.5 }, { xPercent: 0, rotate: 0, ease: 'none' }, 0)
    }, group)
    return () => context.revert()
  }, [still])

  return (
    <section
      aria-labelledby="example-title"
      className="scrim-full relative flex min-h-[130svh] items-center overflow-x-clip py-32"
      id="example"
      ref={root}
      tabIndex={-1}
    >
      <div className="shell">
        <h2 className="display display-lg max-w-[14ch]" data-reveal="0" id="example-title">
          {t('example.title')}
        </h2>
        <p className="mt-7 max-w-[38rem] text-[1.12rem] text-text/90" data-reveal="1">
          {t('example.text')}
        </p>
        <div data-float>
          <div className="relative mt-14 grid gap-8 md:grid-cols-2 md:gap-10" ref={cards}>
            <AnswerCard answer={MOTHER.sender} label="example.sender" side="left" />
            <AnswerCard answer={MOTHER.receiver} label="example.recipient" side="right" tag={{ text: 'example.tag', on: met }} />
            <span
              aria-hidden="true"
              className="seam absolute top-1/2 left-1/2 hidden h-[72%] w-px -translate-x-1/2 -translate-y-1/2 bg-mismatch transition-opacity duration-700 md:block"
              data-on={met}
            />
          </div>
        </div>
        <div className="fade mt-10" data-on={met}>
          <p className="text-mismatch">{t('example.gap')}</p>
          <p className="display display-md mt-2">
            <span className="text-bcc-gold-light">{app('status.with_specialist')}</span>
            {t('example.result')}
          </p>
        </div>
      </div>
    </section>
  )
}
