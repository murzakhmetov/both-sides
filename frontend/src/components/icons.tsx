import type { ReactNode } from 'react'

interface IconProps {
  readonly className?: string
}

function Icon({ className = 'size-5', children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
    >
      {children}
    </svg>
  )
}

export function CheckIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </Icon>
  )
}

export function PersonIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c.8-3.6 3.6-5.5 7-5.5s6.200 1.900 7 5.500" />
    </Icon>
  )
}

export function PauseIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M9 6v12M15 6v12" />
    </Icon>
  )
}

export function ReturnIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M9 7L4.500 11.500 9 16" />
      <path d="M5 11.500h9a5 5 0 0 1 0 10h-2" />
    </Icon>
  )
}

export function LockIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <rect height="9" rx="2" width="13" x="5.500" y="11" />
      <path d="M8.500 11V8a3.500 3.500 0 0 1 7 0v3" />
    </Icon>
  )
}

export function ClockIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.500" />
      <path d="M12 7.500V12l3 2" />
    </Icon>
  )
}

export function AlertIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 4l9 16H3z" />
      <path d="M12 10v4.500M12 17.300v.1" />
    </Icon>
  )
}

export function ShieldIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 3.500l7 2.500v5.500c0 4.300-2.900 7.600-7 9-4.100-1.400-7-4.700-7-9V6z" />
      <path d="M9 12l2.200 2.200L15 10.300" />
    </Icon>
  )
}

export function CalendarIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <rect height="15" rx="3" width="16" x="4" y="5.500" />
      <path d="M8 3.500v4M16 3.500v4M4 10.500h16" />
    </Icon>
  )
}

export function LawIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M12 4v16M8 20h8M5 7h14" />
      <path d="M6.500 7L4 13h5zM17.500 7L15 13h5z" />
    </Icon>
  )
}

export function MessageIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M5 5.500h14a1.500 1.500 0 0 1 1.500 1.500v8a1.500 1.500 0 0 1-1.500 1.500h-7.500L7 20v-3.500H5A1.500 1.500 0 0 1 3.500 15V7A1.500 1.500 0 0 1 5 5.500z" />
    </Icon>
  )
}

export function PhoneIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <rect height="18" rx="3" width="10" x="7" y="3" />
      <path d="M11 17.500h2" />
    </Icon>
  )
}

export function ScreenIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <rect height="11" rx="2.500" width="18" x="3" y="4.500" />
      <path d="M12 15.500v4M8 19.500h8" />
    </Icon>
  )
}

export function FolderIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M3.500 8A2 2 0 0 1 5.500 6h4l2 2.500h7a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" />
    </Icon>
  )
}

export function ChevronIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M9.500 6l6 6-6 6" />
    </Icon>
  )
}

/** The product mark: two sides facing each other. Each half can be lit on its own. */
export function Mark({
  className = 'size-7',
  left = true,
  right = true,
}: IconProps & { readonly left?: boolean; readonly right?: boolean }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 32 32">
      <path
        className={`transition-opacity duration-200 ${left ? 'opacity-100' : 'opacity-25'}`}
        d="M14.500 5.100v21.800A11 11 0 0 1 14.500 5.100z"
        fill="currentColor"
      />
      <path
        className={`transition-opacity duration-200 ${right ? 'opacity-100' : 'opacity-25'}`}
        d="M17.500 5.100v21.800A11 11 0 0 0 17.500 5.100z"
        fill="var(--action-strong)"
      />
    </svg>
  )
}
