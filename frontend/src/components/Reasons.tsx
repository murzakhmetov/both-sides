import { hasKey, useI18n } from '../i18n'

/** Reasons in one short line, for the middle of the demo page. */
export function ReasonLine({ codes }: { codes: readonly string[] }) {
  const { t } = useI18n()
  const words = codes.map((code) => {
    const key = `reason.${code}`
    return hasKey(key) ? t(key) : code
  })
  return (
    <p className={`mt-1 leading-snug font-semibold ${codes.includes('receiver_denied') ? 'text-held' : ''}`}>{words.join(' · ')}</p>
  )
}

interface ReasonsProps {
  readonly codes: readonly string[]
  readonly className?: string
  /** The codes themselves, for the specialist. The hall needs only the words. */
  readonly withCodes?: boolean
}

/** Why the case went this way. Staff screens only. */
export function Reasons({ codes, className = '', withCodes = false }: ReasonsProps) {
  const { t } = useI18n()
  return (
    <ul className={`space-y-1.5 ${className}`}>
      {codes.map((code) => {
        const key = `reason.${code}`
        return (
          <li className="flex flex-wrap items-baseline gap-x-2" key={code}>
            <span className={code === 'receiver_denied' ? 'font-bold text-held' : 'font-bold'}>
              {hasKey(key) ? t(key) : code}
            </span>
            {withCodes && <code className="font-mono text-sm text-muted">{code}</code>}
          </li>
        )
      })}
    </ul>
  )
}
