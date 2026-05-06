import { html } from '../html.js'
import { formatNumber } from '../utils.js'

export function TargetsTable({ title, rows, editedMap, onChangeValue }) {
  return html`
    <div className="rounded-xl border border-zinc-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-zinc-100 px-4 py-3">
        <div className="text-sm font-semibold">${title}</div>
        <div className="text-xs text-zinc-500">${rows.length} dòng</div>
      </div>
      <div className="max-h-[calc(100vh-300px)] overflow-auto">
        <table className="w-full border-separate border-spacing-0">
          <thead className="sticky top-0 bg-white">
            <tr className="text-left text-xs text-zinc-500">
              <th className="border-b border-zinc-100 px-4 py-3">Cấp</th>
              <th className="border-b border-zinc-100 px-4 py-3">Mã</th>
              <th className="border-b border-zinc-100 px-4 py-3">Tên</th>
              <th className="border-b border-zinc-100 px-4 py-3">Chỉ tiêu</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((r) => {
              const edited = editedMap.has(r.unitCode)
              return html`
                <tr className=${edited ? 'bg-blue-50/40' : ''}>
                  <td className="border-b border-zinc-50 px-4 py-3 text-sm text-zinc-700">${r.level}</td>
                  <td className="border-b border-zinc-50 px-4 py-3 text-sm font-medium text-zinc-900">${r.unitCode}</td>
                  <td className="border-b border-zinc-50 px-4 py-3 text-sm text-zinc-900">${r.unitName}</td>
                  <td className="border-b border-zinc-50 px-4 py-2">
                    <div className="flex items-center justify-end gap-2">
                      <input
                        className="w-44 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-right text-sm tabular-nums outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
                        value=${String(r.targetValue ?? '')}
                        onInput=${(e) => onChangeValue(r.unitCode, e.target.value)}
                        inputMode="decimal"
                      />
                      <div className="hidden w-24 text-right text-xs text-zinc-500 md:block">${formatNumber(r.targetValue)}</div>
                    </div>
                  </td>
                </tr>
              `
            })}
          </tbody>
        </table>
      </div>
    </div>
  `
}

