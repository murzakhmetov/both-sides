import { useEffect } from 'react'
import { loginPath } from '../routes'

/** Sends the browser to the login page when the session is missing or over. */
export function useStaffOnly(errorCode: string): void {
  useEffect(() => {
    if (errorCode !== 'login_required') return
    // Inside the demo page the whole window goes to the login, not one frame.
    const target = window.top ?? window
    target.location.assign(loginPath(target.location.pathname))
  }, [errorCode])
}
