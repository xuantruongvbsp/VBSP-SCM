import { html } from '../html.js'

function TreeItem({ node, selectedId, onSelect, depth }) {
  const isSelected = selectedId === node.id
  return html`
    <div>
      <button
        className=${
          isSelected
            ? 'w-full rounded-lg bg-zinc-900 px-3 py-2 text-left text-sm font-medium text-white'
            : 'w-full rounded-lg px-3 py-2 text-left text-sm text-zinc-800 hover:bg-zinc-100'
        }
        style=${{ paddingLeft: `${12 + depth * 12}px` }}
        onClick=${() => onSelect(node)}
      >
        <div className="truncate">${node.label}</div>
        <div className=${isSelected ? 'text-xs text-zinc-200' : 'text-xs text-zinc-500'}>${node.meta || ''}</div>
      </button>
      ${node.children && node.children.length
        ? html`<div className="mt-1 space-y-1">
            ${node.children.map(
              (ch) => html`<${TreeItem} key=${ch.id} node=${ch} selectedId=${selectedId} onSelect=${onSelect} depth=${
                depth + 1
              } />`
            )}
          </div>`
        : ''}
    </div>
  `
}

export function Tree({ title, nodes, selectedId, onSelect }) {
  return html`
    <div className="rounded-xl border border-zinc-200 bg-white shadow-sm">
      <div className="border-b border-zinc-100 px-4 py-3">
        <div className="text-sm font-semibold">${title}</div>
      </div>
      <div className="max-h-[calc(100vh-220px)] space-y-1 overflow-auto p-3">
        ${nodes.length
          ? nodes.map((n) => html`<${TreeItem} key=${n.id} node=${n} selectedId=${selectedId} onSelect=${onSelect} depth=${0} />`)
          : html`<div className="rounded-lg border border-dashed border-zinc-200 p-3 text-sm text-zinc-500">
              Chưa có dữ liệu cây.
            </div>`}
      </div>
    </div>
  `
}

