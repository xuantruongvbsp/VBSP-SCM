import { html, React } from '../html.js'
import { useAppState } from '../state.js'

export function ToastHost() {
  const { toast, setToast } = useAppState()

  React.useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 2500)
    return () => clearTimeout(t)
  }, [toast, setToast])

  if (!toast) return null

  const tone = toast.tone || 'info'
  const toneClass =
    tone === 'success'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
      : tone === 'error'
        ? 'border-red-200 bg-red-50 text-red-900'
        : tone === 'warning'
          ? 'border-amber-200 bg-amber-50 text-amber-900'
          : 'border-blue-200 bg-blue-50 text-blue-900'

  return html`
    <div className="fixed bottom-4 left-1/2 z-50 w-[min(520px,calc(100vw-32px))] -translate-x-1/2">
      <div className=${`rounded-xl border px-4 py-3 text-sm shadow-lg ${toneClass}`}>${toast.message}</div>
    </div>
  `
}

