import { html, React } from '../html.js'
import { Card } from '../components/Card.js'
import { Tree } from '../components/Tree.js'
import { TargetsTable } from '../components/TargetsTable.js'
import { useAppState } from '../state.js'
import { apiGet, apiPost } from '../api.js'
import { clampNumber } from '../utils.js'

function buildTree(unitType, rows, rootCode) {
  if (!rootCode) return []
  const byParent = new Map()
  for (const r of rows) {
    const p = r.parentUnitCode || ''
    if (!byParent.has(p)) byParent.set(p, [])
    byParent.get(p).push(r)
  }

  const rootRow = rows.find((r) => r.unitCode === rootCode)
  const rootLabel = rootRow ? `${rootRow.unitName}` : rootCode

  const children = (byParent.get(rootCode) || []).map((r) => ({
    id: r.unitCode,
    label: r.unitName,
    meta: r.unitCode,
    level: r.level,
    row: r,
    children: (byParent.get(r.unitCode) || []).map((rr) => ({
      id: rr.unitCode,
      label: rr.unitName,
      meta: rr.unitCode,
      level: rr.level,
      row: rr,
      children: [],
    })),
  }))

  return [
    {
      id: rootCode,
      label: rootLabel,
      meta: unitType === 'CN' ? 'Tỉnh' : 'Xã',
      level: rootRow?.level || (unitType === 'CN' ? 'TINH' : 'XA'),
      row: rootRow || null,
      children,
    },
  ]
}

