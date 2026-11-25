import { useEffect, useState } from 'react'

/** True while the value is true and a little longer, so that a fade can end. */
export function useLinger(on: boolean, milliseconds: number): boolean {
  const [late, setLate] = useState(on)
  useEffect(() => {
    if (on) {
      setLate(true)
      return undefined
    }
    const timer = window.setTimeout(() => setLate(false), milliseconds)
    return () => window.clearTimeout(timer)
  }, [on, milliseconds])
  return on || late
}
