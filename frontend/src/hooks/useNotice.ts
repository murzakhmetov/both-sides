import { useEffect, useState } from 'react'

const SHOWN_MS = 6000

/** An error code that goes away by itself after a few seconds. */
export function useNotice(): [string, (code: string) => void] {
  const [code, setCode] = useState('')

  useEffect(() => {
    if (code === '') return undefined
    const timer = window.setTimeout(() => setCode(''), SHOWN_MS)
    return () => window.clearTimeout(timer)
  }, [code])

  return [code, setCode]
}