export function TargetsPage() {
  const { period, periods, setPeriods, setToast } = useAppState()
  const [unitType, setUnitType] = React.useState('CN')
  const [periodLocal, setPeriodLocal] = React.useState(period)
  const [rows, setRows] = React.useState([])
  const [loadedRows, setLoadedRows] = React.useState([])
  const [loading, setLoading] = React.useState(false)
  const [rootCode, setRootCode] = React.useState('')
  const [selectedNode, setSelectedNode] = React.useState(null)
  const [editedMap, setEditedMap] = React.useState(new Set())

  const rootOptions = React.useMemo(() => {
    const level = unitType === 'CN' ? 'TINH' : 'XA'
    return rows.filter((r) => r.level === level)
  }, [rows, unitType])

  const treeNodes = React.useMemo(() => buildTree(unitType, rows, rootCode), [unitType, rows, rootCode])

  const selectedRow = selectedNode?.row || rows.find((r) => r.unitCode === selectedNode?.id) || null

  const childrenRows = React.useMemo(() => {
    if (!selectedNode) return []
    const id = selectedNode.id
    return rows.filter((r) => r.parentUnitCode === id)
  }, [rows, selectedNode])

  const parentTotal = selectedRow ? clampNumber(selectedRow.targetValue) : null
  const childrenTotal = childrenRows.reduce((s, r) => s + clampNumber(r.targetValue), 0)
  const showMismatch = parentTotal != null && Math.abs(childrenTotal - parentTotal) > 1e-6 && childrenRows.length > 0

  const load = React.useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiGet(`/api/targets?unitType=${encodeURIComponent(unitType)}&period=${encodeURIComponent(periodLocal)}`)
      const r = data.rows || []
      setRows(r)
      setLoadedRows(JSON.parse(JSON.stringify(r)))
      setEditedMap(new Set())
      if (r.length) {
        const firstRoot = (unitType === 'CN' ? r.find((x) => x.level === 'TINH') : r.find((x) => x.level === 'XA'))
        if (firstRoot) {
          setRootCode(firstRoot.unitCode)
          setSelectedNode({ id: firstRoot.unitCode, label: firstRoot.unitName, row: firstRoot })
        }
      }
      if (data.periods && Array.isArray(data.periods)) {
        setPeriods(data.periods)
      } else {
        setPeriods(periods)
      }
      setToast({ tone: 'success', message: 'Tải dữ liệu chỉ tiêu thành công.' })
    } catch (e) {
      setToast({ tone: 'error', message: `Không tải được chỉ tiêu: ${e.message}` })
    } finally {
      setLoading(false)
    }
  }, [periodLocal, periods, setPeriods, setToast, unitType])

  React.useEffect(() => {
    setRootCode('')
    setSelectedNode(null)
    setEditedMap(new Set())
    load()
  }, [load, periodLocal, unitType])

  function onSelectRoot(code) {
    setRootCode(code)
    const r = rows.find((x) => x.unitCode === code) || null
    if (r) setSelectedNode({ id: r.unitCode, label: r.unitName, row: r })
  }

  function onSelectNode(n) {
    setSelectedNode(n)
  }

  function onChangeValue(unitCode, raw) {
    const nextVal = clampNumber(raw)
    setRows((prev) => prev.map((r) => (r.unitCode === unitCode ? { ...r, targetValue: nextVal } : r)))
    setEditedMap((prev) => {
      const n = new Set(prev)
      n.add(unitCode)
      return n
    })
  }

  async function onSave() {
    try {
      await apiPost('/api/targets/save', { period: periodLocal, unitType, rows })
      setLoadedRows(JSON.parse(JSON.stringify(rows)))
      setEditedMap(new Set())
      setToast({ tone: 'success', message: 'Đã lưu điều chỉnh.' })
    } catch (e) {
      setToast({ tone: 'error', message: `Không lưu được: ${e.message}` })
    }
  }

  function onUndo() {
    setRows(JSON.parse(JSON.stringify(loadedRows)))
    setEditedMap(new Set())
    setToast({ tone: 'info', message: 'Đã hoàn tác thay đổi.' })
  }

  const empty = !loading && (!rows || rows.length === 0)

  return html`
    <div className="mx-auto max-w-5xl space-y-4 px-4 py-6">
      <${Card}>
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div className="flex flex-col gap-3 md:flex-row md:items-end">
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-600">Loại đơn vị</label>
              <div className="inline-flex rounded-lg border border-zinc-200 bg-white p-1">
                <button
                  className=${
                    unitType === 'CN'
                      ? 'rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white'
                      : 'rounded-md px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100'
                  }
                  onClick=${() => setUnitType('CN')}
                >
                  CN
                </button>
                <button
                  className=${
                    unitType === 'PGD'
                      ? 'rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white'
                      : 'rounded-md px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100'
                  }
                  onClick=${() => setUnitType('PGD')}
                >
                  PGD
                </button>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-600">Kỳ/đợt</label>
              <select
                className="w-56 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
                value=${periodLocal}
                onChange=${(e) => setPeriodLocal(e.target.value)}
              >
                ${(periods && periods.length ? periods : ['2026-Q2']).map((p) => html`<option key=${p} value=${p}>${p}</option>`)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-600">${unitType === 'CN' ? 'Tỉnh' : 'Xã'}</label>
              <select
                className="w-64 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
                value=${rootCode}
                onChange=${(e) => onSelectRoot(e.target.value)}
              >
                <option value="">Chọn…</option>
                ${rootOptions.map((r) => html`<option key=${r.unitCode} value=${r.unitCode}>${r.unitName}</option>`)}
              </select>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              className=${
                loading
                  ? 'inline-flex items-center justify-center rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 opacity-60'
                  : 'inline-flex items-center justify-center rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50'
              }
              onClick=${load}
              disabled=${loading}
            >
              ${loading ? 'Đang tải…' : 'Tải dữ liệu'}
            </button>
            <button
              className=${
                editedMap.size === 0
                  ? 'inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white opacity-50'
                  : 'inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800'
              }
              onClick=${onSave}
              disabled=${editedMap.size === 0}
            >
              Lưu
            </button>
            <button
              className=${
                editedMap.size === 0
                  ? 'inline-flex items-center justify-center rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 opacity-50'
                  : 'inline-flex items-center justify-center rounded-lg border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50'
              }
              onClick=${onUndo}
              disabled=${editedMap.size === 0}
            >
              Hoàn tác
            </button>
          </div>
        </div>
      <//>

      ${empty
        ? html`<${Card} title=${'Chưa có dữ liệu'}>
            <div className="text-sm text-zinc-700">Chưa có dữ liệu cho kỳ/đợt. Hãy nhập Google Sheet trước (demo) hoặc đổi kỳ.</div>
          <//>`
        : html`
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
              <${Tree} title=${unitType === 'CN' ? 'Cây tỉnh → xã' : 'Cây xã → thôn'} nodes=${treeNodes} selectedId=${selectedNode?.id || ''} onSelect=${onSelectNode} />
              <div className="space-y-3">
                <${TargetsTable}
                  title=${selectedNode ? `Danh sách cấp con của: ${selectedNode.label}` : 'Chọn đơn vị để xem'}
                  rows=${childrenRows}
                  editedMap=${editedMap}
                  onChangeValue=${onChangeValue}
                />
                <div className="rounded-xl border border-zinc-200 bg-white px-4 py-3 shadow-sm">
                  <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                    <div>
                      <div className="text-xs text-zinc-500">Tổng cấp con</div>
                      <div className="text-sm font-semibold tabular-nums text-zinc-900">${childrenTotal.toLocaleString('vi-VN')}</div>
                    </div>
                    <div>
                      <div className="text-xs text-zinc-500">Tổng cấp cha</div>
                      <div className="text-sm font-semibold tabular-nums text-zinc-900">${parentTotal == null ? '—' : parentTotal.toLocaleString('vi-VN')}</div>
                    </div>
                    ${showMismatch
                      ? html`<div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                          Cảnh báo: tổng cấp con khác tổng cấp cha.
                        </div>`
                      : html`<div className="text-sm text-zinc-500">${childrenRows.length ? 'Tổng hợp OK.' : 'Chưa có cấp con.'}</div>`}
                  </div>
                </div>
              </div>
            </div>
          `}
    </div>
  `
}
