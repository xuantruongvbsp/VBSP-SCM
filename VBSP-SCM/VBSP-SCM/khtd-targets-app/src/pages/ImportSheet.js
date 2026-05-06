import { html, React } from '../html.js'
import { Card } from '../components/Card.js'
import { useAppState } from '../state.js'
import { apiPost } from '../api.js'
import { formatNumber } from '../utils.js'

export function ImportSheetPage() {
  const { period, setLastSync, setToast } = useAppState()
  const [sheetUrl, setSheetUrl] = React.useState('')
  const [sheetName, setSheetName] = React.useState('KHTD')
  const [periodLocal, setPeriodLocal] = React.useState(period)
  const [loading, setLoading] = React.useState(false)
  const [preview, setPreview] = React.useState(null)

  async function onPreview() {
    setLoading(true)
    try {
      const data = await apiPost('/api/sheets/preview', { sheetUrl, sheetName, period: periodLocal })
      setPreview(data.preview)
      setLastSync({ status: data.preview.errors?.length ? 'error' : 'success', at: new Date().toISOString().slice(0, 19), sheetUrl, sheetName, period: periodLocal })
      setToast({ tone: data.preview.errors?.length ? 'warning' : 'success', message: data.preview.errors?.length ? 'Có lỗi dữ liệu, hãy kiểm tra danh sách lỗi.' : 'Xem trước thành công.' })
    } catch (e) {
      setToast({ tone: 'error', message: `Không tải được preview: ${e.message}` })
    } finally {
      setLoading(false)
    }
  }

  function onClear() {
    setSheetUrl('')
    setSheetName('KHTD')
    setPreview(null)
  }

  return html`
    <div className="mx-auto grid max-w-5xl grid-cols-1 gap-4 px-4 py-6 md:grid-cols-12">
      <div className="md:col-span-4">
        <${Card} title=${'Nguồn Google Sheet'}>
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-600">Link Google Sheet</label>
              <input
                className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
                value=${sheetUrl}
                onInput=${(e) => setSheetUrl(e.target.value)}
                placeholder="https://docs.google.com/spreadsheets/..."
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-600">Tên tab</label>
              <input
                className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
                value=${sheetName}
                onInput=${(e) => setSheetName(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-600">Kỳ/đợt</label>
              <input
                className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
                value=${periodLocal}
                onInput=${(e) => setPeriodLocal(e.target.value)}
              />
            </div>
            <div className="pt-2 text-xs text-zinc-500">
              Demo sử dụng API mock. Thực tế cần quyền truy cập Google Sheet để đồng bộ.
            </div>
            <div className="flex items-center gap-2 pt-2">
              <button
                className=${
                  loading
                    ? 'inline-flex flex-1 items-center justify-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white opacity-60'
                    : 'inline-flex flex-1 items-center justify-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700'
                }
                onClick=${onPreview}
                disabled=${loading}
              >
                ${loading ? 'Đang tải…' : 'Tải xem trước'}
              </button>
              <button
                className="inline-flex items-center justify-center rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
                onClick=${onClear}
              >
                Xóa
              </button>
            </div>
          </div>
        <//>
      </div>

      <div className="md:col-span-8">
        <${Card}
          title=${'Xem trước dữ liệu'}
          right=${preview ? html`<div className="text-xs text-zinc-500">${preview.rows?.length || 0} dòng</div>` : ''}
        >
          ${!preview
            ? html`<div className="rounded-lg border border-dashed border-zinc-200 p-4 text-sm text-zinc-500">
                Nhập thông tin Google Sheet và bấm “Tải xem trước”.
              </div>`
            : html`
                <div className="overflow-auto rounded-lg border border-zinc-200">
                  <table className="w-full border-separate border-spacing-0">
                    <thead className="bg-white">
                      <tr className="text-left text-xs text-zinc-500">
                        <th className="border-b border-zinc-100 px-3 py-2">Cấp</th>
                        <th className="border-b border-zinc-100 px-3 py-2">Mã</th>
                        <th className="border-b border-zinc-100 px-3 py-2">Tên</th>
                        <th className="border-b border-zinc-100 px-3 py-2">Mã cha</th>
                        <th className="border-b border-zinc-100 px-3 py-2 text-right">Chỉ tiêu</th>
                      </tr>
                    </thead>
                    <tbody>
                      ${(preview.rows || []).map(
                        (r, idx) => html`<tr key=${idx}>
                          <td className="border-b border-zinc-50 px-3 py-2 text-sm text-zinc-700">${r.level}</td>
                          <td className="border-b border-zinc-50 px-3 py-2 text-sm font-medium text-zinc-900">${r.unitCode}</td>
                          <td className="border-b border-zinc-50 px-3 py-2 text-sm text-zinc-900">${r.unitName}</td>
                          <td className="border-b border-zinc-50 px-3 py-2 text-sm text-zinc-700">${r.parentUnitCode || '—'}</td>
                          <td className="border-b border-zinc-50 px-3 py-2 text-right text-sm tabular-nums text-zinc-900">${formatNumber(
                            r.targetValue
                          )}</td>
                        </tr>`
                      )}
                    </tbody>
                  </table>
                </div>
                ${(preview.errors || []).length
                  ? html`<div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
                      <div className="text-sm font-semibold text-amber-900">Danh sách lỗi</div>
                      <div className="mt-2 space-y-1">
                        ${preview.errors.map(
                          (e, i) => html`<div key=${i} className="text-sm text-amber-900">
                            ${e.rowIndex === -1 ? '' : `Dòng ${e.rowIndex}: `}${e.message}
                          </div>`
                        )}
                      </div>
                      <div className="mt-2 text-xs text-amber-900/80">Sửa trên Google Sheet rồi tải lại.</div>
                    </div>`
                  : html`<div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
                      Dữ liệu hợp lệ (demo).
                    </div>`}
              `}
        <//>
      </div>
    </div>
  `
}

