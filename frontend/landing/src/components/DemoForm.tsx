import { MAX_ANSWER_LENGTH, MIN_ANSWER_LENGTH, type TryAnswer } from '../api'
import { PAIRS, type Pair } from '../examples'
import { isEmpty, useDemo, type DemoState, type Draft } from '../hooks/useDemo'
import { useLang } from '../lang'

const ERROR_ID = 'demo-error'

function Examples({ onChoose }: { onChoose: (pair: Pair) => void }) {
  const { t } = useLang()
  return (
    <fieldset className="flex flex-wrap items-center gap-2">
      <legend className="caption mb-2">{t('demo.examples')}</legend>
      {PAIRS.map((pair) => (
        <button
          className="button min-h-12 px-4 py-2 text-[0.92rem]"
          key={pair.label}
          onClick={() => onChoose(pair)}
          type="button"
        >
          {t(pair.label)}
        </button>
      ))}
    </fieldset>
  )
}

interface FieldProps {
  readonly label: string
  readonly draft: Draft
  readonly invalid: boolean
  readonly onChange: (text: string) => void
}

function Field({ label, draft, invalid, onChange }: FieldProps) {
  return (
    <label className="block">
      <span className="mb-2 block font-semibold">{label}</span>
      <textarea
        aria-describedby={invalid ? ERROR_ID : undefined}
        aria-invalid={invalid}
        className="field"
        lang={draft.lang}
        maxLength={MAX_ANSWER_LENGTH}
        onChange={(event) => onChange(event.target.value)}
        value={draft.text}
      />
    </label>
  )
}

function Verdict({ answer }: { answer: TryAnswer }) {
  const { t, app, reason } = useLang()
  const match = answer.result === 'match'
  const known = answer.reasons.map(reason).filter((text) => text !== null)
  const lines = match ? [t('demo.reason.match')] : known
  return (
    <div className={`rounded-2xl border p-5 ${match ? 'border-bcc-gold/60 bg-bcc-gold/10' : 'border-white/25 bg-white/5'}`}>
      <p className={`display display-md uppercase ${match ? 'text-bcc-gold-light' : 'text-text'}`}>
        {match ? t('demo.match') : app('status.with_specialist')}
      </p>
      <ul className="mt-3 grid gap-1">
        {(lines.length > 0 ? lines : [t('demo.reason.other')]).map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </div>
  )
}

/** Screen readers hear every change of this part. */
function Outcome({ state }: { state: DemoState }) {
  const { t } = useLang()
  return (
    <div aria-live="polite">
      {state.kind === 'busy' && <p className="sr-only">{t('demo.comparing')}</p>}
      {state.kind === 'done' && <Verdict answer={state.answer} />}
      {state.kind === 'error' && (
        <p className="pt-3 font-semibold text-bcc-gold-soft" id={ERROR_ID}>
          {t(state.text, { min: MIN_ANSWER_LENGTH, max: MAX_ANSWER_LENGTH })}
        </p>
      )}
    </div>
  )
}

export function DemoForm() {
  const { t } = useLang()
  const { receiver, sender, state, change, choose, submit } = useDemo()
  const missing = state.kind === 'error' && state.text === 'demo.error.empty'
  const busy = state.kind === 'busy'
  return (
    <form className="panel p-5 sm:p-7" noValidate onSubmit={submit}>
      <Examples onChoose={choose} />
      <div className="mt-6 grid gap-5 md:grid-cols-2">
        <Field
          draft={receiver}
          invalid={missing && isEmpty(receiver)}
          label={t('demo.recipient')}
          onChange={(text) => change('receiver', text)}
        />
        <Field
          draft={sender}
          invalid={missing && isEmpty(sender)}
          label={t('demo.sender')}
          onChange={(text) => change('sender', text)}
        />
      </div>
      <div className="mt-6 grid gap-x-8 gap-y-5 lg:grid-cols-[17rem_1fr]">
        <div>
          <button aria-disabled={busy} className="button button-gold w-full" type="submit">
            {t(busy ? 'demo.comparing' : 'demo.compare')}
          </button>
          <p className="caption mt-3">{t('demo.private')}</p>
        </div>
        <Outcome state={state} />
      </div>
    </form>
  )
}
