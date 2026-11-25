import { formatAmount } from '../format'

type Tone = 'tile' | 'hero' | 'action'
type Size = 'small' | 'medium'

const TONES: Readonly<Record<Tone, string>> = {
  tile: 'bg-line text-accent',
  hero: 'bg-on-hero text-hero',
  action: 'bg-action text-on-action',
}

const SIZES: Readonly<Record<Size, string>> = {
  small: 'size-9 text-base',
  medium: 'size-12 text-xl',
}

interface AvatarProps {
  readonly name: string
  readonly tone?: Tone
  readonly size?: Size
  readonly className?: string
}

/** The first letter of a first name in a circle. The name itself always stands next to it. */
export function Avatar({ name, tone = 'tile', size = 'medium', className = '' }: AvatarProps) {
  return (
    <span
      aria-hidden="true"
      className={`inline-flex shrink-0 items-center justify-center rounded-full font-bold ${SIZES[size]} ${TONES[tone]} ${className}`}
    >
      {[...name][0]}
    </span>
  )
}

/** Both people of one transfer. */
export function AvatarPair({ sender, receiver }: { sender: string; receiver: string }) {
  return (
    <span aria-hidden="true" className="flex shrink-0 -space-x-1.5">
      <Avatar className="ring-2 ring-surface" name={sender} size="small" />
      <Avatar className="ring-2 ring-surface" name={receiver} size="small" tone="action" />
    </span>
  )
}

/** A large amount with a smaller currency sign. */
export function Amount({ value }: { value: number }) {
  const text = formatAmount(value)
  return (
    <span className="whitespace-nowrap" data-numeric>
      {text.slice(0, -1)}
      <span className="text-[0.72em]">{text.slice(-1)}</span>
    </span>
  )
}
