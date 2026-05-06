import { html } from '../html.js'
import { Link, useLocation } from 'https://esm.sh/react-router-dom@6.23.1'

function NavItem({ to, label, active }) {
  return html`
    <${Link}
      to=${to}
      className=${
        active
          ? 'rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white'
          : 'rounded-lg px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100'
      }
    >
      ${label}
    <//>
  `
}

export function TopBar() {
  const loc = useLocation()
  const path = loc.pathname
  return html`
    <div className="sticky top-0 z-10 border-b border-zinc-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-blue-600"></div>
          <div>
            <div className="text-sm font-semibold leading-5">Chỉ tiêu CN/PGD</div>
            <div className="text-xs text-zinc-500">Giao/điều chỉnh chỉ tiêu KHTD</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <${NavItem} to=${'/'} label=${'Trang chủ'} active=${path === '/'} />
          <${NavItem} to=${'/google-sheet-import'} label=${'Nhập Google Sheet'} active=${path === '/google-sheet-import'} />
          <${NavItem} to=${'/targets'} label=${'Giao/Điều chỉnh'} active=${path === '/targets'} />
        </div>
      </div>
    </div>
  `
}

