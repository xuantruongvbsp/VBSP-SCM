import { html } from '../html.js'

export function Card({ title, right, children }) {
  return html`
    <div className="rounded-xl border border-zinc-200 bg-white shadow-sm">
      ${title || right
        ? html`
            <div className="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
              <div className="text-sm font-semibold text-zinc-900">${title || ''}</div>
              <div>${right || ''}</div>
            </div>
          `
        : ''}
      <div className="p-4">${children}</div>
    </div>
  `
}

