import * as React from "react"

const MOBILE_BREAKPOINT = 768

export function useIsMobile() {
  // Initialize to false so the first client render matches the server
  // (which has no window and renders the desktop variant). The correct
  // value is applied in the effect below. Reading window.innerWidth
  // synchronously here would render the mobile Sheet on the client while
  // the server rendered the desktop sidebar -> hydration mismatch.
  const [isMobile, setIsMobile] = React.useState(false)

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
    const onChange = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
    }
    mql.addEventListener("change", onChange)
    onChange()
    return () => mql.removeEventListener("change", onChange)
  }, [])

  return isMobile
}
