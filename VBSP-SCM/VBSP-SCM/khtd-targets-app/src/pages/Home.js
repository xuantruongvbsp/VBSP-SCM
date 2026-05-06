import { html, React } from '../html.js'
import { Card } from '../components/Card.js'
import { useAppState } from '../state.js'
import { apiGet } from '../api.js'
import { shortUrl } from '../utils.js'
import { Link } from 'https://esm.sh/react-router-dom@6.23.1'

export function HomePage() {
  const { period, setPeriod, periods, setPeriods, lastSync, setLastSync } = useAppState()
  const [loading, setLoading] = React.useState(false)

  React.useEffect(() => {
    let alive = true
    setLoading(true)
    apiGet('/api/status')
      .then((data) => {
        if (!alive) return
        setPeriods((data.periods && data.periods.length ? data.periods : ['2026-Q2']).slice(0))
        setLastSync(data.lastSync || { status: 'never', at: null })
      })
      .finally(() => {
        if (!alive) return
        setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [setPeriods, setLastSync])

  const syncTone = lastSync?.status === 'success' ? 'text-emerald-700' : lastSync?.status === 'error' ? 'text-red-700' : 'text-zinc-600'

  return html`
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-6">
      <${Card}
        title=${'Chọn kỳ/đợt'}
        right=${loading ? html`<div className="text-xs text-zinc-500">Đang tải…</div>` : ''}
      >
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div className="w-full md:max-w-sm">
            <label className="mb-1 block text-xs font-medium text-zinc-600">Kỳ/đợt</label>
            <select
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
              value=${period}
              onChange=${(e) => setPeriod(e.target.value)}
            >
              ${periods.map((p) => html`<option key=${p} value=${p}>${p}</option>`)}
            </select>
          </div>
          <div className="text-xs text-zinc-500">Kỳ đang chọn sẽ dùng mặc định cho các màn hình.</div>
        </div>
      <//>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <${Card} title=${'Nhập dữ liệu Google Sheet'}>
          <div className="text-sm text-zinc-700">Tải dữ liệu từ Google Sheet, xem trước và kiểm tra lỗi.</div>
          <div className="mt-4">
            <${Link}
              to=${'/google-sheet-import'}
              className="inline-flex items-center justify-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Mở
            <//>
          </div>
        <//>
        <${Card} title=${'Giao/Điều chỉnh chỉ tiêu'}>
          <div className="text-sm text-zinc-700">Nhập/điều chỉnh chỉ tiêu theo phân cấp CN hoặc PGD.</div>
          <div className="mt-4">
            <${Link}
              to=${'/targets'}
              className="inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
            >
              Mở
            <//>
          </div>
        <//>
      </div>

      <${Card} title=${'Trạng thái đồng bộ gần nhất'}>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div>
            <div className="text-xs text-zinc-500">Kết quả</div>
            <div className=${`text-sm font-medium ${syncTone}`}>${lastSync?.status || 'unknown'}</div>
          </div>
          <div>
            <div className="text-xs text-zinc-500">Thời gian</div>
            <div className="text-sm text-zinc-800">${lastSync?.at || '—'}</div>
          </div>
          <div>
            <div className="text-xs text-zinc-500">Nguồn</div>
            <div className="text-sm text-zinc-800">${shortUrl(lastSync?.sheetUrl || '') || '—'}</div>
            <div className="text-xs text-zinc-500">${lastSync?.sheetName ? `Tab: ${lastSync.sheetName}` : ''}</div>
          </div>
        </div>
      <//>
    </div>
  `
}

